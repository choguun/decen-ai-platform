from fastapi import APIRouter, HTTPException, status, Request, Depends
from siwe import SiweMessage, generate_nonce
from datetime import datetime
import logging

from ..models.auth_models import NonceResponse, VerifyRequest, VerifyResponse
from ..models.data_models import ErrorResponse # For error responses

# In-memory store for nonces (replace with Redis/DB in production for scalability and persistence)
# Stores nonce -> generated_time
_nonce_store: dict[str, datetime] = {}
NONCE_EXPIRATION_SECONDS = 300 # Nonces expire after 5 minutes

router = APIRouter(
    prefix="/auth",
    tags=["Authentication (SIWE)"],
)

logger = logging.getLogger(__name__)

def cleanup_expired_nonces():
    """Removes expired nonces from the store."""
    now = datetime.now()
    expired_keys = [
        key for key, timestamp in _nonce_store.items()
        if (now - timestamp).total_seconds() > NONCE_EXPIRATION_SECONDS
    ]
    for key in expired_keys:
        try:
            del _nonce_store[key]
            logger.debug(f"Expired nonce removed: {key}")
        except KeyError:
            pass # Already removed by another process/thread

@router.get("/nonce", response_model=NonceResponse)
def get_nonce():
    """
    Generates a unique nonce for the client to use in the SIWE message.
    """
    cleanup_expired_nonces() # Clean up before generating
    nonce = generate_nonce()
    _nonce_store[nonce] = datetime.now()
    logger.info(f"Generated nonce: {nonce}")
    return NonceResponse(nonce=nonce)

@router.post(
    "/verify",
    response_model=VerifyResponse,
    responses={status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}}
)
def verify_signature(verify_request: VerifyRequest, request: Request):
    """
    Verifies a SIWE message signature.

    Checks the message structure, signature validity, domain, and nonce.
    If successful, it implicitly authenticates the user for the scope of this request.
    (Future enhancement: generate a session token/JWT).

    - **message**: The structured SIWE message signed by the user.
    - **signature**: The hex-encoded signature string.
    """
    try:
        siwe_message = SiweMessage(message=verify_request.message)

        # --- Security Checks ---
        # 1. Verify signature and message structure
        # This also checks basic message fields like address format
        siwe_message.verify(verify_request.signature)
        logger.info(f"SIWE signature verified successfully for address: {siwe_message.address}")

        # 2. Check domain binding (should match the frontend domain)
        # TODO: Get expected domain from config/env
        expected_domain = request.url.hostname # Use request hostname for now
        if siwe_message.domain != expected_domain:
             logger.warning(f"SIWE domain mismatch: Expected {expected_domain}, Got {siwe_message.domain}")
             raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Domain mismatch. Expected {expected_domain}"
             )

        # 3. Check nonce validity and expiration
        now = datetime.now()
        nonce_creation_time = _nonce_store.get(siwe_message.nonce)
        if not nonce_creation_time:
            logger.warning(f"SIWE nonce not found or already used: {siwe_message.nonce}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired nonce."
            )

        if (now - nonce_creation_time).total_seconds() > NONCE_EXPIRATION_SECONDS:
            logger.warning(f"SIWE nonce expired: {siwe_message.nonce}")
            # Clean up expired nonce immediately
            try:
                del _nonce_store[siwe_message.nonce]
            except KeyError:
                pass
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Expired nonce."
            )

        # 4. Consume nonce (prevent replay attacks)
        try:
            del _nonce_store[siwe_message.nonce]
            logger.info(f"Nonce consumed: {siwe_message.nonce}")
        except KeyError:
             # Should not happen if check above passed, but handle defensively
             logger.error(f"Attempted to consume nonce {siwe_message.nonce} that was already removed.")
             raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Nonce already used."
            )

        # TODO: Check issued_at / expiration_time fields in message if needed

        # --- Verification Successful ---
        # At this point, the user address (siwe_message.address) is authenticated.
        # For simple use cases, we can just return the address.
        # For persistent sessions, generate and return a JWT here.
        logger.info(f"SIWE verification successful for address: {siwe_message.address}")
        return VerifyResponse(address=siwe_message.address)

    except ValueError as ve:
        # siwe-py raises ValueError for signature/message issues
        logger.warning(f"SIWE verification failed (ValueError): {ve}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Signature verification failed: {ve}"
        )
    except HTTPException as http_exc:
        # Re-raise specific HTTPExceptions from checks above
        raise http_exc
    except Exception as e:
        # Catch-all for unexpected errors
        logger.error(f"Unexpected error during SIWE verification: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred during verification."
        )

# --- Dependency for authenticated user (Example) ---
# This part would typically involve session tokens (JWT) generated after successful verify
# For now, we'll create a placeholder dependency that expects the address in a header
# (THIS IS NOT SECURE FOR PRODUCTION - REPLACE WITH TOKEN-BASED AUTH)
async def get_current_user_address_insecure(request: Request) -> str:
    """Placeholder dependency: Gets address from a header (INSECURE - FOR DEMO ONLY)."""
    user_address = request.headers.get("X-User-Address")
    if not user_address:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated (Missing X-User-Address header - demo only)"
        )
    # TODO: Add address validation (e.g., using web3.is_address)
    return user_address 