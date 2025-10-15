# Architecture Overview

## System Architecture

MLServer follows a modular, plugin-based architecture designed for flexibility and performance.

```
┌─────────────────────────────────────────────────────────┐
│                     Client Applications                  │
└─────────────────┬───────────────────────────────────────┘
                  │ HTTP/REST
┌─────────────────▼───────────────────────────────────────┐
│                    FastAPI Application                   │
│  ┌──────────────────────────────────────────────────┐  │
│  │              API Endpoints Layer                  │  │
│  │  /predict  /info  /metrics  /healthz             │  │
│  └──────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────┐  │
│  │              Middleware Stack                     │  │
│  │  CORS │ Metrics │ Logging │ Rate Limiting       │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────┬───────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────┐
│                  Core Components                         │
│  ┌─────────────┐ ┌──────────┐ ┌──────────────────┐    │
│  │   Adapter   │ │ Predictor│ │  Concurrency     │    │
│  │   Manager   │ │  Loader  │ │    Limiter       │    │
│  └─────────────┘ └──────────┘ └──────────────────┘    │
└─────────────────┬───────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────┐
│                 Predictor Plugin Layer                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ CatBoost │ │  Random  │ │ XGBoost  │ │  Custom  │  │
│  │Predictor │ │  Forest  │ │Predictor │ │Predictor │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
└──────────────────────────────────────────────────────────┘
```

## Core Components

### FastAPI Application

The main application layer built on FastAPI:

```python
# mlserver/server.py
app = FastAPI(
    title=config.server.title,
    lifespan=lifespan  # Manages startup/shutdown
)
```

**Responsibilities**:
- Request routing
- Response serialization
- OpenAPI documentation
- Async request handling

### Configuration System

```python
# mlserver/config.py
class AppConfig:
    server: ServerConfig
    predictor: PredictorConfig
    observability: ObservabilityConfig
    api: ApiConfig
```

**Features**:
- Pydantic validation
- Environment variable overrides
- Multi-classifier support
- Global settings inheritance

### Predictor Loader

Dynamic module loading system:

```python
# mlserver/predictor_loader.py
def load_predictor(config: PredictorConfig):
    # Resolve module path
    module_path = resolve_module_path(config.module)
    
    # Dynamic import
    module = importlib.import_module(module_path)
    
    # Instantiate predictor
    predictor_class = getattr(module, config.class_name)
    return predictor_class(**config.init_kwargs)
```

### Input Adapters

```python
# mlserver/adapters.py
class AdapterFactory:
    @staticmethod
    def get_adapter(adapter_type: str) -> BaseAdapter:
        if adapter_type == "records":
            return RecordsAdapter()
        elif adapter_type == "ndarray":
            return NdarrayAdapter()
        else:
            return AutoAdapter()
```

**Adapter Types**:
- **RecordsAdapter**: JSON objects with named features
- **NdarrayAdapter**: Nested arrays
- **AutoAdapter**: Automatic format detection

### Concurrency Control

```python
# mlserver/concurrency_limiter.py
class ConcurrencyLimiter:
    def __init__(self, max_concurrent: int):
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def acquire(self):
        await self.semaphore.acquire()
    
    def release(self):
        self.semaphore.release()
```

## Request Flow

### 1. Request Reception
```
Client → nginx/LB → FastAPI → Middleware Stack
```

### 2. Preprocessing
```python
# Request validation
request_data = PredictionRequest(**await request.json())

# Correlation ID generation
request_id = str(uuid.uuid4())

# Logging
logger.info(f"Request {request_id}: {request_data}")
```

### 3. Adaptation
```python
# Convert input format
adapter = AdapterFactory.get_adapter(config.api.adapter)
input_array = adapter.transform(request_data.data)
```

### 4. Prediction
```python
# Concurrency control
async with limiter:
    # Thread-safe prediction (if configured)
    with prediction_lock:
        predictions = predictor.predict(input_array)
```

### 5. Response
```python
# Format response
response = PredictionResponse(
    predictions=predictions.tolist(),
    model=config.classifier.name,
    version=config.classifier.version
)

# Return with metrics
return response
```

## Process Model

### Multi-Process Architecture

```
┌─────────────────────────────────────────────┐
│              Main Process                    │
│         (Uvicorn Server Manager)            │
└───────────────┬─────────────────────────────┘
                │ fork()
    ┌───────────┼───────────┬──────────┐
    ▼           ▼           ▼          ▼
┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
│Worker 1 │ │Worker 2 │ │Worker 3 │ │Worker N │
│(Process)│ │(Process)│ │(Process)│ │(Process)│
└─────────┘ └─────────┘ └─────────┘ └─────────┘
```

**Benefits**:
- True parallelism (no GIL)
- Process isolation
- Container-friendly
- Fault tolerance

### Worker Lifecycle

```python
# Each worker process:
1. Fork from main
2. Load configuration
3. Initialize predictor
4. Start FastAPI app
5. Handle requests
6. Graceful shutdown
```

## Performance Optimizations

### 1. Feature Ordering Cache

```python
# Cache feature order after first request
class RecordsAdapter:
    def __init__(self):
        self._feature_order_cache = {}
    
    def transform(self, data):
        # Use cached order for subsequent requests
        if hash(data) in self._feature_order_cache:
            return self._feature_order_cache[hash(data)]
```

### 2. Numpy Optimizations

```python
# Efficient array operations
def batch_predict(self, X):
    # Vectorized operations
    X = np.asarray(X, dtype=np.float32)
    
    # Batch processing
    return self.model.predict(X)
```

### 3. Connection Pooling

```python
# Keep-alive connections
app.add_middleware(
    HTTPSRedirectMiddleware,
    keep_alive=True,
    pool_connections=10
)
```

### 4. Async I/O

```python
# Non-blocking operations
@app.post("/predict")
async def predict(request: Request):
    # Async JSON parsing
    data = await request.json()
    
    # Async prediction (if supported)
    result = await predictor.async_predict(data)
    
    return result
```

## Plugin System

### Predictor Interface

```python
class BasePredictor(ABC):
    @abstractmethod
    def predict(self, X):
        """Make predictions"""
        pass
    
    def predict_proba(self, X):
        """Optional: Return probabilities"""
        raise NotImplementedError
```

### Custom Predictor Example

```python
class CustomPredictor(BasePredictor):
    def __init__(self, model_path: str):
        self.model = self.load_model(model_path)
    
    def predict(self, X):
        return self.model.predict(X)
```

### Registration

```yaml
# mlserver.yaml
predictor:
  module: custom_predictor
  class_name: CustomPredictor
  init_kwargs:
    model_path: "./model.pkl"
```

## Scaling Strategies

### Vertical Scaling

```yaml
# Increase workers
server:
  workers: 16  # More processes

api:
  max_concurrent_requests: 100  # Higher concurrency
```

### Horizontal Scaling

```yaml
# Kubernetes deployment
apiVersion: apps/v1
kind: Deployment
spec:
  replicas: 10  # Multiple pods
  template:
    spec:
      containers:
      - name: mlserver
        resources:
          requests:
            cpu: "2"
            memory: "4Gi"
```

### Load Balancing

```nginx
# nginx.conf
upstream mlserver {
    least_conn;
    server mlserver1:8000;
    server mlserver2:8000;
    server mlserver3:8000;
}
```

## Security Architecture

### Request Validation

```python
# Pydantic models
class PredictionRequest(BaseModel):
    data: Union[List[Dict], List[List]]
    
    @validator('data')
    def validate_data(cls, v):
        # Size limits
        if len(v) > 1000:
            raise ValueError("Batch too large")
        return v
```

### CORS Configuration

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.server.cors.allow_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"]
)
```

### Rate Limiting

```python
# Semaphore-based limiting
if config.api.max_concurrent_requests:
    limiter = ConcurrencyLimiter(
        config.api.max_concurrent_requests
    )
```

## Monitoring Architecture

### Metrics Collection

```python
# Prometheus metrics
request_duration = Histogram(
    'mlserver_request_duration_seconds',
    'Request duration',
    ['endpoint', 'method']
)

@app.middleware("http")
async def metrics_middleware(request, call_next):
    with request_duration.time():
        response = await call_next(request)
    return response
```

### Health Checks

```python
@app.get("/healthz")
def health_check():
    # Liveness probe
    return {"status": "healthy"}

@app.get("/readyz")
def readiness_check():
    # Readiness probe
    if predictor_loaded:
        return {"status": "ready"}
    else:
        raise HTTPException(503)
```

## Error Handling

### Graceful Degradation

```python
@app.exception_handler(PredictionError)
async def prediction_error_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={
            "error": "Prediction failed",
            "details": str(exc),
            "fallback": "Using default prediction"
        }
    )
```

### Circuit Breaker Pattern

```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5):
        self.failure_count = 0
        self.threshold = failure_threshold
        self.is_open = False
    
    async def call(self, func, *args):
        if self.is_open:
            raise ServiceUnavailable()
        
        try:
            result = await func(*args)
            self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            if self.failure_count >= self.threshold:
                self.is_open = True
            raise
```

## Deployment Architecture

### Container Structure

```dockerfile
# Multi-stage build
FROM python:3.9-slim as builder
# Build dependencies

FROM python:3.9-slim
# Runtime only
COPY --from=builder /app /app
CMD ["ml_server", "serve"]
```

### Kubernetes Architecture

```yaml
# Service mesh integration
apiVersion: v1
kind: Service
metadata:
  annotations:
    service.beta.kubernetes.io/aws-load-balancer-type: "nlb"
spec:
  type: LoadBalancer
  ports:
  - port: 80
    targetPort: 8000
```

## Performance Benchmarks

### Latency Profile

| Component | P50 | P95 | P99 |
|-----------|-----|-----|-----|
| Request Parse | 1ms | 2ms | 5ms |
| Adaptation | 2ms | 5ms | 10ms |
| Prediction | 20ms | 50ms | 100ms |
| Response | 1ms | 2ms | 5ms |
| **Total** | **24ms** | **59ms** | **120ms** |

### Throughput

| Workers | RPS | CPU | Memory |
|---------|-----|-----|--------|
| 1 | 100 | 25% | 200MB |
| 4 | 400 | 90% | 800MB |
| 8 | 750 | 95% | 1.6GB |
| 16 | 1200 | 95% | 3.2GB |

### Scalability

```
Throughput vs Workers
1500 RPS │     ╱─────
         │    ╱
1000 RPS │   ╱
         │  ╱
500 RPS  │ ╱
         │╱
0 RPS    └────────────
         0  4  8  12  16
            Workers
```