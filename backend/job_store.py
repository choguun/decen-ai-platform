# backend/job_store.py

import logging
from datetime import datetime, timezone
from typing import Dict, Any

from .models.data_models import TrainingStatusResponse # Assuming data_models is in the parent dir

logger = logging.getLogger(__name__)

# --- In-Memory Job Store (Basic Example) ---
# Stores job_id -> TrainingStatusResponse object
# WARNING: This is lost on server restart! Consider a persistent store (e.g., Redis, DB) for production.
_training_jobs: Dict[str, TrainingStatusResponse] = {}

def get_job(job_id: str) -> TrainingStatusResponse | None:
    """Retrieve a job from the store by its ID."""
    return _training_jobs.get(job_id)

def store_job(job: TrainingStatusResponse):
    """Store or update a job in the store."""
    if not job or not job.job_id:
        logger.error("Attempted to store an invalid job object.")
        return
    _training_jobs[job.job_id] = job
    logger.debug(f"Stored/Updated job {job.job_id}")

def update_job_status(job_id: str, status: str, message: str | None = None, **kwargs):
    """Helper to update the status and other attributes of a job in the store."""
    job = get_job(job_id)
    if job:
        job.status = status
        job.message = message
        job.updated_at = datetime.now(timezone.utc)
        # Update result fields if provided
        for key, value in kwargs.items():
            if hasattr(job, key):
                setattr(job, key, value)
            else:
                 logger.warning(f"Job {job_id}: Attempted to set unknown attribute '{key}' during status update.")
        # Re-store the updated job object
        store_job(job)
        logger.info(f"Updated job {job_id} status to {status} (kwargs: {list(kwargs.keys())})")
    else:
        logger.warning(f"Attempted to update status for unknown job_id: {job_id}") 