FROM python:3.11-slim

# Set environment variables for best practices
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

# Copy requirements first for caching
COPY backend/requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the entire backend directory into /app/backend within the container
COPY backend /app/backend

# Set PYTHONPATH to include the directory containing the 'backend' package
ENV PYTHONPATH=/app

# Expose the port
EXPOSE 8000

# Run uvicorn targeting the module path
# The WORKDIR is still /app, but uvicorn knows to look for backend.main:app
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"] 