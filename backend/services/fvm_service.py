from web3 import Web3
# Remove unused/deprecated middleware import for web3 v6+
# from web3.middleware import geth_poa_middleware
from web3.exceptions import TransactionNotFound
from hexbytes import HexBytes
import json
import logging
import time

from .. import config

logger = logging.getLogger(__name__)

# TODO: Add contract ABI (e.g., load from a JSON file)
CONTRACT_ABI = [] # Replace with your actual contract ABI

if not config.FVM_RPC_URL:
    # Log error, but allow app to start potentially
    logger.error("CRITICAL: FVM_RPC_URL not configured in .env. FVM interactions will fail.")
    w3 = None
else:
    w3 = Web3(Web3.HTTPProvider(config.FVM_RPC_URL))
    # Remove middleware injection - web3 v6 handles PoA differently
    # logger.info("Applying geth_poa_middleware for potential PoA network.")
    # w3.middleware_onion.inject(geth_poa_middleware, layer=0)

if w3 and not w3.is_connected():
    logger.error(f"Failed to connect to FVM RPC URL: {config.FVM_RPC_URL}")
    w3 = None # Ensure w3 is None if connection failed
else:
     logger.info(f"Connected to FVM RPC URL: {config.FVM_RPC_URL}")

if not config.CONTRACT_ADDRESS:
    logger.error("CRITICAL: CONTRACT_ADDRESS not configured in .env. Contract interactions will fail.")
    contract = None

if not config.BACKEND_WALLET_PRIVATE_KEY:
    logger.warning("BACKEND_WALLET_PRIVATE_KEY not configured. Cannot sign FVM transactions.")
    account = None
else:
    try:
        account = w3.eth.account.from_key(config.BACKEND_WALLET_PRIVATE_KEY) if w3 else None
        if account:
             w3.eth.default_account = account.address
             logger.info(f"Backend wallet loaded successfully. Address: {account.address}")
    except ValueError as e:
        logger.error(f"Invalid BACKEND_WALLET_PRIVATE_KEY: {e}")
        account = None

# --- Contract ABI (Placeholder) ---
# TODO: Replace with your actual contract ABI - load from a JSON file ideally
# Example ABI structure for the registerAsset function
DEFAULT_CONTRACT_ABI = json.dumps([
    {
        "inputs": [
            {"internalType": "address", "name": "_owner", "type": "address"},
            {"internalType": "string", "name": "_datasetCid", "type": "string"},
            {"internalType": "string", "name": "_modelCid", "type": "string"},
            {"internalType": "string", "name": "_metadataCid", "type": "string"}
        ],
        "name": "registerAsset",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    # TODO: Add ABIs for getAssetByCid and getAssetsByOwner functions
    # Example:
    # {
    #     "inputs": [{"internalType": "string", "name": "_cid", "type": "string"}],
    #     "name": "getAssetByCid",
    #     "outputs": [{"components": [...], "internalType": "struct AssetRecord", "name": "", "type": "tuple"}],
    #     "stateMutability": "view",
    #     "type": "function"
    # },
    # {
    #     "inputs": [{"internalType": "address", "name": "_owner", "type": "address"}],
    #     "name": "getAssetsByOwner",
    #     "outputs": [{"components": [...], "internalType": "struct AssetRecord[]", "name": "", "type": "tuple[]"}],
    #     "stateMutability": "view",
    #     "type": "function"
    # }
])

# --- Load Contract Instance ---
try:
    if w3 and config.CONTRACT_ADDRESS:
        contract = w3.eth.contract(address=Web3.to_checksum_address(config.CONTRACT_ADDRESS), abi=DEFAULT_CONTRACT_ABI)
        logger.info(f"Contract instance created for address: {config.CONTRACT_ADDRESS}")
    else:
        contract = None
except Exception as e:
    logger.error(f"Failed to create contract instance: {e}", exc_info=True)
    contract = None


# --- Service Functions ---

def register_asset_provenance(owner_address: str, dataset_cid: str, model_cid: str, metadata_cid: str) -> str | None:
    """Registers asset provenance on the FVM contract by sending a transaction."""
    logger.info(f"Attempting to register provenance: Owner={owner_address}, Dataset={dataset_cid}, Model={model_cid}, Metadata={metadata_cid}")

    if not w3 or not w3.is_connected():
        logger.error("Cannot register provenance: Web3 client not connected.")
        return None
    if not contract:
        logger.error("Cannot register provenance: Contract not initialized.")
        return None
    if not account:
        logger.error("Cannot register provenance: Backend wallet not configured or loaded.")
        return None

    try:
        # Ensure owner address is checksummed
        checksum_owner_address = Web3.to_checksum_address(owner_address)

        # 1. Get the correct nonce
        nonce = w3.eth.get_transaction_count(account.address)
        logger.info(f"Using nonce {nonce} for transaction from {account.address}")

        # 2. Build the transaction
        # Note: Gas estimation can be tricky on Filecoin. Start with reasonable values
        # or use w3.eth.estimate_gas if it works reliably on your target network.
        tx_data = contract.functions.registerAsset(
            checksum_owner_address,
            dataset_cid,
            model_cid,
            metadata_cid
        ).build_transaction({
            'chainId': w3.eth.chain_id, # Important for replay protection
            'gas': 2000000, # Adjust gas limit as needed (Estimate or set high initially)
            'gasPrice': w3.eth.gas_price, # Use current network gas price
            'nonce': nonce,
            'from': account.address # Specify sender explicitly
        })
        logger.info("Transaction data built successfully.")

        # 3. Sign the transaction
        signed_tx = w3.eth.account.sign_transaction(tx_data, private_key=account.key)
        logger.info("Transaction signed successfully.")

        # 4. Send raw transaction
        tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        tx_hash_hex = tx_hash.hex()
        logger.info(f"Transaction sent! Hash: {tx_hash_hex}")

        # 5. (Optional but Recommended) Wait for transaction receipt
        logger.info("Waiting for transaction receipt...")
        # Add a timeout to avoid waiting indefinitely
        tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120) # Wait up to 120 seconds

        if tx_receipt.status == 1:
            logger.info(f"Transaction successful! Receipt: {tx_receipt}")
            return tx_hash_hex
        else:
            logger.error(f"Transaction failed! Receipt: {tx_receipt}")
            return None # Indicate failure

    except TransactionNotFound:
        logger.error(f"Transaction {tx_hash_hex} not found after timeout. It might still be pending or dropped.")
        return None
    except ValueError as ve:
        # Catch potential issues like insufficient funds, gas errors during build/send
        logger.error(f"ValueError during transaction: {ve}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during provenance registration: {e}", exc_info=True)
        return None


def get_provenance_by_cid(cid: str):
    """Placeholder function to query provenance by CID from the FVM contract."""
    logger.info(f"Querying provenance for CID: {cid}")
    if not w3 or not contract:
        logger.error("Cannot query provenance: Web3 client or contract not initialized.")
        return None
    # TODO: Implement contract.functions.getAssetByCid(cid).call() logic
    # Requires the ABI for getAssetByCid to be added above
    return {"cid": cid, "owner": "0x... (Not Implemented)", "related_assets": []} # Placeholder data

def get_provenance_by_owner(owner_address: str):
    """Placeholder function to query provenance by owner address."""
    logger.info(f"Querying provenance for owner: {owner_address}")
    if not w3 or not contract:
        logger.error("Cannot query provenance: Web3 client or contract not initialized.")
        return None
    # TODO: Implement contract.functions.getAssetsByOwner(owner_address).call() logic
    # Requires the ABI for getAssetsByOwner to be added above
    return [] # Placeholder data
