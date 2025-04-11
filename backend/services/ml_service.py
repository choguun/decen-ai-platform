import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
import xgboost as xgb
from sklearn.metrics import accuracy_score
import joblib
import os
import json
import logging
import tempfile
from typing import Tuple, Dict, Any, Optional

logger = logging.getLogger(__name__)

def train_model_on_dataset(
    dataset_path: str,
    output_dir: str,
    model_type: str,
    target_column: str,
    hyperparameters: Dict[str, Any]
) -> Tuple[Any, Dict[str, Any], str, str] | Tuple[None, None, None, None]:
    """
    Trains a specified ML model on the dataset using provided parameters.
    Saves the trained model (.joblib) and metadata (.json) to the specified output directory.

    Args:
        dataset_path: The file path to the dataset (e.g., CSV).
        output_dir: The directory path where the model and info files will be saved.
        model_type: String identifier for the model (e.g., "RandomForest", "XGBoost").
        target_column: The name of the column to predict.
        hyperparameters: Dictionary of hyperparameters for the model.

    Returns:
        A tuple containing:
        - The trained model object.
        - A dictionary containing model metadata (accuracy, features, etc.).
        - The file path to the saved model (.joblib).
        - The file path to the saved model info (.json).
        Returns (None, None, None, None) if training fails.
    """
    logger.info(f"Starting model training. Dataset: {dataset_path}, Model: {model_type}, Target: {target_column}, Params: {hyperparameters}")
    try:
        # Load the dataset
        df = pd.read_csv(dataset_path)
        logger.info(f"Dataset loaded successfully. Shape: {df.shape}")

        # --- Validate Target Column --- 
        if target_column not in df.columns:
            logger.error(f"Target column '{target_column}' not found in the dataset columns: {list(df.columns)}")
            return None, None, None, None

        # --- Separate features (X) and target (y) --- 
        X = df.drop(target_column, axis=1)
        y = df[target_column]
        
        # --- Preprocessing: Handle Categorical Features using One-Hot Encoding --- 
        categorical_cols = X.select_dtypes(include=['object', 'category']).columns
        if not categorical_cols.empty:
            logger.info(f"Applying one-hot encoding to categorical columns: {list(categorical_cols)}")
            X = pd.get_dummies(X, columns=list(categorical_cols), drop_first=True) # drop_first avoids multicollinearity
            logger.info(f"Data shape after one-hot encoding: {X.shape}")
        else:
             logger.info("No categorical columns found requiring one-hot encoding.")

        # Get feature names *after* potential encoding
        feature_names = list(X.columns)

        # --- Split into training and testing sets --- 
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42) # Use processed X
        logger.info(f"Data split into training ({len(X_train)} samples) and testing ({len(X_test)} samples).")

        # --- Model Selection and Initialization --- 
        model = None
        sanitized_hyperparams = hyperparameters.copy()
        
        # Ensure random_state is passed if needed and present
        if 'random_state' not in sanitized_hyperparams:
            sanitized_hyperparams['random_state'] = 42 # Default random state
            
        try:
            if model_type == "RandomForest":
                # Only pass relevant params to avoid errors
                valid_rf_params = {k: v for k, v in sanitized_hyperparams.items() if k in RandomForestClassifier().get_params()}
                model = RandomForestClassifier(**valid_rf_params)
                logger.info(f"Initializing RandomForestClassifier with params: {valid_rf_params}")
            elif model_type == "XGBoost":
                 # XGBoost specific handling (e.g., label encoding if needed)
                 # Note: XGBoost might need target labels to be 0, 1, ...
                 # Add preprocessing here if necessary based on y_train
                 
                 # Only pass relevant params
                 valid_xgb_params = {k: v for k, v in sanitized_hyperparams.items() if k in xgb.XGBClassifier().get_params()}
                 # Handle potential objective incompatibility if passed in params
                 if 'objective' not in valid_xgb_params:
                      # Infer objective based on target type (simplistic example)
                      if len(y_train.unique()) == 2:
                           valid_xgb_params['objective'] = 'binary:logistic'
                      else:
                           valid_xgb_params['objective'] = 'multi:softprob' # Or other appropriate objective
                 
                 model = xgb.XGBClassifier(**valid_xgb_params)
                 logger.info(f"Initializing XGBClassifier with params: {valid_xgb_params}")
            elif model_type == "LogisticRegression":
                 # Only pass relevant params
                 valid_lr_params = {k: v for k, v in sanitized_hyperparams.items() if k in LogisticRegression().get_params()}
                 model = LogisticRegression(**valid_lr_params)
                 logger.info(f"Initializing LogisticRegression with params: {valid_lr_params}")
            else:
                logger.error(f"Unsupported model_type: {model_type}")
                return None, None, None, None
                
        except TypeError as te:
             logger.error(f"Invalid hyperparameter provided for model type {model_type}. Error: {te}", exc_info=True)
             return None, None, None, None

        # --- Train the selected model --- 
        model.fit(X_train, y_train)
        logger.info(f"{model_type} model trained successfully.")

        # --- Evaluate the model --- 
        y_pred = model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        logger.info(f"Model evaluation completed. Accuracy: {accuracy:.4f}")

        # --- Create model info dictionary --- 
        model_info = {
            "model_type": model_type, # Store actual model type used
            "hyperparameters_used": sanitized_hyperparams, # Store parameters used
            "features": feature_names,
            "target_column": target_column, # Store actual target column used
            "accuracy": float(accuracy),
            "training_samples": int(len(X_train)),
            "test_samples": int(len(X_test)),
            # Remove dataset_source_path if not needed downstream
            # "dataset_source_path": dataset_path 
        }

        # --- Save model and info to the specified output directory --- 
        os.makedirs(output_dir, exist_ok=True) # Ensure the output directory exists
        model_filename = "trained_model.joblib"
        info_filename = "model_info.json"

        # Construct full paths within the output directory
        model_path = os.path.join(output_dir, model_filename)
        info_path = os.path.join(output_dir, info_filename)

        joblib.dump(model, model_path)
        with open(info_path, 'w') as f:
            json.dump(model_info, f, indent=2)

        logger.info(f"Model saved to: {model_path}")
        logger.info(f"Model info saved to: {info_path}")

        return model, model_info, model_path, info_path

    except FileNotFoundError:
        logger.error(f"Dataset file not found at {dataset_path}")
        return None, None, None, None
    except KeyError as e:
        logger.error(f"Missing expected column in dataset: {e}")
        return None, None, None, None
    except Exception as e:
        logger.error(f"An error occurred during model training: {e}", exc_info=True)
        return None, None, None, None

def predict_with_model(
    model: Any,
    model_info: Dict[str, Any],
    input_data: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Makes a prediction using the loaded model and input data.

    Args:
        model: The loaded scikit-learn model object.
        model_info: The dictionary containing model metadata (especially feature list).
        input_data: A dictionary representing a single input sample, with keys
                    matching the model's expected features.

    Returns:
        A dictionary containing the prediction and probabilities, or None if prediction fails.
    """
    logger.info(f"Making prediction with model type: {model_info.get('model_type', 'Unknown')}")
    try:
        # Ensure all required features are present in input_data
        required_features = model_info.get("features")
        if not required_features:
            logger.error("Feature list not found in model_info.")
            return None

        if not all(feature in input_data for feature in required_features):
            missing = [f for f in required_features if f not in input_data]
            logger.error(f"Missing required features in input data: {missing}")
            return None

        # Create DataFrame in the correct order
        input_df = pd.DataFrame([input_data])[required_features] # Ensure correct column order
        logger.debug(f"Input DataFrame for prediction: \n{input_df}")

        # Make prediction
        prediction = model.predict(input_df)
        prediction_value = int(prediction[0]) # Convert numpy int to standard int

        # Get probabilities (if available)
        probabilities = None
        if hasattr(model, "predict_proba"):
            proba_raw = model.predict_proba(input_df)
            # Assuming binary classification: [prob_class_0, prob_class_1]
            probabilities = {
                "class_0": float(proba_raw[0][0]),
                "class_1": float(proba_raw[0][1])
            }

        result = {
            "prediction": prediction_value,
            "probabilities": probabilities
        }
        logger.info(f"Prediction successful: {result}")
        return result

    except Exception as e:
        logger.error(f"An error occurred during prediction: {e}", exc_info=True)
        return None 