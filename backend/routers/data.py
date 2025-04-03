from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, status
from fastapi.responses import JSONResponse
import tempfile
import os
import logging

from ..services import lighthouse_service
from ..models.data_models import UploadResponse, ErrorResponse
from ..routers.auth import get_current_active_user

router = APIRouter(
    prefix="/data",
    tags=["Data Management"],
)

logger = logging.getLogger(__name__)

@router.post(
    "/upload/dataset",
    response_model=UploadResponse,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}
    }
)
def upload_dataset(
    file: UploadFile = File(...),
    current_user_address: str = Depends(get_current_active_user)
):
    """
    Uploads a dataset file (e.g., CSV) to Lighthouse storage.
    Requires authentication via JWT bearer token.

    - **file**: The dataset file to upload.
    """
    logger.info(f"Authenticated user {current_user_address} uploading dataset: {file.filename}")

    # Use a temporary directory for secure handling
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_file_path = os.path.join(temp_dir, file.filename)
        try:
            # Save the uploaded file temporarily
            with open(temp_file_path, "wb") as buffer:
                buffer.write(file.file.read())
            logger.info(f"Temporarily saved uploaded file to: {temp_file_path}")

            # Upload to Lighthouse
            cid = lighthouse_service.upload_file(temp_file_path)

            if cid:
                logger.info(f"Dataset {file.filename} uploaded successfully. CID: {cid}")
                return UploadResponse(
                    filename=file.filename,
                    content_type=file.content_type,
                    cid=cid
                )
            else:
                logger.error(f"Failed to upload dataset {file.filename} to Lighthouse.")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to upload file to decentralized storage."
                )

        except HTTPException as http_exc:
            # Re-raise HTTPExceptions directly
            raise http_exc
        except Exception as e:
            logger.error(f"Error processing dataset upload for {file.filename}: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An unexpected error occurred: {e}"
            )
        finally:
            # Ensure temporary file is cleaned up (though TemporaryDirectory handles it)
            if os.path.exists(temp_file_path):
                # Optional: log cleanup if needed
                pass

# TODO: Add endpoint for uploading models (similar structure)
# TODO: Add endpoints for querying/listing datasets/models (will likely involve FVM interaction)

# TODO: Apply the same `Depends` pattern to other protected endpoints
# (model upload, training start, inference, provenance queries needing user context) 