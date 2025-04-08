from fastapi import APIRouter, HTTPException, status, Request, Depends
from fastapi.security import OAuth2PasswordBearer # For JWT extraction
from siwe import SiweMessage, generate_nonce
from datetime import datetime, timedelta, timezone # Added timezone
from jose import JWTError, jwt # For JWT handling
from pydantic import BaseModel, ValidationError # For token payload validation
import logging

from ..models.auth_models import NonceResponse, VerifyRequest, VerifyResponse
from ..models.data_models import ErrorResponse
from .. import config # Import config for JWT settings

# --- JWT Configuration ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token") # Dummy URL, we use /verify

# --- Token Payload Model ---
class TokenData(BaseModel):
    sub: str # Subject (typically the user identifier, e.g., address)
    # Add other claims like roles if needed

# In-memory store for nonces (replace with Redis/DB in production)
_nonce_store: dict[str, datetime] = {}
NONCE_EXPIRATION_SECONDS = 300

router = APIRouter(
    prefix="/auth",
    tags=["Authentication (SIWE)"],
)

logger = logging.getLogger(__name__)

# --- Helper Functions ---
def cleanup_expired_nonces():
    """Removes expired nonces from the store."""
    now = datetime.now(timezone.utc) # Use timezone-aware datetime
    expired_keys = [
        key for key, timestamp in _nonce_store.items()
        if (now - timestamp).total_seconds() > NONCE_EXPIRATION_SECONDS
    ]
    for key in expired_keys:
        try:
            del _nonce_store[key]
            logger.debug(f"Expired nonce removed: {key}")
        except KeyError:
            pass

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Creates a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # Default expiry from config
        expire = datetime.now(timezone.utc) + timedelta(minutes=config.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM)
    return encoded_jwt

# --- API Endpoints ---
@router.get("/nonce", response_model=NonceResponse)
def get_nonce():
    """
    Generates a unique nonce for the client to use in the SIWE message.
    """
    cleanup_expired_nonces()
    nonce = generate_nonce()
    _nonce_store[nonce] = datetime.now(timezone.utc) # Use timezone-aware datetime
    logger.info(f"Generated nonce: {nonce}")
    return NonceResponse(nonce=nonce)

@router.post(
    "/verify",
    response_model=VerifyResponse,
    responses={status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}}
)
def verify_signature(verify_request: VerifyRequest, request: Request):
    """
    Verifies a SIWE message signature and returns a JWT access token upon success.

    Checks message structure, signature, domain, and nonce.
    If successful, generates a JWT containing the user's address.

    - **message**: The structured SIWE message signed by the user.
    - **signature**: The hex-encoded signature string.
    """
    try:
        # Parse the message by creating SiweMessage from the dictionary
        # Unpack the dictionary received in verify_request.message
        siwe_message = SiweMessage(**verify_request.message)
        
        # Verify the signature against the constructed message object.
        # The nonce/domain/etc. are part of the siwe_message object now.
        siwe_message.verify(verify_request.signature)
        
        logger.info(f"SIWE signature verified successfully for address: {siwe_message.address}")

        # --- Nonce Validation --- 
        # Check if nonce exists in our store and is not expired
        now = datetime.now(timezone.utc) # Use timezone-aware
        nonce_creation_time = _nonce_store.get(siwe_message.nonce)
        
        if not nonce_creation_time:
            logger.warning(f"SIWE nonce not found or already used: {siwe_message.nonce}")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired nonce.")

        if (now - nonce_creation_time).total_seconds() > NONCE_EXPIRATION_SECONDS:
            logger.warning(f"SIWE nonce expired: {siwe_message.nonce}")
            try: del _nonce_store[siwe_message.nonce]
            except KeyError: pass
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Expired nonce.")
        
        # --- Domain Validation --- 
        # Compare against the expected frontend domain from config
        expected_domain = config.EXPECTED_FRONTEND_DOMAIN # Assumes this exists in config
        
        if not expected_domain:
            # Configuration error
            logger.error("Missing EXPECTED_FRONTEND_DOMAIN configuration.")
            # Don't expose config details, raise a generic internal error
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Server configuration error.")
        
        if siwe_message.domain != expected_domain:
             logger.warning(f"SIWE domain mismatch: Expected '{expected_domain}', Got '{siwe_message.domain}'")
             raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Domain mismatch. Signature is not valid for this application.") # More generic error message

        # --- Consume Nonce --- 
        try:
            del _nonce_store[siwe_message.nonce]
            logger.info(f"Nonce consumed: {siwe_message.nonce}")
        except KeyError:
             logger.error(f"Attempted to consume nonce {siwe_message.nonce} that was already removed.")
             raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nonce already used.")

        # --- Verification Successful - Generate JWT ---
        access_token_expires = timedelta(minutes=config.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": siwe_message.address}, expires_delta=access_token_expires
        )
        logger.info(f"JWT generated successfully for address: {siwe_message.address}")

        return VerifyResponse(
            address=siwe_message.address,
            access_token=access_token,
            token_type="bearer" # Included via model default
        )

    except ValueError as ve:
        logger.warning(f"SIWE verification failed (ValueError): {ve}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Signature verification failed: {ve}")
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Unexpected error during SIWE verification: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred during verification.")


# --- Secure Dependency for Authenticated User ---
async def get_current_active_user(token: str = Depends(oauth2_scheme)) -> str:
    """
    Dependency that verifies the JWT token from the Authorization header
    and returns the user's address (subject of the token).
    Raises HTTPException 401 if the token is invalid or expired.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, config.JWT_SECRET_KEY, algorithms=[config.JWT_ALGORITHM]
        )
        # Extract the address from the 'sub' claim
        address: str | None = payload.get("sub")
        if address is None:
            logger.warning("Token payload missing 'sub' (address) claim.")
            raise credentials_exception

        # Validate payload structure (optional but good practice)
        token_data = TokenData(sub=address)

    except JWTError as e:
        logger.warning(f"JWT Error during token decoding: {e}")
        raise credentials_exception
    except ValidationError as e:
         logger.warning(f"JWT payload validation error: {e}")
         raise credentials_exception

    # TODO: Could add extra checks here, e.g., check if user is active in a DB

    # Return the address (user identifier)
    return token_data.sub


# --- REMOVE THE INSECURE PLACEHOLDER ---
# async def get_current_user_address_insecure(request: Request) -> str:
#     ... (Removed) ...

# --- Dependency for authenticated user (Example) ---
# This part would typically involve session tokens (JWT) generated after successful verify
# For now, we'll create a placeholder dependency that expects the address in a header
# (THIS IS NOT SECURE FOR PRODUCTION - REPLACE WITH TOKEN-BASED AUTH)
# async def get_current_user_address_insecure(request: Request) -> str:
#     """Placeholder dependency: Gets address from a header (INSECURE - FOR DEMO ONLY)."""
#     user_address = request.headers.get("X-User-Address")
#     if not user_address:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Not authenticated (Missing X-User-Address header - demo only)"
#         )
#     # TODO: Add address validation (e.g., using web3.is_address)
#     return user_address 