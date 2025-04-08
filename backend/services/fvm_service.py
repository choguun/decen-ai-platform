from web3 import Web3
# Remove unused/deprecated middleware import for web3 v6+
# from web3.middleware import geth_poa_middleware
from web3.exceptions import TransactionNotFound
from hexbytes import HexBytes
import json
import logging
import time
import os # For path joining
from typing import Dict, List, Any # Import typing helpers
from datetime import datetime, timezone

from .. import config

logger = logging.getLogger(__name__)

# --- ABI Loading ---
# Calculate path relative to this file's location (backend/services)
_SERVICE_DIR = os.path.dirname(__file__)
_BACKEND_DIR = os.path.abspath(os.path.join(_SERVICE_DIR, os.pardir))
# Adjust path if your contract output is different
_ABI_FILE_PATH = os.path.join(_BACKEND_DIR, os.pardir, "contracts", "out", "ProvenanceLedger.sol", "ProvenanceLedger.json")

CONTRACT_ABI = None
try:
    with open(_ABI_FILE_PATH, 'r') as f:
        # Foundry output contains more than just the ABI, extract it.
        contract_artifact = json.load(f)
        CONTRACT_ABI = contract_artifact.get('abi')
        if CONTRACT_ABI:
            logger.info(f"Successfully loaded contract ABI from: {_ABI_FILE_PATH}")
        else:
             logger.error(f"'abi' key not found in artifact file: {_ABI_FILE_PATH}")
except FileNotFoundError:
    logger.error(f"CRITICAL: Contract ABI file not found at: {_ABI_FILE_PATH}. Contract interactions will fail.")
except json.JSONDecodeError as e:
     logger.error(f"CRITICAL: Failed to parse ABI JSON file {_ABI_FILE_PATH}: {e}")
except Exception as e:
    logger.error(f"CRITICAL: An unexpected error occurred loading ABI from {_ABI_FILE_PATH}: {e}", exc_info=True)

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

# --- Load Contract Instance ---
try:
    # Use the loaded CONTRACT_ABI instead of DEFAULT_CONTRACT_ABI
    if w3 and config.CONTRACT_ADDRESS and CONTRACT_ABI:
        contract = w3.eth.contract(address=Web3.to_checksum_address(config.CONTRACT_ADDRESS), abi=CONTRACT_ABI)
        logger.info(f"Contract instance created for address: {config.CONTRACT_ADDRESS}")
    else:
        contract = None
        if not CONTRACT_ABI:
             logger.error("Cannot create contract instance: ABI not loaded.")
        elif not w3:
             logger.error("Cannot create contract instance: Web3 not connected.")
        elif not config.CONTRACT_ADDRESS:
             logger.error("Cannot create contract instance: CONTRACT_ADDRESS not set.")

except Exception as e:
    logger.error(f"Failed to create contract instance: {e}", exc_info=True)
    contract = None


# --- Service Functions ---

def register_asset_provenance(
    owner_address: str, 
    asset_type: str, # Added asset_type argument
    name: str | None, # Added name argument
    dataset_cid: str | None, 
    model_cid: str | None, 
    metadata_cid: str | None
) -> str | None:
    """Registers asset provenance on the FVM contract by sending a transaction."""
    logger.info(f"Attempting to register provenance: Owner={owner_address}, Type={asset_type}, Name={name}, Dataset={dataset_cid}, Model={model_cid}, Metadata={metadata_cid}")

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
        # Determine primary and related CIDs based on type
        if asset_type == "Dataset":
            primary_asset_cid = dataset_cid or ""
            related_cid = ""
        elif asset_type == "Model":
            primary_asset_cid = model_cid or ""
            related_cid = dataset_cid or "" # Link model back to its source dataset
        else:
            logger.error(f"Unknown asset_type provided: {asset_type}")
            return None
            
        if not primary_asset_cid:
            logger.error(f"Cannot register provenance: Primary asset CID is empty for asset_type {asset_type}.")
            return None
            
        # Ensure None CIDs are empty strings for the contract call
        metadata_cid_str = metadata_cid or ""

        # --- Use provided name or default to empty string --- 
        name_str = name or "" 
        description_str = "" # Keep description as placeholder for now

        # --- (Timestamp and Agent were part of previous incorrect mapping, removed) ---

        # Ensure owner address is checksummed
        checksum_owner_address = Web3.to_checksum_address(owner_address)

        # 1. Get the correct nonce
        nonce = w3.eth.get_transaction_count(account.address)
        logger.info(f"Using nonce {nonce} for transaction from {account.address}")

        # 2. Build the transaction with the CORRECT 7 arguments for ProvenanceLedger.sol
        tx_data = contract.functions.registerAsset(
            checksum_owner_address, # 1. ownerAddress (address)
            asset_type,             # 2. assetType (string)
            name_str,               # 3. name (string) - NOW USES FILENAME
            description_str,        # 4. description (string)
            primary_asset_cid,      # 5. filecoinCid (string)
            metadata_cid_str,       # 6. metadataCid (string)
            related_cid             # 7. sourceAssetCid (string)
        ).build_transaction({
            'chainId': w3.eth.chain_id,
            'gas': 100000000, 
            'gasPrice': w3.eth.gas_price, 
            'nonce': nonce,
            'from': account.address # Sender is the backend wallet
        })
        logger.info("Transaction data built successfully using correct contract signature.")

        # 3. Sign the transaction
        signed_tx = w3.eth.account.sign_transaction(tx_data, private_key=account.key)
        logger.info("Transaction signed successfully.")

        # 4. Send raw transaction
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        tx_hash_hex = tx_hash.hex()
        logger.info(f"Transaction sent! Hash: {tx_hash_hex}")

        # 5. (Optional but Recommended) Wait for transaction receipt
        logger.info("Waiting for transaction receipt...")
        tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120) 

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
        logger.error(f"ValueError during transaction: {ve}", exc_info=True)
        return None
    except Exception as e:
        # Catch potential ABI mismatches specifically if possible
        if "MismatchedABI" in str(type(e)):
             logger.error(f"ABI Mismatch during provenance registration: {e}. Check contract definition and arguments.", exc_info=False)
        else:
             logger.error(f"An unexpected error occurred during provenance registration: {e}", exc_info=True)
        return None


def get_provenance_by_cid(cid: str) -> Dict[str, Any] | None:
    """Queries provenance by a specific CID from the FVM contract."""
    logger.info(f"Querying provenance for CID: {cid}")
    if not w3 or not contract:
        logger.error("Cannot query provenance: Web3 client or contract not initialized.")
        return None

    try:
        # Call the contract's view function
        result_tuple = contract.functions.getAssetByCid(cid).call()
        logger.debug(f"Raw provenance result for CID {cid}: {result_tuple}")

        # --- Validate the returned tuple structure (based on observed logs) ---
        # Expecting at least 8 elements based on logs (9 if boolean is part of struct)
        if not isinstance(result_tuple, (list, tuple)) or len(result_tuple) < 8:
            logger.warning(f"Skipping record for CID {cid} due to unexpected structure or length. Raw tuple: {result_tuple}")
            return None
        
        # --- Extract data based on OBSERVED order --- 
        owner_addr = result_tuple[0]
        timestamp_val = result_tuple[1] # TIMESTAMP IS AT INDEX 1
        asset_type = result_tuple[2]
        name = result_tuple[3] # Not directly needed for Pydantic model
        # description = result_tuple[4] # Not directly needed
        primary_cid_from_contract = result_tuple[5] # The main CID stored
        metadata_cid_from_contract = result_tuple[6]
        source_asset_cid_from_contract = result_tuple[7]

        # --- Validate Owner --- 
        if not isinstance(owner_addr, str) or not owner_addr.startswith('0x') or len(owner_addr) != 42:
            logger.warning(f"Skipping record for CID {cid} due to invalid owner address format. Raw tuple: {result_tuple}")
            return None
        
        if owner_addr == '0x0000000000000000000000000000000000000000':
            logger.info(f"No provenance record found for CID {cid} (owner is zero address).")
            return None 

        # --- Validate and Convert Timestamp (from index 1) --- 
        timestamp_int = None
        if isinstance(timestamp_val, int):
            timestamp_int = timestamp_val
        elif isinstance(timestamp_val, str) and timestamp_val.isdigit():
            try:
                timestamp_int = int(timestamp_val)
            except ValueError:
                logger.warning(f"Skipping record for CID {cid} due to timestamp conversion error (ValueError on index 1). Raw tuple: {result_tuple}")
                return None
        else:
            logger.warning(f"Skipping record for CID {cid} due to invalid non-numeric timestamp format (index 1). Type: {type(timestamp_val)}. Raw tuple: {result_tuple}")
            return None

        # --- Construct the dictionary matching AssetRecord Pydantic model --- 
        if timestamp_int is not None:
             # Map contract results to Pydantic model fields
             # Map contract results to a dictionary structure
             asset_record_data = {
                "owner": owner_addr,
                "timestamp": timestamp_int,
                "assetType": asset_type, # Include assetType
                "name": name or "", # Include name (index 3)
                "filecoinCid": primary_cid_from_contract, # Primary CID (index 5)
                "metadataCid": metadata_cid_from_contract or None, # Index 6
                "sourceAssetCid": source_asset_cid_from_contract or None # Index 7
             }
             # Ensure None for empty strings returned from contract if Pydantic expects None
             # Clean up None values if necessary (though Pydantic handles optional)
             asset_record_data["metadataCid"] = asset_record_data["metadataCid"] or None
             asset_record_data["sourceAssetCid"] = asset_record_data["sourceAssetCid"] or None
             
             logger.info(f"Provenance found and validated for CID {cid}")
             return asset_record_data # Return the detailed dictionary
        else:
            logger.error(f"Timestamp validation passed but timestamp_int is still None for CID {cid}. Logic error?")
            return None

    except Exception as e:
        logger.error(f"Error querying provenance by CID {cid}: {e}", exc_info=True)
        return None

def get_provenance_by_owner(owner_address: str) -> List[Dict[str, Any]] | None:
    """
    Queries provenance records for a specific owner address by fetching
    AssetRegistered events from the blockchain.
    """
    logger.info(f"Querying provenance for owner via events: {owner_address}")
    if not w3 or not contract or not CONTRACT_ABI: # Ensure ABI is loaded
        logger.error("Cannot query provenance events: Web3 client, contract, or ABI not initialized.")
        return None

    all_asset_records = []

    try:
        # Ensure address is checksummed
        checksum_owner = Web3.to_checksum_address(owner_address)

        # --- Calculate reasonable from_block based on lookback limit --- 
        try:
            latest_block = w3.eth.block_number
            # Approx 2880 blocks in 24 hours on Calibration (30s block time)
            # Use a slightly smaller number for safety margin
            lookback_blocks = 2800 
            from_block_val = max(0, latest_block - lookback_blocks) 
            logger.info(f"Querying events from block {from_block_val} (approx last 24 hours)")
        except Exception as block_err:
             logger.warning(f"Could not get latest block number, defaulting from_block to 0. Error: {block_err}")
             from_block_val = 0 # Fallback if block number fetch fails

        # Define event filter parameters
        # Querying from block 0 can be slow on large chains, consider a starting block
        # or storing the last queried block number somewhere.
        # from_block_val = 0 # Use snake_case for variable names too
        event_filter_params = {
            'from_block': from_block_val, # Use calculated recent block
            'to_block': 'latest',        # Use snake_case key
            'argument_filters': {
                'owner': checksum_owner # Filter by indexed owner
            }
        }

        logger.debug(f"Fetching 'AssetRegistered' events with filter: {event_filter_params}")

        # --- Fetch event logs ---
        # Use the contract instance created with the ABI
        event_logs = contract.events.AssetRegistered.get_logs(**event_filter_params)

        logger.info(f"Found {len(event_logs)} 'AssetRegistered' event logs for owner {owner_address}")

        # --- Process logs ---
        for event in event_logs:
            try:
                args = event.args # Arguments from the event
                tx_hash_bytes: HexBytes = event.transactionHash # Get the transaction hash
                tx_hash_hex = tx_hash_bytes.hex()

                # Extract data based on assumed event structure
                # Adjust keys/indices if your event arguments differ
                timestamp_val = args.get('timestamp') # Assuming 'timestamp' key
                asset_type = args.get('assetType', '')
                name = args.get('name', '')
                filecoin_cid = args.get('filecoinCid', '')
                metadata_cid = args.get('metadataCid', None)
                source_asset_cid = args.get('sourceAssetCid', None)
                owner_from_event = args.get('owner', None) # Should match queried owner
                
                # Basic validation
                if owner_from_event != checksum_owner:
                    logger.warning(f"Skipping event log for Tx {tx_hash_hex}: Owner mismatch in event args.")
                    continue
                if not filecoin_cid:
                    logger.warning(f"Skipping event log for Tx {tx_hash_hex}: Missing filecoinCid in event args.")
                    continue

                # Validate and convert timestamp
                timestamp_int = None
                if isinstance(timestamp_val, int):
                    timestamp_int = timestamp_val
                elif isinstance(timestamp_val, str) and timestamp_val.isdigit():
                    timestamp_int = int(timestamp_val)
                else:
                    logger.warning(f"Skipping event log for Tx {tx_hash_hex}: Invalid timestamp format in event args ({type(timestamp_val)}).")
                    continue

                # Construct the record dictionary matching Pydantic model
                asset_record = {
                    "owner": owner_from_event,
                    "assetType": asset_type, # Use the decoded string
                    "name": name,
                    "filecoinCid": filecoin_cid,
                    "metadataCid": metadata_cid or None,
                    "sourceAssetCid": source_asset_cid or None,
                    "timestamp": timestamp_int,
                    "txHash": tx_hash_hex # Include the transaction hash
                }
                all_asset_records.append(asset_record)

            except Exception as e:
                logger.error(f"Error processing event log: {event}. Error: {e}", exc_info=True)
                # Decide whether to skip or stop (skip for now)
                continue

        logger.info(f"Successfully processed {len(all_asset_records)} valid provenance records from events for owner {owner_address}")
        return all_asset_records

    except Exception as e:
        # Handle potential issues with get_logs (e.g., node errors, filter issues)
        logger.error(f"Error querying AssetRegistered events for owner {owner_address}: {e}", exc_info=True)
        return None # Return None on general error during the process
