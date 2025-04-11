from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from datetime import datetime

class UploadResponse(BaseModel):
    filename: str
    content_type: str
    cid: str = Field(..., description="Content Identifier (CID) of the uploaded file on Lighthouse/IPFS")
    message: str = "File uploaded successfully"

class ErrorResponse(BaseModel):
    detail: str 

class TrainRequest(BaseModel):
    dataset_cid: str = Field(..., description="CID of the dataset file on Lighthouse/IPFS to be used for training.")
    model_type: str = Field(..., description="Type of the ML model to train (e.g., RandomForest, XGBoost).")
    target_column: str = Field(..., description="Name of the target variable column in the dataset.")
    hyperparameters: Dict[str, Any] = Field({}, description="Hyperparameters for the model as a JSON object.") # Default to empty dict
    # Add other potential training parameters here later if needed
    # e.g., model_type: str = "RandomForestClassifier"
    # e.g., hyperparameters: Dict[str, Any] = None

class TrainResponse(BaseModel):
    job_id: str = Field(..., description="Unique ID for the background training job.")
    message: str = "Training job initiated successfully. Check status later."
    dataset_cid: str
    # These fields are now part of the status response, not immediate response
    # model_cid: str = Field(..., description="CID of the trained model file (.joblib)")
    # model_info_cid: str = Field(..., description="CID of the model metadata file (.json)")
    # accuracy: Optional[float] = Field(None, description="Accuracy achieved on the test set during training.")
    # fvm_tx_hash: Optional[str] = Field(None, description="Transaction hash for provenance registration on FVM.")

# Add model for status reporting
class TrainingStatusResponse(BaseModel):
    job_id: str
    status: str = Field(..., description="Current status (e.g., PENDING, DOWNLOADING, TRAINING, TRAINING_COMPLETE, UPLOADING, REGISTERING, COMPLETED, FAILED)")
    message: Optional[str] = Field(None, description="Optional message, e.g., error details.")
    dataset_cid: str
    owner_address: str
    # Results available when status is TRAINING_COMPLETE or COMPLETED
    model_cid: Optional[str] = None
    model_info_cid: Optional[str] = None
    accuracy: Optional[float] = None
    fvm_tx_hash: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # --- Add fields to store temporary results --- 
    temp_model_path: Optional[str] = None # Store path to .joblib file
    temp_info_path: Optional[str] = None # Store path to .json file

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

# --- Models for the new Upload endpoint --- 
class UploadTrainedModelRequest(BaseModel):
    model_name: Optional[str] = Field(None, description="Optional name to use for the model registration.")

class UploadTrainedModelResponse(BaseModel):
    model_cid: str
    model_info_cid: str
    fvm_tx_hash: Optional[str] = None # FVM hash might be None if registration fails
    message: str = "Model uploaded and provenance registered successfully." 