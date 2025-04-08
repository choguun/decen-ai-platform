import requests
from lighthouseweb3 import Lighthouse
from .. import config
import logging
import os # Import os for checking file existence

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if not config.LIGHTHOUSE_API_KEY:
    # Log error instead of raising immediately, allows app to potentially start
    logger.error("CRITICAL: LIGHTHOUSE_API_KEY not configured in .env. Uploads will fail.")
    # Set lighthouse to None or a mock object if you want to handle this gracefully later
    lighthouse = None
else:
    lighthouse = Lighthouse(token=config.LIGHTHOUSE_API_KEY)

def upload_file(file_path: str) -> str | None:
    """Uploads a file to Lighthouse Storage and returns the CID."""
    if not lighthouse:
        logger.error("Lighthouse client not initialized. Cannot upload.")
        return None
    if not os.path.exists(file_path):
        logger.error(f"File not found for upload: {file_path}")
        return None

    logger.info(f"Attempting to upload {file_path} to Lighthouse...")
    try:
        # Use tag to identify uploads from this app
        result = lighthouse.upload(source=file_path, tag="decen-ai-platform")
        logger.debug(f"Lighthouse upload API response: {result}")

        if result and isinstance(result, dict) and 'data' in result and isinstance(result['data'], dict) and 'Hash' in result['data']:
            cid = result['data']['Hash']
            name = result['data'].get('Name', os.path.basename(file_path))
            size = result['data'].get('Size', 'N/A')
            logger.info(f"Upload successful! CID: {cid}, Name: {name}, Size: {size}")
            return cid
        else:
            logger.error(f"Lighthouse upload failed or returned unexpected format. Response: {result}")
            return None
    except Exception as e:
        logger.error(f"Error during Lighthouse upload of {file_path}: {e}", exc_info=True)
        return None

def download_file(cid: str, output_path: str) -> bool:
    """Downloads a file from Lighthouse Storage gateway using its CID."""
    # Relaxed CID check: Ensure it's a non-empty string.
    # The gateway request will fail if the CID is actually invalid.
    if not cid or not isinstance(cid, str):
        logger.error(f"Invalid or empty CID provided for download: {cid!r}") # Use !r for clearer logging of type/value
        return False

    gateway_url = f"https://gateway.lighthouse.storage/ipfs/{cid}"
    logger.info(f"Attempting to download CID {cid} from {gateway_url} to {output_path}...")

    try:
        # Ensure the output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir:
             os.makedirs(output_dir, exist_ok=True)

        # Make the request
        response = requests.get(gateway_url, stream=True, timeout=300) # stream=True for large files, add timeout
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

        # Write the file
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192): # Download in chunks
                f.write(chunk)

        logger.info(f"Download successful! CID {cid} saved to {output_path}")
        return True

    except requests.exceptions.RequestException as e:
        # More specific error logging
        if isinstance(e, requests.exceptions.HTTPError):
            # This case is already handled by response.raise_for_status(), but good to be explicit
            logger.error(f"HTTP Error {e.response.status_code} downloading CID {cid} from {gateway_url}: {e.response.text}")
        elif isinstance(e, requests.exceptions.ConnectionError):
             logger.error(f"Connection Error downloading CID {cid} from {gateway_url}: {e}", exc_info=True) # Show traceback for connection issues
        elif isinstance(e, requests.exceptions.Timeout):
             logger.error(f"Timeout Error downloading CID {cid} from {gateway_url}: {e}", exc_info=True)
        elif isinstance(e, requests.exceptions.SSLError):
             logger.error(f"SSL Error downloading CID {cid} from {gateway_url}: {e}", exc_info=True) # Show traceback for SSL issues
        else: # Catch-all for other RequestExceptions
            logger.error(f"Network or request error downloading CID {cid} from {gateway_url}: {type(e).__name__} - {e}", exc_info=True)
        return False
    except IOError as e:
        logger.error(f"Error writing downloaded file to {output_path}: {e}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred during download of CID {cid}: {e}", exc_info=True)
        return False
