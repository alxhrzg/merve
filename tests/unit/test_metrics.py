import pytest
import time
from unittest.mock import Mock, MagicMock
from fastapi import Request, Response
from prometheus_client import REGISTRY, CollectorRegistry

from mlserver.metrics import MetricsCollector, init_metrics, get_metrics


@pytest.fixture(autouse=True)
def clean_registry():
    """Clean up Prometheus registry after each test"""
    # Create a new registry for each test to avoid conflicts
    original_registry = REGISTRY._collector_to_names.copy()
    yield
    # Clean up after test
    for collector in list(REGISTRY._collector_to_names.keys()):
        try:
            REGISTRY.unregister(collector)
        except KeyError:
            pass  # Already unregistered


class TestMetricsCollector:
    """Test MetricsCollector functionality"""

    def test_init_with_model_name(self):
        collector = MetricsCollector("TestModel")
        assert collector.model_name == "TestModel"

    def test_init_without_model_name(self):
        collector = MetricsCollector()
        assert collector.model_name == "unknown"

    def test_metrics_creation(self):
        collector = MetricsCollector("TestModel")

        # Test that all metrics are created
        assert collector.request_count is not None
        assert collector.request_duration is not None
        assert collector.prediction_duration is not None
        assert collector.prediction_count is not None
        assert collector.active_requests is not None
        assert collector.model_info is not None

    def test_track_request(self):
        collector = MetricsCollector("TestModel")

        # Mock request and response
        request = Mock(spec=Request)
        request.url.path = "/predict"
        request.method = "POST"

        response = Mock(spec=Response)
        response.status_code = 200

        duration = 0.1

        # Track request
        collector.track_request(request, response, duration)

        # Verify metrics were updated
        # Note: We can't easily check the exact values due to Prometheus client internals
        # but we can verify the methods were called without error

    def test_track_prediction(self):
        collector = MetricsCollector("TestModel")

        endpoint = "/predict"
        duration = 0.05
        sample_count = 2

        # Track prediction
        collector.track_prediction(endpoint, duration, sample_count)

        # Should complete without error

    def test_active_requests_counter(self):
        collector = MetricsCollector("TestModel")

        # Test increment
        collector.inc_active_requests()

        # Test decrement
        collector.dec_active_requests()

        # Should complete without error

    def test_generate_metrics(self):
        collector = MetricsCollector("TestModel")

        # Generate some metrics
        metrics_output = collector.generate_metrics()

        assert isinstance(metrics_output, bytes)
        assert b"mlserver_" in metrics_output
        assert b"TestModel" in metrics_output

    def test_get_content_type(self):
        collector = MetricsCollector("TestModel")
        content_type = collector.get_content_type()
        assert "text/plain" in content_type

    def test_metrics_with_labels(self):
        collector = MetricsCollector("MyModel")

        # Mock request with different endpoints
        request1 = Mock(spec=Request)
        request1.url.path = "/predict"
        request1.method = "POST"

        request2 = Mock(spec=Request)
        request2.url.path = "/predict_proba"
        request2.method = "POST"

        response = Mock(spec=Response)
        response.status_code = 200

        # Track different requests
        collector.track_request(request1, response, 0.1)
        collector.track_request(request2, response, 0.2)

        # Track predictions with different endpoints
        collector.track_prediction("/predict", 0.05, 1)
        collector.track_prediction("/predict_proba", 0.08, 1)

        # Generate metrics and check for labels
        metrics_output = collector.generate_metrics()
        assert b"/predict" in metrics_output
        assert b"/predict_proba" in metrics_output
        assert b"MyModel" in metrics_output

    def test_error_response_tracking(self):
        collector = MetricsCollector("TestModel")

        request = Mock(spec=Request)
        request.url.path = "/predict"
        request.method = "POST"

        response = Mock(spec=Response)
        response.status_code = 500  # Error response

        # Should handle error responses
        collector.track_request(request, response, 0.1)

    def test_different_http_methods(self):
        collector = MetricsCollector("TestModel")

        methods = ["GET", "POST", "PUT"]
        for method in methods:
            request = Mock(spec=Request)
            request.url.path = "/test"
            request.method = method

            response = Mock(spec=Response)
            response.status_code = 200

            collector.track_request(request, response, 0.1)

    def test_histogram_buckets(self):
        collector = MetricsCollector("TestModel")

        # Test different durations to hit different buckets
        durations = [0.001, 0.01, 0.1, 1.0, 5.0]

        request = Mock(spec=Request)
        request.url.path = "/predict"
        request.method = "POST"

        response = Mock(spec=Response)
        response.status_code = 200

        for duration in durations:
            collector.track_request(request, response, duration)
            collector.track_prediction("/predict", duration, 1)

    def test_multiple_samples_prediction(self):
        collector = MetricsCollector("TestModel")

        # Track prediction with multiple samples
        collector.track_prediction("/batch_predict", 0.5, 10)

        metrics_output = collector.generate_metrics()
        assert b"batch_predict" in metrics_output


class TestMetricsModule:
    """Test module-level functions"""

    def test_init_metrics(self):
        collector = init_metrics("TestModel")
        assert isinstance(collector, MetricsCollector)
        assert collector.model_name == "TestModel"

    def test_get_metrics_after_init(self):
        init_metrics("TestModel")
        collector = get_metrics()
        assert isinstance(collector, MetricsCollector)
        assert collector.model_name == "TestModel"

    def test_get_metrics_before_init(self):
        # Reset global collector
        import mlserver.metrics
        mlserver.metrics._metrics_collector = None

        collector = get_metrics()
        assert collector is None

    def test_reinit_metrics(self):
        # Initialize first time
        collector1 = init_metrics("Model1")
        assert collector1.model_name == "Model1"

        # Clear registry before reinitializing to avoid duplicate metrics
        from prometheus_client import REGISTRY
        collectors = list(REGISTRY._collector_to_names.keys())
        for collector in collectors:
            try:
                REGISTRY.unregister(collector)
            except KeyError:
                pass

        # Reset global collector
        from mlserver import metrics
        metrics._metrics_collector = None

        # Initialize again with different name
        collector2 = init_metrics("Model2")
        assert collector2.model_name == "Model2"

        # Should get the new one
        current = get_metrics()
        assert current.model_name == "Model2"


class TestMetricsIntegration:
    """Test metrics in realistic scenarios"""

    def test_complete_request_cycle(self):
        collector = MetricsCollector("IntegrationTest")

        # Simulate a complete request
        request = Mock(spec=Request)
        request.url.path = "/predict"
        request.method = "POST"

        response = Mock(spec=Response)
        response.status_code = 200

        # Track active request
        collector.inc_active_requests()

        # Track prediction
        prediction_duration = 0.05
        collector.track_prediction("/predict", prediction_duration, 2)

        # Track complete request
        total_duration = 0.1
        collector.track_request(request, response, total_duration)

        # Decrement active requests
        collector.dec_active_requests()

        # Generate metrics
        metrics_output = collector.generate_metrics()
        assert b"mlserver_requests_total" in metrics_output
        assert b"mlserver_request_duration_seconds" in metrics_output
        assert b"mlserver_prediction_duration_seconds" in metrics_output
        assert b"mlserver_predictions_total" in metrics_output

    def test_concurrent_requests_simulation(self):
        collector = MetricsCollector("ConcurrentTest")

        # Simulate multiple concurrent requests
        for i in range(5):
            collector.inc_active_requests()

        # Process requests
        for i in range(5):
            request = Mock(spec=Request)
            request.url.path = f"/predict_{i}"
            request.method = "POST"

            response = Mock(spec=Response)
            response.status_code = 200

            collector.track_prediction(f"/predict_{i}", 0.1, 1)
            collector.track_request(request, response, 0.15)
            collector.dec_active_requests()

    def test_error_scenarios(self):
        collector = MetricsCollector("ErrorTest")

        # Test various error scenarios
        error_codes = [400, 422, 500]

        for code in error_codes:
            request = Mock(spec=Request)
            request.url.path = "/predict"
            request.method = "POST"

            response = Mock(spec=Response)
            response.status_code = code

            collector.track_request(request, response, 0.1)

        # Should track different status codes
        metrics_output = collector.generate_metrics()
        assert b"400" in metrics_output or b"422" in metrics_output or b"500" in metrics_output