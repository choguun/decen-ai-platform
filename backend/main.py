from fastapi import FastAPI
import logging # Add logging config

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Import routers
from .routers import data, training, inference # Add training and inference

app = FastAPI(
    title="Decentralized AI Platform Backend",
    description="API for managing ML datasets and models with Filecoin storage and FVM provenance.",
    version="0.1.0"
)

# Include routers
app.include_router(data.router)
app.include_router(training.router) # Include training router
app.include_router(inference.router) # Include inference router

@app.get("/", tags=["Health Check"])
def read_root():
    """Root endpoint for health check."""
    return {"status": "ok", "message": "Welcome to the Decentralized AI Platform Backend!"}

# --- Placeholder Endpoints (to be implemented) ---

# TODO: Authentication endpoints (SIWE)

# TODO: Dataset upload endpoint

# TODO: Model training endpoint

# TODO: Model inference endpoint

# TODO: Provenance query endpoints


# --- Server Startup (for local development) ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 