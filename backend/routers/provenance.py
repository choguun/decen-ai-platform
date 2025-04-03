from fastapi import APIRouter, Depends, HTTPException, status
import logging

from ..services import fvm_service
from ..models.provenance_models import ProvenanceResponse, ProvenanceListResponse, AssetRecord
from ..models.data_models import ErrorResponse # Shared error model
from ..routers.auth import get_current_active_user # Auth dependency

router = APIRouter(
    prefix="/provenance",
    tags=["Provenance Querying"],
)

logger = logging.getLogger(__name__)

@router.get(
    "/cid/{cid}",
    response_model=ProvenanceResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse}
    }
)
def get_provenance_record_by_cid(cid: str):
    """
    Retrieves a single provenance asset record by its associated CID
    (dataset, model, or metadata).
    """
    logger.info(f"Received request to get provenance for CID: {cid}")
    record_data = fvm_service.get_provenance_by_cid(cid)

    if record_data is None:
        # Could be not found or an error during query
        # FVM service logs the error, so we can assume not found here for the client
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provenance record not found for CID: {cid}"
        )

    # Validate and structure the response using Pydantic model
    try:
        asset_record = AssetRecord(**record_data)
        return ProvenanceResponse(record=asset_record)
    except Exception as e:
        logger.error(f"Failed to parse provenance data for CID {cid}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process provenance data from FVM."
        )

@router.get(
    "/owner/{owner_address}",
    response_model=ProvenanceListResponse,
    responses={status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse}}
)
def get_provenance_records_by_owner(owner_address: str):
    """
    Retrieves all provenance asset records registered by a specific owner address.
    """
    logger.info(f"Received request to get provenance for owner: {owner_address}")
    records_data = fvm_service.get_provenance_by_owner(owner_address)

    if records_data is None:
        # Indicates an error during the FVM query
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query provenance records for owner: {owner_address}"
        )

    # Validate and structure the response
    try:
        validated_records = [AssetRecord(**record) for record in records_data]
        return ProvenanceListResponse(records=validated_records)
    except Exception as e:
        logger.error(f"Failed to parse provenance data for owner {owner_address}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process provenance data list from FVM."
        )

@router.get(
    "/mine",
    response_model=ProvenanceListResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse}
    }
)
def get_my_provenance_records(
    current_user_address: str = Depends(get_current_active_user)
):
    """
    Retrieves all provenance asset records registered by the currently
    authenticated user (based on JWT).
    Requires authentication.
    """
    logger.info(f"Received request to get provenance for current user: {current_user_address}")
    # Reuse the existing function, passing the authenticated user's address
    return get_provenance_records_by_owner(current_user_address) 