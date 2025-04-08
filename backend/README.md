# Backend

This directory contains the Python backend service.
 
- **Framework:** FastAPI
- **Key Libraries:** Lighthouse-Web3 SDK, Scikit-learn, Pandas, Joblib, Web3.py, Celery (optional)
- **Purpose:** Handles API requests, manages ML workflows (training, inference), interacts with Lighthouse for storage, and communicates with the FVM smart contract for provenance. 

```shell
$ source venv/bin/activate
$ cd ..
$ uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```