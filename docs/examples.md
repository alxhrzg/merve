# Examples Guide

## Quick Start Examples

### Basic Single Classifier

```yaml
# mlserver.yaml
predictor:
  module: my_predictor
  class_name: MyPredictor
  init_kwargs:
    model_path: "./model.pkl"
```

```python
# my_predictor.py
import pickle
import numpy as np

class MyPredictor:
    def __init__(self, model_path: str):
        with open(model_path, 'rb') as f:
            self.model = pickle.load(f)

    def predict(self, X):
        return self.model.predict(X)
```

```bash
# Start server
ml_server serve

# Test prediction
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"payload": {"ndarray": [[1, 2, 3, 4]]}}'
```

## Titanic Survival Example

Complete example with data preprocessing and multiple models.

### Directory Structure
```
examples/example_titanic_manual_setup/
├── mlserver.yaml
├── mlserver_multi_classifier_simple.yaml
├── predictor_catboost.py
├── predictor_randomforest.py
├── train_models.py
└── models/
    ├── catboost_model.cbm
    ├── rf_model.pkl
    ├── features.json
    ├── encoders.pkl
    └── scaler.pkl
```

### Training Script
```python
# train_models.py
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.ensemble import RandomForestClassifier
from catboost import CatBoostClassifier
import pickle
import json

# Load and prepare data
def prepare_titanic_data():
    # Load data (example using synthetic data)
    data = pd.DataFrame({
        'age': np.random.randint(1, 80, 1000),
        'sex': np.random.choice(['male', 'female'], 1000),
        'fare': np.random.uniform(5, 500, 1000),
        'pclass': np.random.choice([1, 2, 3], 1000),
        'survived': np.random.choice([0, 1], 1000)
    })

    # Encode categorical variables
    le_sex = LabelEncoder()
    data['sex_encoded'] = le_sex.fit_transform(data['sex'])

    # Scale features
    scaler = StandardScaler()
    features = ['age', 'sex_encoded', 'fare', 'pclass']
    X = data[features]
    X_scaled = scaler.fit_transform(X)
    y = data['survived']

    return X_scaled, y, features, {'sex': le_sex}, scaler

# Train models
X, y, features, encoders, scaler = prepare_titanic_data()
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)

# Train CatBoost
catboost_model = CatBoostClassifier(
    iterations=100,
    learning_rate=0.1,
    depth=6,
    verbose=False
)
catboost_model.fit(X_train, y_train)

# Train RandomForest
rf_model = RandomForestClassifier(
    n_estimators=100,
    max_depth=10,
    random_state=42
)
rf_model.fit(X_train, y_train)

# Save artifacts
catboost_model.save_model('models/catboost_model.cbm')
with open('models/rf_model.pkl', 'wb') as f:
    pickle.dump(rf_model, f)
with open('models/features.json', 'w') as f:
    json.dump(features, f)
with open('models/encoders.pkl', 'wb') as f:
    pickle.dump(encoders, f)
with open('models/scaler.pkl', 'wb') as f:
    pickle.dump(scaler, f)

print("Models trained and saved!")
```

### CatBoost Predictor
```python
# predictor_catboost.py
import json
import pickle
import numpy as np
import pandas as pd
from catboost import CatBoostClassifier
from typing import Union, List

class CatBoostPredictor:
    def __init__(self,
                 model_path: str = "./models/catboost_model.cbm",
                 features_path: str = "./models/features.json",
                 scaler_path: str = "./models/scaler.pkl"):

        # Load model
        self.model = CatBoostClassifier()
        self.model.load_model(model_path)

        # Load features
        with open(features_path, 'r') as f:
            self.features = json.load(f)

        # Load scaler
        with open(scaler_path, 'rb') as f:
            self.scaler = pickle.load(f)

    def preprocess(self, data: pd.DataFrame) -> np.ndarray:
        """Preprocess input data."""
        # Encode sex if present
        if 'sex' in data.columns:
            data['sex_encoded'] = data['sex'].map({'male': 1, 'female': 0})

        # Select features
        X = data[self.features].values

        # Scale
        X_scaled = self.scaler.transform(X)

        return X_scaled

    def predict(self, X: Union[List, np.ndarray, pd.DataFrame]) -> np.ndarray:
        """Make predictions."""
        # Convert to DataFrame if needed
        if isinstance(X, (list, np.ndarray)):
            X = pd.DataFrame(X, columns=self.features[:len(X[0])])

        # Preprocess
        X_processed = self.preprocess(X)

        # Predict
        return self.model.predict(X_processed)

    def predict_proba(self, X: Union[List, np.ndarray, pd.DataFrame]) -> np.ndarray:
        """Return prediction probabilities."""
        if isinstance(X, (list, np.ndarray)):
            X = pd.DataFrame(X, columns=self.features[:len(X[0])])

        X_processed = self.preprocess(X)
        return self.model.predict_proba(X_processed)
```

### Configuration
```yaml
# mlserver.yaml - Single classifier
server:
  title: "Titanic Survival Prediction"
  workers: 4

predictor:
  module: predictor_catboost
  class_name: CatBoostPredictor

observability:
  metrics: true
  structured_logging: true

api:
  adapter: "auto"
  thread_safe_predict: true

classifier:
  name: "catboost-survival"
  version: "1.0.0"
```

```yaml
# mlserver_multi_classifier_simple.yaml - Multiple classifiers
classifiers:
  catboost-survival:
    predictor:
      module: predictor_catboost
      class_name: CatBoostPredictor
    metadata:
      name: "catboost-survival"
      version: "1.0.0"
      description: "CatBoost model for Titanic survival"

  randomforest-survival:
    predictor:
      module: predictor_randomforest
      class_name: RandomForestSurvivalPredictor
    metadata:
      name: "randomforest-survival"
      version: "2.0.0"
      description: "RandomForest model for Titanic survival"

default_classifier: "catboost-survival"

server:
  workers: 4
  port: 8000

observability:
  metrics: true
```

### Running the Example

```bash
# Train models
python train_models.py

# Serve single classifier
ml_server serve mlserver.yaml

# Or serve specific classifier from multi-config
ml_server serve mlserver_multi_classifier_simple.yaml --classifier catboost-survival

# Test prediction
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "payload": {
      "records": [{
        "age": 25,
        "sex": "male",
        "fare": 72.5,
        "pclass": 1
      }]
    }
  }'

# Response
{
  "predictions": [0],
  "time_ms": 12.5,
  "metadata": {
    "project": "mlserver-repo",
    "classifier": "catboost-survival",
    "predictor_class": "CatBoostPredictor",
    "predictor_module": "predictor_catboost",
    "config_file": "mlserver.yaml",
    "git_commit": "abc123",
    "git_tag": "v1.0.0",
    "deployed_at": "2025-01-18T10:00:00Z",
    "mlserver_version": "2.0.0"
  }
}
```

## Load Testing Example

### Locust Configuration
```python
# tests/load/locustfile.py
from locust import HttpUser, task, between
import random

class TitanicPredictionUser(HttpUser):
    wait_time = between(0.5, 2.0)

    def generate_passenger(self):
        """Generate random passenger data."""
        return {
            "age": random.randint(1, 80),
            "sex": random.choice(["male", "female"]),
            "fare": random.uniform(5, 500),
            "pclass": random.choice([1, 2, 3])
        }

    @task(10)
    def single_prediction(self):
        """Test single prediction endpoint."""
        self.client.post(
            "/predict",
            json={"payload": {"records": [self.generate_passenger()]}}
        )

    @task(5)
    def batch_prediction(self):
        """Test batch predictions."""
        passengers = [self.generate_passenger() for _ in range(10)]
        self.client.post(
            "/batch_predict",
            json={"payload": {"records": passengers}}
        )

    @task(2)
    def prediction_proba(self):
        """Test probability predictions."""
        self.client.post(
            "/predict_proba",
            json={"payload": {"records": [self.generate_passenger()]}}
        )

    @task(1)
    def check_health(self):
        """Health check."""
        self.client.get("/healthz")

    @task(1)
    def get_info(self):
        """Get model info."""
        self.client.get("/info")
```

### Running Load Tests
```bash
# Start server
ml_server serve

# Run Locust web UI
locust -f tests/load/locustfile.py --host http://localhost:8000

# Or run headless
locust -f tests/load/locustfile.py \
  --headless \
  --users 100 \
  --spawn-rate 10 \
  --run-time 60s \
  --host http://localhost:8000
```

### Interactive Load Test Demo
```python
# examples/load_test_demo.py
import asyncio
import httpx
import time
from rich.console import Console
from rich.table import Table
from rich.live import Live
import statistics

console = Console()

class LoadTester:
    def __init__(self, base_url: str, num_workers: int = 10):
        self.base_url = base_url
        self.num_workers = num_workers
        self.results = []
        self.errors = 0

    async def make_request(self, session: httpx.AsyncClient):
        """Make a single prediction request."""
        start = time.time()
        try:
            response = await session.post(
                f"{self.base_url}/predict",
                json={
                    "payload": {
                        "records": [{
                            "age": 25,
                            "sex": "male",
                            "fare": 50,
                            "pclass": 2
                        }]
                    }
                }
            )
            response.raise_for_status()
            elapsed = time.time() - start
            self.results.append(elapsed)
            return True
        except Exception as e:
            self.errors += 1
            return False

    async def worker(self, session: httpx.AsyncClient):
        """Worker that continuously makes requests."""
        while True:
            await self.make_request(session)
            await asyncio.sleep(0.1)

    def get_stats(self):
        """Calculate statistics."""
        if not self.results:
            return {}

        return {
            "requests": len(self.results),
            "errors": self.errors,
            "avg_ms": statistics.mean(self.results) * 1000,
            "p50_ms": statistics.median(self.results) * 1000,
            "p95_ms": statistics.quantiles(self.results, n=20)[18] * 1000 if len(self.results) > 20 else 0,
            "p99_ms": statistics.quantiles(self.results, n=100)[98] * 1000 if len(self.results) > 100 else 0,
        }

    async def run(self, duration: int = 30):
        """Run load test for specified duration."""
        async with httpx.AsyncClient() as session:
            # Start workers
            workers = [
                asyncio.create_task(self.worker(session))
                for _ in range(self.num_workers)
            ]

            # Run for duration
            start_time = time.time()
            with Live(console=console, refresh_per_second=1) as live:
                while time.time() - start_time < duration:
                    stats = self.get_stats()

                    # Create table
                    table = Table(title="Load Test Results")
                    table.add_column("Metric", style="cyan")
                    table.add_column("Value", style="green")

                    table.add_row("Total Requests", str(stats.get("requests", 0)))
                    table.add_row("Errors", str(stats.get("errors", 0)))
                    table.add_row("Avg Latency", f"{stats.get('avg_ms', 0):.2f} ms")
                    table.add_row("P50 Latency", f"{stats.get('p50_ms', 0):.2f} ms")
                    table.add_row("P95 Latency", f"{stats.get('p95_ms', 0):.2f} ms")
                    table.add_row("P99 Latency", f"{stats.get('p99_ms', 0):.2f} ms")

                    live.update(table)
                    await asyncio.sleep(1)

            # Cancel workers
            for worker in workers:
                worker.cancel()

# Run the load test
async def main():
    tester = LoadTester("http://localhost:8000", num_workers=20)
    await tester.run(duration=30)

if __name__ == "__main__":
    asyncio.run(main())
```

## Monitoring Stack Example

### Docker Compose Setup
```yaml
# docker-compose.monitoring.yml
version: '3.8'

services:
  mlserver:
    build: .
    ports:
      - "8000:8000"
    environment:
      - MLSERVER_METRICS=true
    volumes:
      - ./examples:/app/examples

  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'

  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - ./monitoring/dashboards:/var/lib/grafana/dashboards
      - ./monitoring/provisioning:/etc/grafana/provisioning
```

### Prometheus Configuration
```yaml
# monitoring/prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'mlserver'
    static_configs:
      - targets: ['mlserver:8000']
```

### Grafana Dashboard
```json
# monitoring/dashboards/mlserver.json
{
  "dashboard": {
    "title": "MLServer Metrics",
    "panels": [
      {
        "title": "Request Rate",
        "targets": [
          {
            "expr": "rate(mlserver_requests_total[5m])"
          }
        ]
      },
      {
        "title": "Latency (P95)",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(mlserver_request_duration_seconds_bucket[5m]))"
          }
        ]
      },
      {
        "title": "Error Rate",
        "targets": [
          {
            "expr": "rate(mlserver_prediction_errors_total[5m])"
          }
        ]
      }
    ]
  }
}
```

### Running the Stack
```bash
# Start all services
docker-compose -f docker-compose.monitoring.yml up

# Access services
# MLServer: http://localhost:8000
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3000 (admin/admin)

# Run load test to generate metrics
python examples/load_test_demo.py
```

## Custom Predictor Examples

### PyTorch Example
```python
# predictor_pytorch.py
import torch
import torch.nn as nn
import numpy as np

class PyTorchPredictor:
    def __init__(self, model_path: str):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = torch.load(model_path, map_location=self.device)
        self.model.eval()

    def predict(self, X):
        X_tensor = torch.FloatTensor(X).to(self.device)

        with torch.no_grad():
            outputs = self.model(X_tensor)
            predictions = torch.argmax(outputs, dim=1)

        return predictions.cpu().numpy()
```

### TensorFlow Example
```python
# predictor_tensorflow.py
import tensorflow as tf
import numpy as np

class TensorFlowPredictor:
    def __init__(self, model_path: str):
        self.model = tf.keras.models.load_model(model_path)

    def predict(self, X):
        predictions = self.model.predict(X)
        return np.argmax(predictions, axis=1)

    def predict_proba(self, X):
        return self.model.predict(X)
```

### Hugging Face Transformers Example
```python
# predictor_transformers.py
from transformers import pipeline
import numpy as np

class TransformerPredictor:
    def __init__(self, model_name: str = "distilbert-base-uncased-finetuned-sst-2-english"):
        self.classifier = pipeline("sentiment-analysis", model=model_name)

    def predict(self, texts):
        results = self.classifier(texts)
        return np.array([1 if r['label'] == 'POSITIVE' else 0 for r in results])

    def predict_proba(self, texts):
        results = self.classifier(texts)
        return np.array([[1-r['score'], r['score']] if r['label'] == 'POSITIVE'
                        else [r['score'], 1-r['score']] for r in results])
```

## Complete Demo Makefile

```makefile
# Makefile
.PHONY: demo-setup demo-train demo-serve demo-test demo-load demo-monitoring demo-full

# Setup environment
demo-setup:
	pip install -e ".[dev]"
	mkdir -p examples/models

# Train models
demo-train:
	cd examples && python train_models.py

# Start server
demo-serve:
	ml_server serve examples/mlserver.yaml

# Test predictions
demo-test:
	@echo "Testing single prediction..."
	curl -X POST http://localhost:8000/predict \
		-H "Content-Type: application/json" \
		-d '{"payload": {"records": [{"age": 25, "sex": "male", "fare": 50, "pclass": 2}]}}'

# Run load test
demo-load:
	python examples/load_test_demo.py

# Start monitoring stack
demo-monitoring:
	docker-compose -f docker-compose.monitoring.yml up -d

# Full demo
demo-full: demo-setup demo-train
	@echo "Starting full demo..."
	$(MAKE) demo-monitoring
	$(MAKE) demo-serve &
	sleep 5
	$(MAKE) demo-test
	$(MAKE) demo-load
	@echo "Demo complete! Check:"
	@echo "  - API: http://localhost:8000"
	@echo "  - Docs: http://localhost:8000/docs"
	@echo "  - Metrics: http://localhost:8000/metrics"
	@echo "  - Prometheus: http://localhost:9090"
	@echo "  - Grafana: http://localhost:3000"
```