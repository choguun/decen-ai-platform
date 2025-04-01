from pydantic import BaseModel, Field
from typing import Dict, Any, Optional

class UploadResponse(BaseModel):
    filename: str
    content_type: str
    cid: str = Field(..., description="Content Identifier (CID) of the uploaded file on Lighthouse/IPFS")
    message: str = "File uploaded successfully"

class ErrorResponse(BaseModel):
    detail: str 

class TrainRequest(BaseModel):
    dataset_cid: str = Field(..., description="CID of the dataset file on Lighthouse/IPFS to be used for training.")
    # Add other potential training parameters here later if needed
    # e.g., model_type: str = "RandomForestClassifier"
    # e.g., hyperparameters: Dict[str, Any] = None

class TrainResponse(BaseModel):
    message: str = "Training job initiated successfully"
    dataset_cid: str
    model_cid: str = Field(..., description="CID of the trained model file (.joblib)")
    model_info_cid: str = Field(..., description="CID of the model metadata file (.json)")
    accuracy: Optional[float] = Field(None, description="Accuracy achieved on the test set during training.")
    fvm_tx_hash: Optional[str] = Field(None, description="Transaction hash for provenance registration on FVM.")

class InferenceRequest(BaseModel):
    model_cid: str = Field(..., description="CID of the trained model (.joblib) to use for inference.")
    # We expect input data as a flat dictionary matching model features
    input_data: Dict[str, Any] = Field(..., description="Input features for prediction as a key-value map.")
    # Optional: CID for model info if needed and not implicitly linked
    model_info_cid: Optional[str] = Field(None, description="Optional CID of the model metadata file (.json). Required if features aren't stored with model.")

class InferenceResponse(BaseModel):
    prediction: Any = Field(..., description="The prediction result from the model.")
    probabilities: Optional[Dict[str, float]] = Field(None, description="Prediction probabilities for each class (if available).")
    model_cid: str
    # Optional: include input_data in response? Can be large.
    # input_data: Dict[str, Any] 