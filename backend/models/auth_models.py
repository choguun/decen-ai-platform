from pydantic import BaseModel, Field
from typing import Dict, Any

class NonceResponse(BaseModel):
    nonce: str = Field(..., description="Unique nonce for the SIWE message.")

class VerifyRequest(BaseModel):
    message: Dict[str, Any] = Field(..., description="The SIWE message object.")
    signature: str = Field(..., description="The signature provided by the user's wallet.")

class VerifyResponse(BaseModel):
    status: str = "ok"
    address: str = Field(..., description="The verified Ethereum address of the user.")
    # We can add JWT token generation here later if needed for session management
    # token: str | None = None 