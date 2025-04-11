from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging # Add logging config

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Import routers
from .routers import data, training, inference, auth, provenance, models # Add models router

app = FastAPI(
    title="Decentralized AI Platform Backend",
    description="API for managing ML datasets and models with Filecoin storage and FVM provenance.",
    version="0.1.0"
)

# --- CORS Configuration ---
# Define allowed origins (adjust as needed for production)
# For development, allow the Next.js frontend origin
origins = [
    "http://localhost:3000", # Next.js frontend
    # Add your deployed frontend URL here for production
    # e.g., "https://your-frontend-domain.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # List of origins that are allowed to make requests
    allow_credentials=True, # Allow cookies/authorization headers
    allow_methods=["*"],    # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],    # Allow all headers
)

# Include routers
app.include_router(auth.router) # Include auth router
app.include_router(data.router)
app.include_router(training.router) # Include training router
app.include_router(inference.router) # Include inference router
app.include_router(provenance.router) # Include provenance router
app.include_router(models.router) # Include the new models router


@app.get("/", tags=["Health Check"])
def read_root():
    """Root endpoint for health check."""
    return {"status": "ok", "message": "Welcome to the Decentralized AI Platform Backend!"}

# --- Placeholder Endpoints (to be implemented) ---

# TODO: Authentication endpoints (SIWE)

# TODO: Dataset upload endpoint

# TODO: Model training endpoint

# TODO: Model inference endpoint

# TODO: Provenance query endpoints (FVM interaction)


# --- Server Startup (for local development) ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) # Use reload for development 