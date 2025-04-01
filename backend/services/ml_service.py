import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
import joblib
import os
import json
import logging
import tempfile
from typing import Tuple, Dict, Any

logger = logging.getLogger(__name__)

def train_model_on_dataset(dataset_path: str) -> Tuple[Any, Dict[str, Any], str, str] | Tuple[None, None, None, None]:
    """
    Trains a RandomForestClassifier model on the dataset located at dataset_path.

    Args:
        dataset_path: The file path to the dataset (e.g., CSV).

    Returns:
        A tuple containing:
        - The trained model object.
        - A dictionary containing model metadata (accuracy, features, etc.).
        - The file path to the saved model (.joblib).
        - The file path to the saved model info (.json).
        Returns (None, None, None, None) if training fails.
    """
    logger.info(f"Starting model training using dataset: {dataset_path}")
    try:
        # Load the dataset
        df = pd.read_csv(dataset_path)
        logger.info(f"Dataset loaded successfully. Shape: {df.shape}")

        # Basic validation (assuming 'diabetes' is the target column)
        if 'diabetes' not in df.columns:
            logger.error("Target column 'diabetes' not found in the dataset.")
            return None, None, None, None

        # Split features and target
        X = df.drop('diabetes', axis=1)
        y = df['diabetes']
        feature_names = list(X.columns)

        # Split into training and testing sets
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        logger.info(f"Data split into training ({len(X_train)} samples) and testing ({len(X_test)} samples).")

        # Train a Random Forest classifier
        model = RandomForestClassifier(n_estimators=100, random_state=42)
        model.fit(X_train, y_train)
        logger.info("RandomForestClassifier model trained successfully.")

        # Evaluate the model
        y_pred = model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        logger.info(f"Model evaluation completed. Accuracy: {accuracy:.4f}")

        # Create model info dictionary
        model_info = {
            "model_type": "RandomForestClassifier",
            "n_estimators": 100,
            "random_state": 42,
            "features": feature_names,
            "target_column": "diabetes",
            "accuracy": float(accuracy),
            "training_samples": int(len(X_train)),
            "test_samples": int(len(X_test)),
            "dataset_source_path": dataset_path # Keep track of source for reference
        }

        # Save model and info to temporary files
        temp_dir = tempfile.mkdtemp()
        model_filename = "trained_model.joblib"
        info_filename = "model_info.json"
        model_path = os.path.join(temp_dir, model_filename)
        info_path = os.path.join(temp_dir, info_filename)

        joblib.dump(model, model_path)
        with open(info_path, 'w') as f:
            json.dump(model_info, f, indent=2)

        logger.info(f"Model saved to temporary path: {model_path}")
        logger.info(f"Model info saved to temporary path: {info_path}")

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

def predict_with_model(model: Any, model_info: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any] | None:
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