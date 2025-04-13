import os
from dotenv import load_dotenv

load_dotenv()

LIGHTHOUSE_API_KEY = os.getenv("LIGHTHOUSE_API_KEY")
FVM_RPC_URL = os.getenv("FVM_RPC_URL")
BACKEND_WALLET_PRIVATE_KEY = os.getenv("BACKEND_WALLET_PRIVATE_KEY")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")

# Expected Frontend Origin (for SIWE domain validation)
EXPECTED_FRONTEND_DOMAIN = os.getenv("EXPECTED_FRONTEND_DOMAIN", "localhost:3000") # Default to localhost:3000 for dev

# JWT Settings
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 30))

# --- Service Fees (in Wei) --- 
# Load as string and convert to int, defaulting to 0 if not set or invalid
try:
    TRAINING_SERVICE_FEE = int(os.getenv("TRAINING_SERVICE_FEE", "0"))
except ValueError:
    print("Warning: Invalid TRAINING_SERVICE_FEE in .env file. Defaulting to 0.")
    TRAINING_SERVICE_FEE = 0

try:
    INFERENCE_SERVICE_FEE = int(os.getenv("INFERENCE_SERVICE_FEE", "0"))
except ValueError:
    print("Warning: Invalid INFERENCE_SERVICE_FEE in .env file. Defaulting to 0.")
    INFERENCE_SERVICE_FEE = 0

# Basic validation
if not LIGHTHOUSE_API_KEY:
    print("Warning: LIGHTHOUSE_API_KEY not found in .env file.")
if not FVM_RPC_URL:
    print("Warning: FVM_RPC_URL not found in .env file.")
if not JWT_SECRET_KEY:
    print("Warning: JWT_SECRET_KEY not found in .env file. Authentication will fail.")
# Add more checks as needed, especially for private key presence in production 