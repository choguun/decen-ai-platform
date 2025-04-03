from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
import logging
import tempfile
import os
import json
import shutil # For cleaning up temp dirs/files

from ..services import lighthouse_service, ml_service, fvm_service
from ..models.data_models import TrainRequest, TrainResponse, ErrorResponse
from ..routers.auth import get_current_active_user # Import the auth dependency

router = APIRouter(
    prefix="/training",
    tags=["Model Training"],
)

logger = logging.getLogger(__name__)

def run_training_job(
    dataset_cid: str,
    owner_address: str # Add owner address parameter
):
    """Background task to run the full training pipeline, including owner address."""
    logger.info(f"Background training job started for dataset CID: {dataset_cid} by owner: {owner_address}")
    temp_dir = None
    downloaded_dataset_path = None
    model_path = None
    info_path = None

    try:
        # Create a temporary directory for all files
        temp_dir = tempfile.mkdtemp()
        logger.info(f"Created temporary directory for training: {temp_dir}")

        # 1. Download dataset
        downloaded_dataset_path = os.path.join(temp_dir, f"{dataset_cid}_dataset.csv")
        logger.info(f"Attempting to download dataset {dataset_cid} to {downloaded_dataset_path}")
        if not lighthouse_service.download_file(dataset_cid, downloaded_dataset_path):
            logger.error(f"Failed to download dataset {dataset_cid}")
            # TODO: Implement better status reporting for background tasks
            return # Exit task
        logger.info(f"Dataset {dataset_cid} downloaded successfully.")

        # 2. Train model
        model, model_info, model_path, info_path = ml_service.train_model_on_dataset(downloaded_dataset_path)
        if not model or not model_info or not model_path or not info_path:
            logger.error(f"Model training failed for dataset {dataset_cid}")
            # TODO: Implement better status reporting
            return # Exit task
        logger.info(f"Model training successful. Accuracy: {model_info.get('accuracy')}")
        # Add dataset CID to model_info for provenance
        model_info['source_dataset_cid'] = dataset_cid
        # Add owner address to metadata
        model_info['owner_address'] = owner_address
        # Re-save info file with dataset CID and owner address
        with open(info_path, 'w') as f:
            json.dump(model_info, f, indent=2)
        logger.info(f"Model info updated with owner {owner_address} and dataset CID {dataset_cid}")

        # 3. Upload model and metadata
        logger.info(f"Uploading trained model from {model_path}")
        model_cid = lighthouse_service.upload_file(model_path)
        if not model_cid:
            logger.error("Failed to upload trained model file.")
            # TODO: Status reporting
            return
        logger.info(f"Trained model uploaded successfully. CID: {model_cid}")

        logger.info(f"Uploading model info from {info_path}")
        model_info_cid = lighthouse_service.upload_file(info_path)
        if not model_info_cid:
            # Warning: Model uploaded, but info failed. State is inconsistent.
            logger.error("Failed to upload model info file.")
            # TODO: Status reporting / potential cleanup?
            return
        logger.info(f"Model info uploaded successfully. CID: {model_info_cid}")

        # 4. Register Provenance on FVM (Now uses owner_address)
        logger.info(f"Registering provenance on FVM for owner {owner_address}...")
        fvm_tx_hash = fvm_service.register_asset_provenance(
            owner_address=owner_address, # Pass the owner address
            dataset_cid=dataset_cid,
            model_cid=model_cid,
            metadata_cid=model_info_cid
        )
        if fvm_tx_hash:
            logger.info(f"Provenance registered successfully. Tx Hash: {fvm_tx_hash}")
        else:
            logger.warning("Failed to register provenance on FVM. Uploads are complete.")
            # TODO: Status reporting

        # TODO: Update database/status store with results (dataset_cid, model_cid, info_cid, accuracy, tx_hash)
        logger.info(f"Training job for dataset {dataset_cid} completed successfully.")
        logger.info(f"Results: Model CID={model_cid}, Info CID={model_info_cid}, Accuracy={model_info.get('accuracy')}, FVM Tx={fvm_tx_hash}")

    except Exception as e:
        logger.error(f"An unexpected error occurred in the background training task: {e}", exc_info=True)
        # TODO: Update job status to failed

    finally:
        # Clean up temporary directory
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                logger.info(f"Cleaned up temporary directory: {temp_dir}")
            except Exception as e:
                logger.error(f"Error cleaning up temporary directory {temp_dir}: {e}")

@router.post(
    "/start",
    response_model=TrainResponse, # Response indicates initiation, not completion
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        # Add 401 response for auth failure
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse}
    }
)
def start_training(
    train_request: TrainRequest,
    background_tasks: BackgroundTasks,
    # Add the dependency to get authenticated user address
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
    logger.info(f"User {current_user_address} requested training for dataset CID: {train_request.dataset_cid}")
    # TODO: Validate dataset_cid format?
    # TODO: Check if dataset CID exists / is accessible? (maybe deferred to background task)

    # Add the training job to background tasks, passing the user address
    background_tasks.add_task(
        run_training_job,
        dataset_cid=train_request.dataset_cid,
        owner_address=current_user_address # Pass the authenticated user address
    )

    logger.info(f"Training job for dataset {train_request.dataset_cid} added to background tasks for user {current_user_address}.")

    # Return an initial response - actual results come from background task
    # Note: CIDs and Tx hash won't be available here yet.
    return TrainResponse(
        message="Training job initiated successfully. Check status later.",
        dataset_cid=train_request.dataset_cid,
        model_cid="pending",
        model_info_cid="pending",
        fvm_tx_hash="pending"
    )

# TODO: Add endpoint to check training job status 