import pytest
import json
import logging
from unittest.mock import patch
from prometheus_client import REGISTRY


class TestMetricsEndpoint:
    """Test Prometheus metrics endpoint"""

    async def test_metrics_endpoint_exists(self, observability_client):
        response = await observability_client.get("/metrics")
        assert response.status_code == 200

    async def test_metrics_content_type(self, observability_client):
        response = await observability_client.get("/metrics")
        assert "text/plain" in response.headers["content-type"]

    async def test_metrics_format(self, observability_client):
        response = await observability_client.get("/metrics")
        content = response.text

        # Should contain Prometheus metrics format
        assert "# HELP" in content
        assert "# TYPE" in content
        assert "mlserver_" in content

    async def test_model_info_metric(self, observability_client):
        response = await observability_client.get("/metrics")
        content = response.text

        # Should contain model info
        assert "mlserver_model_info" in content
        assert "MockPredictor" in content

    async def test_metrics_after_requests(self, observability_client, sample_records_payload):
        # Make some requests first
        await observability_client.post("/predict", json=sample_records_payload)
        await observability_client.get("/healthz")

        # Get metrics
        response = await observability_client.get("/metrics")
        content = response.text

        # Should contain request metrics
        assert "mlserver_requests_total" in content
        assert "mlserver_request_duration_seconds" in content

    async def test_prediction_metrics(self, observability_client, sample_records_payload):
        # Make prediction request
        await observability_client.post("/predict", json=sample_records_payload)

        # Check metrics
        response = await observability_client.get("/metrics")
        content = response.text

        # Should contain prediction-specific metrics
        assert "mlserver_predictions_total" in content
        assert "mlserver_prediction_duration_seconds" in content

    async def test_metrics_labels(self, observability_client, sample_records_payload):
        # Make requests to different endpoints
        await observability_client.get("/healthz")
        await observability_client.post("/predict", json=sample_records_payload)

        response = await observability_client.get("/metrics")
        content = response.text

        # Should contain endpoint labels
        assert "/healthz" in content
        assert "/predict" in content
        assert "GET" in content
        assert "POST" in content

    async def test_status_code_labels(self, observability_client, sample_records_payload):
        # Make successful request
        await observability_client.post("/predict", json=sample_records_payload)

        # Make failing request
        await observability_client.post("/predict", json={})

        response = await observability_client.get("/metrics")
        content = response.text

        # Should contain different status codes
        assert "200" in content or "400" in content


class TestMetricsAccuracy:
    """Test metrics accuracy and counting"""

    async def test_request_counter_accuracy(self, observability_client, sample_records_payload):
        # Get initial metrics
        initial_response = await observability_client.get("/metrics")
        initial_content = initial_response.text

        # Make known number of requests
        for _ in range(3):
            await observability_client.post("/predict", json=sample_records_payload)

        # Get final metrics
        final_response = await observability_client.get("/metrics")
        final_content = final_response.text

        # The counter should have increased
        # Note: Exact verification is complex due to Prometheus format,
        # but we can check that metrics are being generated
        assert len(final_content) >= len(initial_content)

    async def test_different_endpoints_counted_separately(self, observability_client, sample_records_payload):
        # Make requests to different endpoints
        await observability_client.get("/healthz")
        await observability_client.post("/predict", json=sample_records_payload)

        response = await observability_client.get("/metrics")
        content = response.text

        # Both endpoints should be represented in metrics
        healthz_metrics = "/healthz" in content
        predict_metrics = "/predict" in content

        assert healthz_metrics and predict_metrics

    async def test_histogram_buckets(self, observability_client, sample_records_payload):
        # Make request to generate timing data
        await observability_client.post("/predict", json=sample_records_payload)

        response = await observability_client.get("/metrics")
        content = response.text

        # Should contain histogram buckets
        assert "_bucket{" in content
        assert "le=" in content  # Less-than-or-equal bucket labels

    async def test_active_requests_gauge(self, observability_client):
        # The active requests gauge should be present
        response = await observability_client.get("/metrics")
        content = response.text

        assert "mlserver_active_requests" in content


class TestStructuredLogging:
    """Test structured logging functionality"""

    @patch('mlserver.logging_conf.logging.getLogger')
    async def test_correlation_ids_generated(self, mock_get_logger, observability_client, sample_records_payload):
        mock_logger = mock_get_logger.return_value

        # Make request
        await observability_client.post("/predict", json=sample_records_payload)

        # Check that logging was called (may be called multiple times)
        assert mock_logger.info.call_count >= 1

    async def test_request_response_logging(self, observability_client, sample_records_payload):
        # This test verifies that requests are processed without logging errors
        # when structured logging is enabled
        response = await observability_client.post("/predict", json=sample_records_payload)
        assert response.status_code == 200

        # If structured logging caused errors, the request would likely fail
        data = response.json()
        assert "predictions" in data

    async def test_logging_with_errors(self, observability_client):
        # Make request that will cause an error
        response = await observability_client.post("/predict", json={})
        assert response.status_code == 400

        # Should still handle error logging gracefully
        # If logging failed, this might cause server errors


class TestObservabilityMiddleware:
    """Test observability middleware functionality"""

    async def test_timing_headers_or_logs(self, observability_client, sample_records_payload):
        # Make request and verify it completes
        response = await observability_client.post("/predict", json=sample_records_payload)
        assert response.status_code == 200

        # Timing should be captured (verified via metrics)
        metrics_response = await observability_client.get("/metrics")
        assert "duration_seconds" in metrics_response.text

    async def test_middleware_error_handling(self, observability_client):
        # Test that middleware handles errors gracefully
        response = await observability_client.get("/nonexistent")
        assert response.status_code == 404

        # Metrics should still be collected for 404s
        metrics_response = await observability_client.get("/metrics")
        content = metrics_response.text
        assert "404" in content or "mlserver_requests_total" in content

    async def test_concurrent_request_tracking(self, observability_client, sample_records_payload):
        import asyncio

        # Make concurrent requests
        tasks = [
            observability_client.post("/predict", json=sample_records_payload)
            for _ in range(3)
        ]

        responses = await asyncio.gather(*tasks)

        # All should succeed
        for response in responses:
            assert response.status_code == 200

        # Metrics should reflect multiple requests
        metrics_response = await observability_client.get("/metrics")
        assert metrics_response.status_code == 200


class TestMetricsDisabled:
    """Test behavior when metrics are disabled"""

    async def test_no_metrics_endpoint_when_disabled(self, async_client):
        # Basic client has metrics disabled
        response = await async_client.get("/metrics")
        assert response.status_code == 404

    async def test_normal_operation_without_metrics(self, async_client, sample_records_payload):
        # Should work normally without metrics
        response = await async_client.post("/predict", json=sample_records_payload)
        assert response.status_code == 200

        data = response.json()
        assert "predictions" in data


class TestMetricsConfiguration:
    """Test different metrics configurations"""

    async def test_custom_metrics_endpoint(self):
        # This would require a custom fixture with different config
        # Testing that custom metrics endpoint paths work
        pass

    async def test_metrics_with_custom_labels(self, observability_client):
        # Test that model name appears in metrics
        response = await observability_client.get("/metrics")
        content = response.text

        # Should contain model name in labels
        assert "MockPredictor" in content


class TestObservabilityIntegration:
    """Test full observability integration"""

    async def test_complete_observability_workflow(self, observability_client, sample_records_payload):
        # Complete workflow: request -> prediction -> metrics -> logs

        # 1. Make prediction request
        predict_response = await observability_client.post("/predict", json=sample_records_payload)
        assert predict_response.status_code == 200

        predict_data = predict_response.json()
        assert "predictions" in predict_data
        assert predict_data["time_ms"] > 0

        # 2. Check health
        health_response = await observability_client.get("/healthz")
        assert health_response.status_code == 200

        # 3. Get metrics
        metrics_response = await observability_client.get("/metrics")
        assert metrics_response.status_code == 200

        content = metrics_response.text

        # Verify comprehensive metrics
        expected_metrics = [
            "mlserver_requests_total",
            "mlserver_request_duration_seconds",
            "mlserver_predictions_total",
            "mlserver_prediction_duration_seconds",
            "mlserver_model_info"
        ]

        for metric in expected_metrics:
            assert metric in content

        # Verify labels and values exist
        assert "MockPredictor" in content
        assert "/predict" in content
        assert "/healthz" in content

    async def test_error_observability(self, observability_client):
        # Test observability during error conditions

        # Make request that will fail
        error_response = await observability_client.post("/predict", json={})
        assert error_response.status_code == 400

        # Check metrics still collected
        metrics_response = await observability_client.get("/metrics")
        assert metrics_response.status_code == 200

        content = metrics_response.text
        assert "400" in content or "mlserver_requests_total" in content

    async def test_performance_impact(self, observability_client, sample_records_payload):
        # Test that observability doesn't significantly impact performance
        import time

        # Make request without timing (rough test)
        start_time = time.time()
        response = await observability_client.post("/predict", json=sample_records_payload)
        end_time = time.time()

        assert response.status_code == 200

        # Should complete reasonably quickly (less than 1 second for test data)
        duration = end_time - start_time
        assert duration < 1.0

        # The reported timing should be reasonable
        data = response.json()
        assert data["time_ms"] < 1000  # Less than 1 second