from __future__ import annotations
import time
from typing import Optional
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Request, Response


class MetricsCollector:
    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or "unknown"

        # Request metrics
        self.request_count = Counter(
            "mlserver_requests_total",
            "Total number of requests",
            ["method", "endpoint", "status_code", "model"]
        )


        self.request_duration = Histogram(
            "mlserver_request_duration_seconds",
            "Request duration in seconds",
            ["method", "endpoint", "model"],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        )

        # Prediction-specific metrics
        self.prediction_duration = Histogram(
            "mlserver_prediction_duration_seconds",
            "Model prediction duration in seconds",
            ["model", "endpoint"],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
        )

        self.prediction_count = Counter(
            "mlserver_predictions_total",
            "Total number of predictions made",
            ["model", "endpoint"]
        )

        # System metrics
        self.active_requests = Gauge(
            "mlserver_active_requests",
            "Number of active requests",
            ["model"]
        )

        # Model info
        self.model_info = Gauge(
            "mlserver_model_info",
            "Model information",
            ["model", "version"]
        )
        self.model_info.labels(model=self.model_name, version="1.0").set(1)

    def track_request(self, request: Request, response: Response, duration: float):
        """Track general request metrics"""
        endpoint = request.url.path
        method = request.method
        status_code = str(response.status_code)

        self.request_count.labels(
            method=method,
            endpoint=endpoint,
            status_code=status_code,
            model=self.model_name
        ).inc()

        self.request_duration.labels(
            method=method,
            endpoint=endpoint,
            model=self.model_name
        ).observe(duration)

    def track_prediction(self, endpoint: str, duration: float, sample_count: int = 1):
        """Track prediction-specific metrics"""
        self.prediction_duration.labels(
            model=self.model_name,
            endpoint=endpoint
        ).observe(duration)

        self.prediction_count.labels(
            model=self.model_name,
            endpoint=endpoint
        ).inc(sample_count)

    def inc_active_requests(self):
        """Increment active requests counter"""
        self.active_requests.labels(model=self.model_name).inc()

    def dec_active_requests(self):
        """Decrement active requests counter"""
        self.active_requests.labels(model=self.model_name).dec()

    def generate_metrics(self) -> str:
        """Generate Prometheus metrics in text format"""
        return generate_latest()

    def get_content_type(self) -> str:
        """Get the content type for metrics response"""
        return CONTENT_TYPE_LATEST


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None


def init_metrics(model_name: Optional[str] = None) -> MetricsCollector:
    """Initialize global metrics collector"""
    global _metrics_collector
    _metrics_collector = MetricsCollector(model_name)
    return _metrics_collector


def get_metrics() -> Optional[MetricsCollector]:
    """Get global metrics collector instance"""
    return _metrics_collector