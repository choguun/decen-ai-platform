import os
from dotenv import load_dotenv

load_dotenv()

LIGHTHOUSE_API_KEY = os.getenv("LIGHTHOUSE_API_KEY")
FVM_RPC_URL = os.getenv("FVM_RPC_URL")
BACKEND_WALLET_PRIVATE_KEY = os.getenv("BACKEND_WALLET_PRIVATE_KEY")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")

# Basic validation
if not LIGHTHOUSE_API_KEY:
    print("Warning: LIGHTHOUSE_API_KEY not found in .env file.")
if not FVM_RPC_URL:
    print("Warning: FVM_RPC_URL not found in .env file.")
# Add more checks as needed, especially for private key presence in production 