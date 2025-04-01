from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
import logging
import tempfile
import os
import json
import shutil # For cleaning up temp dirs/files

from ..services import lighthouse_service, ml_service, fvm_service
from ..models.data_models import TrainRequest, TrainResponse, ErrorResponse

router = APIRouter(
    prefix="/training",
    tags=["Model Training"],
)

logger = logging.getLogger(__name__)

def run_training_job(
    dataset_cid: str,
    # Add other params later if needed (hyperparameters, etc.)
):
    """Background task to run the full training pipeline."""
    logger.info(f"Background training job started for dataset CID: {dataset_cid}")
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
        # Re-save info file with dataset CID
        with open(info_path, 'w') as f:
            json.dump(model_info, f, indent=2)

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

        # 4. Register Provenance on FVM (Placeholder)
        logger.info("Registering provenance on FVM...")
        fvm_tx_hash = fvm_service.register_asset_provenance(
            dataset_cid=dataset_cid,
            model_cid=model_cid,
            metadata_cid=model_info_cid
            # Add owner address later from authenticated user
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
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse}
    }
)
def start_training(
    train_request: TrainRequest,
    background_tasks: BackgroundTasks
    # TODO: Add dependency for authenticated user later: user: User = Depends(get_current_user)
):
    """
    Initiates a model training job in the background.

    Takes a dataset CID, downloads the data, trains a model,
    uploads the model and metadata to Lighthouse, and registers provenance on FVM.
    This endpoint returns immediately after starting the background task.

    - **dataset_cid**: CID of the dataset to train on.
    """
    logger.info(f"Received request to start training for dataset CID: {train_request.dataset_cid}")
    # TODO: Validate dataset_cid format?
    # TODO: Check if dataset CID exists / is accessible? (maybe deferred to background task)

    # Add the training job to background tasks
    background_tasks.add_task(run_training_job, train_request.dataset_cid)

    logger.info(f"Training job for dataset {train_request.dataset_cid} added to background tasks.")

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