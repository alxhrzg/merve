# Generated Dockerfile for titanic-survival-predictor v1.0.0
# Generated at: 2025-09-15T18:36:43.230146

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install mlserver-fastapi-wrapper
COPY mlserver_fastapi_wrapper*.whl /tmp/
RUN pip install --no-cache-dir /tmp/mlserver_fastapi_wrapper*.whl && rm /tmp/mlserver_fastapi_wrapper*.whl

# Copy project files (intelligently selected)
COPY artifacts/ ./artifacts/
COPY mlserver.yaml requirements.txt ./

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Set PYTHONPATH to include current directory for local modules
ENV PYTHONPATH=/app

# Create non-root user
RUN useradd --create-home --shell /bin/bash mlserver
RUN chown -R mlserver:mlserver /app
USER mlserver

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

# Expose port
EXPOSE 8000

# Set labels for metadata
LABEL org.opencontainers.image.title="titanic-survival-predictor"
LABEL org.opencontainers.image.version="1.0.0"
LABEL org.opencontainers.image.description="Titanic survival prediction model using CatBoost"
LABEL ml.classifier.name="titanic-survival-predictor"
LABEL ml.classifier.version="1.0.0"
LABEL ml.created="2025-09-15T18:36:43.230163"

# Command to run the server
CMD ["ml_server", "serve", "mlserver.yaml"]
