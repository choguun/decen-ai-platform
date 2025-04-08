from pydantic import BaseModel, Field
from typing import List

class AssetRecord(BaseModel):
    owner: str = Field(..., description="Address of the user who registered the asset.")
    assetType: str = Field(..., description="Type of the asset (e.g., 'Dataset', 'Model').")
    name: str = Field(..., description="Name of the asset (e.g., filename).")
    filecoinCid: str = Field(..., description="Primary Filecoin CID of the asset.")
    metadataCid: str | None = Field(None, description="CID of the associated metadata.")
    sourceAssetCid: str | None = Field(None, description="CID of the source asset (e.g., dataset for a model).")
    timestamp: int = Field(..., description="Unix timestamp of registration.")
    txHash: str = Field(..., description="Transaction hash of the registration event.")

    # Remove orm_mode if not using ORM
    # class Config:
    #     orm_mode = True

class ProvenanceResponse(BaseModel):
    # For returning a single record
    record: AssetRecord | None = None

class ProvenanceListResponse(BaseModel):
    # For returning multiple records
    records: List[AssetRecord] = [] 