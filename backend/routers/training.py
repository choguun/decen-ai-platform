from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
import logging
import tempfile
import os
import json
import shutil
import uuid # For generating job IDs
from datetime import datetime, timezone # For timestamps
from typing import Dict, Any # For job store type hint

from ..services import lighthouse_service, ml_service, fvm_service
from ..models.data_models import TrainRequest, TrainResponse, ErrorResponse, TrainingStatusResponse
from ..routers.auth import get_current_active_user
from .. import job_store # Import the new job store module
from .. import config # Import config to get service fee

router = APIRouter(
    prefix="/training",
    tags=["Model Training"],
)

logger = logging.getLogger(__name__)

def run_training_job(
    job_id: str, 
    dataset_cid: str,
    owner_address: str,
    model_type: str,
    target_column: str,
    hyperparameters: Dict[str, Any],
    payment_tx_hash: str,
    payment_nonce: str
):
    """Background task to verify payment, then run the training part of the pipeline."""
    logger.info(f"Background job {job_id} started. Verifying payment {payment_tx_hash}...")
    # --- Optional: Update status to indicate verification step --- 
    job_store.update_job_status(job_id, "VERIFYING_PAYMENT", "Verifying service fee payment...")
    
    temp_dir = None # We still use a temp dir for the downloaded dataset
    temp_model_path = None # Will hold the path to the saved model in temp_dir
    temp_info_path = None # Will hold the path to the saved info in temp_dir
    accuracy = None

    try:
        # --- 1. Payment Verification --- 
        expected_fee = config.TRAINING_SERVICE_FEE 
        if not expected_fee: # Check config again in background task
             logger.error(f"Job {job_id}: Configuration error: TRAINING_SERVICE_FEE is not set.")
             job_store.update_job_status(job_id, "FAILED", "Service configuration error.")
             return

        payment_verified = fvm_service.verify_payment(
            tx_hash=payment_tx_hash,
            expected_payer=owner_address, # Use owner_address passed to task
            expected_amount=expected_fee, 
            expected_service_type="TRAINING",
            expected_nonce=payment_nonce
        )

        if not payment_verified:
            logger.warning(f"Job {job_id}: Payment verification failed for tx {payment_tx_hash}")
            job_store.update_job_status(job_id, "FAILED", "Service fee payment verification failed.")
            return
        
        logger.info(f"Job {job_id}: Payment verified successfully.")
        # --- End Payment Verification --- 

        # Create a temporary directory for the job
        temp_dir = tempfile.mkdtemp()
        logger.info(f"Created temporary directory for training job {job_id}: {temp_dir}")

        # 2. Download dataset into the job's temp directory
        job_store.update_job_status(job_id, "DOWNLOADING")
        downloaded_dataset_path = os.path.join(temp_dir, f"{dataset_cid}_dataset.csv")
        if not lighthouse_service.download_file(dataset_cid, downloaded_dataset_path):
            logger.error(f"Job {job_id}: Failed to download dataset {dataset_cid}")
            job_store.update_job_status(job_id, "FAILED", "Failed to download dataset from storage.")
            return

        # 3. Train model, saving outputs into the same job temp directory
        job_store.update_job_status(job_id, "TRAINING")
        model, model_info, saved_model_path, saved_info_path = ml_service.train_model_on_dataset(
            dataset_path=downloaded_dataset_path,
            output_dir=temp_dir, # Pass the temp dir for saving model/info
            model_type=model_type,
            target_column=target_column,
            hyperparameters=hyperparameters
        )
        if not model or not model_info or not saved_model_path or not saved_info_path:
            logger.error(f"Job {job_id}: Model training failed for dataset {dataset_cid}")
            job_store.update_job_status(job_id, "FAILED", "Model training process failed.")
            return
        
        # Store the paths to the generated files for later upload
        temp_model_path = saved_model_path
        temp_info_path = saved_info_path
        
        # Store parameters used in metadata
        accuracy = model_info.get('accuracy')
        model_info['source_dataset_cid'] = dataset_cid
        model_info['owner_address'] = owner_address
        model_info['model_type'] = model_type
        model_info['target_column'] = target_column
        model_info['hyperparameters_used'] = hyperparameters
        
        # Update info file *in place* within the temp directory
        with open(temp_info_path, 'w') as f:
            json.dump(model_info, f, indent=2)

        # 4. Mark Training as Complete (Upload & Registration done separately)
        job_store.update_job_status(
            job_id, 
            "TRAINING_COMPLETE",
            message="Model training finished. Ready for upload and registration.",
            accuracy=accuracy, 
            temp_model_path=temp_model_path, # Store the path for the next step
            temp_info_path=temp_info_path    # Store the path for the next step
        )
        logger.info(f"Training job {job_id} reached TRAINING_COMPLETE status.")

    except Exception as e:
        logger.error(f"An unexpected error occurred in background training job {job_id}: {e}", exc_info=True)

        # Ensure status is FAILED if an exception occurs
        job_store.update_job_status(job_id, "FAILED", message=f"An unexpected error occurred during training: {e}")

        # If an error occurred *after* model files were saved, we might still have the paths
        # But the job failed, so maybe clear them or leave them for debugging?
        # For now, let's leave them if they exist, but the status is FAILED.

    finally:
        # --- Selective Cleanup --- 
        # Only clean up the downloaded dataset file.
        # Leave the generated model and info files for the upload step.
        # The upload endpoint will be responsible for cleaning up those files.
        downloaded_dataset_path = os.path.join(temp_dir, f"{dataset_cid}_dataset.csv") if temp_dir and dataset_cid else None
        if downloaded_dataset_path and os.path.exists(downloaded_dataset_path):
            try: 
                os.remove(downloaded_dataset_path)
                logger.info(f"Job {job_id}: Cleaned up downloaded dataset file: {downloaded_dataset_path}")
            except Exception as e: 
                logger.error(f"Job {job_id}: Error cleaning up downloaded dataset file {downloaded_dataset_path}: {e}")
        
        # Note: The temporary directory itself (temp_dir) might remain with model/info files.
        # Consider a separate cleanup mechanism for old/orphaned job directories if necessary.

@router.post(
    "/start",
    response_model=TrainResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={ # Add 401
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
        status.HTTP_402_PAYMENT_REQUIRED: {"model": ErrorResponse, "description": "Payment verification failed"},
    }
)
async def start_training(
    train_request: TrainRequest,
    background_tasks: BackgroundTasks,
    current_user_address: str = Depends(get_current_active_user)
):
    """
    Initiates a model training job in the background for the authenticated user.
    Payment verification happens asynchronously within the background task.
    Requires JWT authentication.

    Takes a dataset CID, downloads the data, trains a model,
    saves the model/metadata locally, and sets status to TRAINING_COMPLETE.
    This endpoint returns immediately after starting the background task.

    - **dataset_cid**: CID of the dataset to train on.
    - **paymentTxHash**: Transaction hash of the service fee payment.
    - **paymentNonce**: Unique nonce associated with the payment transaction.
    """
    logger.info(f"User {current_user_address} requesting training. Payload: {train_request.dict()}")

    # Generate a unique Job ID
    job_id = str(uuid.uuid4())

    # Store initial job status
    now = datetime.now(timezone.utc)
    initial_status = TrainingStatusResponse(
        job_id=job_id,
        status="PENDING",
        dataset_cid=train_request.dataset_cid,
        owner_address=current_user_address,
        created_at=now,
        updated_at=now
    )
    job_store.store_job(initial_status)
    logger.info(f"Created training job {job_id} with PENDING status.")

    # Add the training job to background tasks, passing the new parameters
    background_tasks.add_task(
        run_training_job,
        job_id=job_id,
        dataset_cid=train_request.dataset_cid,
        owner_address=current_user_address,
        model_type=train_request.model_type,
        target_column=train_request.target_column,
        hyperparameters=train_request.hyperparameters,
        # --- Pass payment details to background task --- 
        payment_tx_hash=train_request.paymentTxHash,
        payment_nonce=train_request.paymentNonce
    )

    # Return job ID in the initial response
    return TrainResponse(
        job_id=job_id,
        dataset_cid=train_request.dataset_cid
    )

@router.get(
    "/status/{job_id}",
    response_model=TrainingStatusResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse} # Check if user owns job?
    }
)
async def get_training_status(
    job_id: str,
    current_user_address: str = Depends(get_current_active_user) # Secure the endpoint
):
    """Retrieves the status and results of a specific training job."""
    logger.info(f"User {current_user_address} requesting status for job_id: {job_id}")
    job_status = job_store.get_job(job_id)

    if not job_status:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Training job with ID {job_id} not found.")

    # Authorization check: Ensure the requesting user owns the job
    if job_status.owner_address != current_user_address:
        logger.warning(f"User {current_user_address} attempted to access job {job_id} owned by {job_status.owner_address}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authorized to view this training job status.")

    return job_status 