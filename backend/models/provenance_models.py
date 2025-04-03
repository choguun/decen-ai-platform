from pydantic import BaseModel, Field
from typing import List

class AssetRecord(BaseModel):
    owner: str = Field(..., description="Address of the user who registered the asset.")
    dataset_cid: str | None = Field(None, description="CID of the source dataset.")
    model_cid: str | None = Field(None, description="CID of the trained model.")
    metadata_cid: str | None = Field(None, description="CID of the model metadata.")
    timestamp: int = Field(..., description="Unix timestamp of registration.")

    class Config:
        # Allow creation from non-dict objects if needed (e.g., ORM models in future)
        orm_mode = True

class ProvenanceResponse(BaseModel):
    # For returning a single record
    record: AssetRecord | None = None

class ProvenanceListResponse(BaseModel):
    # For returning multiple records
    records: List[AssetRecord] = [] 