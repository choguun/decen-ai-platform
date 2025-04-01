from fastapi import APIRouter, Depends, HTTPException, status
import logging
import tempfile
import os
import joblib
import json
import shutil

from ..services import lighthouse_service, ml_service
from ..models.data_models import InferenceRequest, InferenceResponse, ErrorResponse

router = APIRouter(
    prefix="/inference",
    tags=["Model Inference"],
)

logger = logging.getLogger(__name__)

# Simple cache for loaded models and info (consider a more robust cache like Redis/Memcached for production)
_model_cache = {}
_model_info_cache = {}

def load_model_and_info(model_cid: str, model_info_cid: str | None) -> tuple[Any | None, Dict | None]:
    """Loads model and model_info, using cache if available."""
    # Check cache first
    cached_model = _model_cache.get(model_cid)
    cached_info = _model_info_cache.get(model_info_cid or model_cid) # Use model_cid as key if info_cid missing

    if cached_model and cached_info:
        logger.info(f"Using cached model and info for CID: {model_cid}")
        return cached_model, cached_info

    logger.info(f"Cache miss for model {model_cid}. Downloading...")
    temp_dir = None
    model = None
    model_info = None

    try:
        temp_dir = tempfile.mkdtemp()
        model_path = os.path.join(temp_dir, f"{model_cid}.joblib")
        info_path = os.path.join(temp_dir, f"{model_info_cid or model_cid}.json")

        # Download model
        if not lighthouse_service.download_file(model_cid, model_path):
            logger.error(f"Failed to download model file {model_cid}")
            return None, None

        # Download model info (if CID provided)
        info_cid_to_download = model_info_cid or model_info.get('model_info_cid') # Need a reliable way to get info_cid if not provided
        if info_cid_to_download:
             if not lighthouse_service.download_file(info_cid_to_download, info_path):
                logger.warning(f"Failed to download model info file {info_cid_to_download}. Inference might fail if features not embedded.")
                # Continue without info, prediction might still work if model is self-contained
             else:
                 with open(info_path, 'r') as f:
                    model_info = json.load(f)
        else:
            logger.warning(f"Model info CID not provided for model {model_cid}. Required for feature validation.")
            # Attempt to load model anyway, but it might fail later

        # Load model from file
        model = joblib.load(model_path)

        # Update cache
        _model_cache[model_cid] = model
        if model_info:
            _model_info_cache[model_info_cid or model_cid] = model_info

        return model, model_info

    except Exception as e:
        logger.error(f"Error loading model/info for CID {model_cid}: {e}", exc_info=True)
        return None, None
    finally:
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                logger.error(f"Error cleaning up temp dir {temp_dir} during model load: {e}")

@router.post(
    "/predict",
    response_model=InferenceResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse}
    }
)
def predict(
    inference_request: InferenceRequest,
    # TODO: Add auth dependency
):
    """
    Performs inference using a specified model CID and input data.

    Downloads the model (and optionally metadata) from Lighthouse,
    loads it, and makes a prediction based on the provided input features.

    - **model_cid**: CID of the model to use.
    - **input_data**: Dictionary of feature names and values.
    - **model_info_cid** (optional): CID of the metadata file if needed.
    """
    logger.info(f"Received inference request for model CID: {inference_request.model_cid}")

    # Load model and info (handles caching and downloading)
    model, model_info = load_model_and_info(inference_request.model_cid, inference_request.model_info_cid)

    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model not found or failed to load for CID: {inference_request.model_cid}"
        )

    # Model info is crucial for knowing feature names/order
    if not model_info:
         raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Model metadata (containing feature list) is required for inference but was not found or failed to load. Provide model_info_cid."
        )

    # Perform prediction using the service
    prediction_result = ml_service.predict_with_model(
        model=model,
        model_info=model_info,
        input_data=inference_request.input_data
    )

    if prediction_result is None:
        # Error logged within the service function
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Prediction failed. Check server logs for details."
        )

    return InferenceResponse(
        prediction=prediction_result["prediction"],
        probabilities=prediction_result["probabilities"],
        model_cid=inference_request.model_cid
    ) 