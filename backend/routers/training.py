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

router = APIRouter(
    prefix="/training",
    tags=["Model Training"],
)

logger = logging.getLogger(__name__)

# --- In-Memory Job Store (Basic Example) ---
# Stores job_id -> TrainingStatusResponse object
# WARNING: This is lost on server restart!
_training_jobs: Dict[str, TrainingStatusResponse] = {}

def update_job_status(job_id: str, status: str, message: str | None = None, **kwargs):
    """Helper to update the status of a job in the store."""
    if job_id in _training_jobs:
        job = _training_jobs[job_id]
        job.status = status
        job.message = message
        job.updated_at = datetime.now(timezone.utc)
        # Update result fields if provided
        for key, value in kwargs.items():
            if hasattr(job, key):
                setattr(job, key, value)
        logger.info(f"Updated job {job_id} status to {status}")
    else:
        logger.warning(f"Attempted to update status for unknown job_id: {job_id}")

def run_training_job(
    job_id: str, 
    dataset_cid: str,
    owner_address: str,
    model_type: str,
    target_column: str,
    hyperparameters: Dict[str, Any]
):
    """Background task to run the full training pipeline, updating status."""
    logger.info(f"Background training job {job_id} started. Dataset: {dataset_cid}, Owner: {owner_address}, Model: {model_type}, Target: {target_column}, Params: {hyperparameters}")
    temp_dir = None
    model_cid = None # Define potential result vars here
    model_info_cid = None
    accuracy = None
    fvm_tx_hash = None

    try:
        # Create a temporary directory
        temp_dir = tempfile.mkdtemp()
        logger.info(f"Created temporary directory for training job {job_id}: {temp_dir}")

        # 1. Download dataset
        update_job_status(job_id, "DOWNLOADING")
        downloaded_dataset_path = os.path.join(temp_dir, f"{dataset_cid}_dataset.csv")
        if not lighthouse_service.download_file(dataset_cid, downloaded_dataset_path):
            logger.error(f"Job {job_id}: Failed to download dataset {dataset_cid}")
            update_job_status(job_id, "FAILED", "Failed to download dataset from storage.")
            return

        # 2. Train model
        update_job_status(job_id, "TRAINING")
        model, model_info, model_path, info_path = ml_service.train_model_on_dataset(
            dataset_path=downloaded_dataset_path,
            model_type=model_type,
            target_column=target_column,
            hyperparameters=hyperparameters
        )
        if not model or not model_info or not model_path or not info_path:
            logger.error(f"Job {job_id}: Model training failed for dataset {dataset_cid}")
            update_job_status(job_id, "FAILED", "Model training process failed.")
            return
        
        # Store parameters used in metadata
        accuracy = model_info.get('accuracy')
        model_info['source_dataset_cid'] = dataset_cid
        model_info['owner_address'] = owner_address
        model_info['model_type'] = model_type
        model_info['target_column'] = target_column
        model_info['hyperparameters_used'] = hyperparameters
        
        # Update info file before uploading
        with open(info_path, 'w') as f:
            json.dump(model_info, f, indent=2)

        # 3. Upload model and metadata
        update_job_status(job_id, "UPLOADING_MODEL")
        model_cid = lighthouse_service.upload_file(model_path)
        if not model_cid:
            logger.error(f"Job {job_id}: Failed to upload trained model file.")
            update_job_status(job_id, "FAILED", "Failed to upload trained model file.")
            return

        update_job_status(job_id, "UPLOADING_METADATA")
        model_info_cid = lighthouse_service.upload_file(info_path)
        if not model_info_cid:
            logger.error(f"Job {job_id}: Failed to upload model info file.")
            update_job_status(job_id, "FAILED", "Failed to upload model metadata file.")
            return

        # 4. Register Provenance on FVM
        update_job_status(job_id, "REGISTERING_PROVENANCE")
        fvm_tx_hash = fvm_service.register_asset_provenance(
            owner_address=owner_address,
            asset_type="Model",
            name="",
            dataset_cid=dataset_cid,
            model_cid=model_cid,
            metadata_cid=model_info_cid
        )
        if not fvm_tx_hash:
             # Log warning but potentially continue? Or mark as completed with warning?
             logger.warning(f"Job {job_id}: Failed to register provenance on FVM. Uploads complete.")
             # Decide if this constitutes full failure or partial success
             # For now, mark as completed but note the issue.
             update_job_status(job_id, "COMPLETED",
                               message="Provenance registration failed, but assets uploaded.",
                               model_cid=model_cid,
                               model_info_cid=model_info_cid,
                               accuracy=accuracy,
                               fvm_tx_hash=None)
             return # Exit successfully despite warning

        # 5. Mark as Completed
        update_job_status(job_id, "COMPLETED",
                          message="Training and registration completed successfully.",
                          model_cid=model_cid,
                          model_info_cid=model_info_cid,
                          accuracy=accuracy,
                          fvm_tx_hash=fvm_tx_hash)
        logger.info(f"Training job {job_id} completed successfully.")

    except Exception as e:
        logger.error(f"An unexpected error occurred in background training job {job_id}: {e}", exc_info=True)
        update_job_status(job_id, "FAILED", f"An unexpected error occurred: {e}")

    finally:
        # Clean up temporary directory
        if temp_dir and os.path.exists(temp_dir):
            try: shutil.rmtree(temp_dir)
            except Exception as e: logger.error(f"Error cleaning up temp dir {temp_dir} for job {job_id}: {e}")

@router.post(
    "/start",
    response_model=TrainResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={ # Add 401
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse}
    }
)
def start_training(
    train_request: TrainRequest,
    background_tasks: BackgroundTasks,
    current_user_address: str = Depends(get_current_active_user)
):
    """
    Initiates a model training job in the background for the authenticated user.
    Requires JWT authentication.

    Takes a dataset CID, downloads the data, trains a model,
    uploads the model and metadata to Lighthouse, and registers provenance on FVM.
    This endpoint returns immediately after starting the background task.

    - **dataset_cid**: CID of the dataset to train on.
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
    _training_jobs[job_id] = initial_status
    logger.info(f"Created training job {job_id} with PENDING status.")

    # Add the training job to background tasks, passing the new parameters
    background_tasks.add_task(
        run_training_job,
        job_id=job_id,
        dataset_cid=train_request.dataset_cid,
        owner_address=current_user_address,
        model_type=train_request.model_type,
        target_column=train_request.target_column,
        hyperparameters=train_request.hyperparameters
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
def get_training_status(
    job_id: str,
    current_user_address: str = Depends(get_current_active_user) # Secure the endpoint
):
    """Retrieves the status and results of a specific training job."""
    logger.info(f"User {current_user_address} requesting status for job_id: {job_id}")
    job_status = _training_jobs.get(job_id)

    if not job_status:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Training job with ID {job_id} not found.")

    # Authorization check: Ensure the requesting user owns the job
    if job_status.owner_address != current_user_address:
        logger.warning(f"User {current_user_address} attempted to access job {job_id} owned by {job_status.owner_address}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authorized to view this training job status.")

    return job_status 