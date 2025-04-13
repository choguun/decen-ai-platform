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
        
        # --- Explicitly drop identifier columns not used for training ---
        identifier_cols = ['CustomerID'] # Add other identifiers if needed
        cols_to_drop_in_X = [col for col in identifier_cols if col in X.columns]
        if cols_to_drop_in_X:
            X = X.drop(columns=cols_to_drop_in_X)
            logger.info(f"Dropped identifier columns from features: {cols_to_drop_in_X}")

        # --- Preprocessing: Handle Categorical Features using One-Hot Encoding --- 
        categorical_cols = X.select_dtypes(include=['object', 'category']).columns
        if not categorical_cols.empty:
            logger.info(f"Applying one-hot encoding to categorical columns: {list(categorical_cols)}")
            X = pd.get_dummies(X, columns=list(categorical_cols), drop_first=True) # drop_first avoids multicollinearity
            logger.info(f"Data shape after one-hot encoding: {X.shape}")
        else:
             logger.info("No categorical columns found requiring one-hot encoding.")

        # --- Store original categorical cols used for encoding --- 
        original_categorical_cols = list(categorical_cols)

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
            "original_categorical_features": original_categorical_cols # Store the list
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
        model: The loaded model object.
        model_info: The dictionary containing model metadata (features, categorical features).
        input_data: A dictionary representing a single input sample, with keys
                    matching the model's expected features.

    Returns:
        A dictionary containing the prediction and probabilities, or None if prediction fails.
    """
    logger.info(f"Making prediction with model type: {model_info.get('model_type', 'Unknown')}")
    try:
        # --- Get required info from metadata --- 
        expected_features_after_encoding = model_info.get("features") # Full feature list AFTER encoding
        original_categorical_features = model_info.get("original_categorical_features", []) # List of categorical cols BEFORE encoding

        if not expected_features_after_encoding:
            logger.error("Feature list not found in model_info.")
            return None

        # --- Convert input dict to DataFrame --- 
        # We need a DataFrame to use get_dummies
        input_df_original = pd.DataFrame([input_data])
        logger.debug(f"Original input DataFrame: \n{input_df_original}")

        # --- Drop identifier columns before preprocessing ---
        identifier_cols = ['CustomerID'] # Match the columns dropped during training
        cols_to_drop_in_input = [col for col in identifier_cols if col in input_df_original.columns]
        if cols_to_drop_in_input:
            input_df_original = input_df_original.drop(columns=cols_to_drop_in_input)
            logger.info(f"Dropped identifier columns from input data: {cols_to_drop_in_input}")

        # --- Apply One-Hot Encoding if needed --- 
        input_df_processed = input_df_original.copy()
        if original_categorical_features:
            logger.info(f"Applying one-hot encoding to input for columns: {original_categorical_features}")
            try:
                # Ensure only columns present in input are encoded
                cols_to_encode = [col for col in original_categorical_features if col in input_df_processed.columns]
                if cols_to_encode:
                    input_df_processed = pd.get_dummies(input_df_processed, columns=cols_to_encode, drop_first=True)
                    logger.debug(f"Input DataFrame after get_dummies: \n{input_df_processed.head()}")
                    # Log dtypes after get_dummies
                    logger.debug(f"Input DataFrame dtypes after get_dummies: \n{input_df_processed.dtypes}")
                else:
                    logger.info("No categorical columns found in the input data to encode.")
            except Exception as e:
                logger.error(f"Error applying get_dummies to input data: {e}", exc_info=True)
                return None # Encoding failed

        # --- Align Columns with Training Data --- 
        # Ensure the DataFrame has exactly the columns the model expects,
        # in the correct order, filling missing ones with 0.
        try:
            # Reindex based on the feature list from training
            input_df_aligned = input_df_processed.reindex(columns=expected_features_after_encoding, fill_value=0)
            logger.debug(f"Input DataFrame after aligning columns: \n{input_df_aligned}")
            # Log dtypes after alignment
            logger.debug(f"Input DataFrame dtypes after alignment: \n{input_df_aligned.dtypes}")
        except Exception as e:
             logger.error(f"Error aligning input columns with trained features: {e}", exc_info=True)
             return None # Column alignment failed

        # --- Validate no unexpected extra columns --- 
        extra_cols = set(input_df_aligned.columns) - set(expected_features_after_encoding)
        if extra_cols:
             logger.warning(f"Input data contained unexpected columns after processing: {extra_cols}. These will be ignored.")
             # Note: reindex should handle this, but double-checking might be useful.

        # Make prediction
        prediction = model.predict(input_df_aligned) # Use the fully processed DataFrame
        logger.debug(f"Raw prediction output: {prediction} (Type: {type(prediction)})")
        prediction_value = int(prediction[0]) # Convert numpy int to standard int

        # Get probabilities (if available)
        probabilities = None
        if hasattr(model, "predict_proba"):
            proba_raw = model.predict_proba(input_df_aligned)
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