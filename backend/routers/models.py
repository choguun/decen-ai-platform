# backend/routers/models.py

import logging
import os
from fastapi import APIRouter, Depends, HTTPException, status

from .. import job_store
from ..services import lighthouse_service, fvm_service
from ..models.data_models import (
    UploadTrainedModelRequest, 
    UploadTrainedModelResponse, 
    ErrorResponse
)
from ..routers.auth import get_current_active_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/models",
    tags=["Model Management"],
    responses={404: {"description": "Not found"}}
)

@router.post(
    "/{job_id}/upload",
    response_model=UploadTrainedModelResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload Trained Model and Register Provenance",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse, "description": "Not authenticated"},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse, "description": "User does not own this job"},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "Job not found or required files missing"},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse, "description": "Job is not in TRAINING_COMPLETE state"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse, "description": "Upload or registration failed"}
    }
)
async def upload_and_register_model(
    job_id: str,
    upload_request: UploadTrainedModelRequest,
    current_user_address: str = Depends(get_current_active_user)
) -> UploadTrainedModelResponse:
    """
    Takes a completed training job ID, uploads the generated model and info 
    files to Lighthouse, registers provenance on FVM, and updates the job status.

    Requires the job to be in the 'TRAINING_COMPLETE' state.
    Requires JWT authentication and user must be the owner of the job.
    """
    logger.info(f"User {current_user_address} requesting upload for job {job_id}. Payload: {upload_request.dict()}")

    job = job_store.get_job(job_id)

    # --- Validations ---
    if not job:
        logger.warning(f"Upload requested for non-existent job {job_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Training job {job_id} not found.")

    if job.owner_address.lower() != current_user_address.lower():
        logger.warning(f"User {current_user_address} attempted to upload model for job {job_id} owned by {job.owner_address}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not authorized to perform this action on the specified job.")

    if job.status != "TRAINING_COMPLETE":
        logger.warning(f"Upload requested for job {job_id} with incorrect status: {job.status}")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Job {job_id} is not ready for upload. Current status: {job.status}")

    if not job.temp_model_path or not job.temp_info_path:
        logger.error(f"Job {job_id} is TRAINING_COMPLETE but missing temp file paths.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal error: Training output file paths not found.")

    if not os.path.exists(job.temp_model_path) or not os.path.exists(job.temp_info_path):
        logger.error(f"Job {job_id}: Temporary model/info files not found at expected paths: {job.temp_model_path}, {job.temp_info_path}")
        # This could happen if the temp dir was cleaned up prematurely or server restarted
        job_store.update_job_status(job_id, "FAILED", message="Required temporary files for upload were missing.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Required files for upload not found. The job may have expired or encountered an error.")

    model_cid = None
    model_info_cid = None
    fvm_tx_hash = None
    final_status = "FAILED" # Default to FAILED unless everything succeeds
    final_message = "" # Default message

    try:
        # --- Perform Uploads and Registration ---
        logger.info(f"Job {job_id}: Starting upload process.")
        
        # 1. Upload Model
        logger.info(f"Job {job_id}: Uploading model from {job.temp_model_path}")
        model_cid = lighthouse_service.upload_file(job.temp_model_path)
        if not model_cid:
            final_message = "Failed to upload trained model file."
            logger.error(f"Job {job_id}: {final_message}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=final_message)
        logger.info(f"Job {job_id}: Model uploaded successfully. CID: {model_cid}")

        # 2. Upload Info
        logger.info(f"Job {job_id}: Uploading model info from {job.temp_info_path}")
        model_info_cid = lighthouse_service.upload_file(job.temp_info_path)
        if not model_info_cid:
            final_message = "Failed to upload model metadata file."
            logger.error(f"Job {job_id}: {final_message}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=final_message)
        logger.info(f"Job {job_id}: Model info uploaded successfully. CID: {model_info_cid}")

        # 3. Register Provenance
        logger.info(f"Job {job_id}: Registering provenance on FVM.")
        model_name = upload_request.model_name if upload_request.model_name else f"ML Model from Job {job_id[:8]}"
        
        fvm_tx_hash = fvm_service.register_asset_provenance(
            owner_address=job.owner_address,
            asset_type="Model",
            name=model_name,
            dataset_cid=job.dataset_cid,
            model_cid=model_cid,
            metadata_cid=model_info_cid
        )

        if not fvm_tx_hash:
            # Log warning but consider the operation partially successful (uploads done)
            final_message = "Model and metadata uploaded, but FVM provenance registration failed."
            logger.warning(f"Job {job_id}: {final_message}")
            final_status = "COMPLETED" # Mark as completed, but with warning
        else:
            final_message = "Model uploaded and provenance registered successfully."
            logger.info(f"Job {job_id}: {final_message} Tx: {fvm_tx_hash}")
            final_status = "COMPLETED"

    except HTTPException as http_exc: # Catch specific upload/info failures
        final_status = "UPLOAD_FAILED"
        final_message = final_message or str(http_exc.detail)
        raise http_exc # Re-raise to return the specific error
    except Exception as e:
        final_message = f"An unexpected error occurred during upload/registration: {e}"
        logger.error(f"Job {job_id}: {final_message}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=final_message)
    finally:
        # --- Update Job Status (Final) ---
        # This runs even if exceptions occurred mid-way
        logger.info(f"Job {job_id}: Updating final status to {final_status} with message: {final_message}")
        job_store.update_job_status(
            job_id,
            status=final_status,
            message=final_message,
            model_cid=model_cid,          # Store even if only partially successful
            model_info_cid=model_info_cid,# Store even if only partially successful
            fvm_tx_hash=fvm_tx_hash,      # Store hash if registration succeeded
            temp_model_path=None,       # Clear temp paths as they are likely invalid or uploaded
            temp_info_path=None
        )

        # --- Clean up the specific model and info files --- 
        # This should happen regardless of success/failure of upload/registration,
        # as long as the paths were valid at the start of the endpoint call.
        if job and job.temp_model_path and os.path.exists(job.temp_model_path):
            try:
                os.remove(job.temp_model_path)
                logger.info(f"Job {job_id}: Cleaned up temporary model file: {job.temp_model_path}")
            except Exception as e:
                logger.error(f"Job {job_id}: Error cleaning up model file {job.temp_model_path}: {e}")
        
        if job and job.temp_info_path and os.path.exists(job.temp_info_path):
             try:
                 os.remove(job.temp_info_path)
                 logger.info(f"Job {job_id}: Cleaned up temporary info file: {job.temp_info_path}")
             except Exception as e:
                 logger.error(f"Job {job_id}: Error cleaning up info file {job.temp_info_path}: {e}")
                 
        # Note: The temporary directory itself might still exist if other files were created,
        # or if the original training task failed before creating the dataset path variable.
        # Consider a more robust cleanup strategy for the whole temp directory if needed.

    # If we got here without re-raising an exception, it means COMPLETED (potentially with registration warning)
    return UploadTrainedModelResponse(
        model_cid=model_cid or "", # Should always have value if COMPLETED
        model_info_cid=model_info_cid or "", # Should always have value if COMPLETED
        fvm_tx_hash=fvm_tx_hash, # Can be None if registration failed
        message=final_message
    ) 