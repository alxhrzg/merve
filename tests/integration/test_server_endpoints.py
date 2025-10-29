import pytest
import json


class TestHealthEndpoint:
    """Test health endpoint functionality"""

    async def test_health_endpoint_success(self, async_client):
        response = await async_client.get("/healthz")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ok"
        assert "model" in data
        assert data["model"] == "MockPredictor"

    async def test_health_endpoint_content_type(self, async_client):
        response = await async_client.get("/healthz")
        assert response.headers["content-type"] == "application/json"


class TestPredictEndpoint:
    """Test prediction endpoint functionality"""

    async def test_predict_records_format(self, async_client, sample_records_payload):
        response = await async_client.post("/predict", json=sample_records_payload)
        assert response.status_code == 200

        data = response.json()
        assert "predictions" in data
        assert "time_ms" in data
        assert "metadata" in data  # Updated: response now has metadata instead of model
        assert len(data["predictions"]) == 2  # Two records in sample

    async def test_predict_ndarray_format(self, async_client, sample_ndarray_payload):
        response = await async_client.post("/predict", json=sample_ndarray_payload)
        assert response.status_code == 200

        data = response.json()
        assert "predictions" in data
        assert len(data["predictions"]) == 2

    async def test_predict_single_record(self, async_client, sample_single_record_payload):
        response = await async_client.post("/predict", json=sample_single_record_payload)
        assert response.status_code == 200

        data = response.json()
        assert "predictions" in data
        assert len(data["predictions"]) == 1

    async def test_predict_empty_payload(self, async_client):
        response = await async_client.post("/predict", json={})
        assert response.status_code == 400

    async def test_predict_invalid_json(self, async_client):
        response = await async_client.post(
            "/predict",
            content="invalid json",
            headers={"content-type": "application/json"}
        )
        assert response.status_code == 422

    async def test_predict_missing_payload(self, async_client):
        response = await async_client.post("/predict", json={"data": []})
        assert response.status_code == 400

    async def test_predict_response_structure(self, async_client, sample_records_payload):
        response = await async_client.post("/predict", json=sample_records_payload)
        data = response.json()

        # Verify response structure
        assert isinstance(data["predictions"], list)
        assert isinstance(data["time_ms"], (int, float))
        assert data["time_ms"] >= 0
        # metadata is optional, so only check type if present
        if data.get("metadata") is not None:
            assert isinstance(data["metadata"], dict)

    async def test_predict_timing(self, async_client, sample_records_payload):
        response = await async_client.post("/predict", json=sample_records_payload)
        data = response.json()

        # Should have reasonable timing
        assert 0 <= data["time_ms"] <= 10000  # Less than 10 seconds


class TestPredictProbaEndpoint:
    """Test predict_proba endpoint functionality"""

    async def test_predict_proba_success(self, async_client_preprocessing, sample_records_payload):
        response = await async_client_preprocessing.post("/predict_proba", json=sample_records_payload)
        assert response.status_code == 200

        data = response.json()
        assert "probabilities" in data
        assert "time_ms" in data
        assert "metadata" in data  # Updated: response now has metadata instead of model

    async def test_predict_proba_response_structure(self, async_client_preprocessing, sample_records_payload):
        response = await async_client_preprocessing.post("/predict_proba", json=sample_records_payload)
        data = response.json()

        # Probabilities should be list of lists (for binary/multiclass)
        assert isinstance(data["probabilities"], list)
        assert len(data["probabilities"]) == 2  # Two samples

        for prob_row in data["probabilities"]:
            assert isinstance(prob_row, list)
            assert len(prob_row) >= 1  # At least one class
            # Probabilities should sum to ~1.0 for each sample
            assert abs(sum(prob_row) - 1.0) < 0.01

    async def test_predict_proba_invalid_payload(self, async_client_preprocessing):
        response = await async_client_preprocessing.post("/predict_proba", json={})
        assert response.status_code == 400

    async def test_predict_proba_predictor_without_method(self, async_client):
        # Test with basic mock predictor that might not have predict_proba
        response = await async_client.post("/predict_proba", json={
            "payload": {"records": [{"f1": 1, "f2": 2, "f3": 3, "f4": 4, "f5": 5}]}
        })
        # Should still work as MockPredictor has predict_proba
        assert response.status_code == 200


# TestBatchPredictEndpoint class REMOVED - batch_predict endpoint was removed
# The /predict endpoint now handles both single and batch predictions naturally
# See: mlserver/server.py line 473 - "batch_predict endpoint removed"


class TestErrorHandling:
    """Test error handling scenarios"""

    async def test_invalid_endpoint(self, async_client):
        response = await async_client.get("/nonexistent")
        assert response.status_code == 404

    async def test_wrong_http_method(self, async_client):
        # GET on predict endpoint
        response = await async_client.get("/predict")
        assert response.status_code == 405

    async def test_invalid_adapter_format(self, async_client):
        invalid_payload = {
            "payload": {
                "invalid_format": "this should fail"
            }
        }
        response = await async_client.post("/predict", json=invalid_payload)
        assert response.status_code == 400

    async def test_malformed_records(self, async_client):
        # Records with inconsistent keys
        malformed_payload = {
            "payload": {
                "records": [
                    {"f1": 1, "f2": 2},
                    {"f1": 1, "f3": 3}  # Different keys
                ]
            }
        }
        response = await async_client.post("/predict", json=malformed_payload)
        assert response.status_code == 400

    async def test_large_payload(self, async_client):
        # Test with very large payload
        large_payload = {
            "payload": {
                "records": [
                    {"f1": i, "f2": i, "f3": i, "f4": i, "f5": i}
                    for i in range(1000)
                ]
            }
        }
        response = await async_client.post("/predict", json=large_payload)

        # Should either succeed or fail gracefully
        assert response.status_code in [200, 400, 422, 500]
        if response.status_code == 200:
            data = response.json()
            assert len(data["predictions"]) == 1000

    async def test_prediction_error_handling(self, async_client):
        # Test payload with extreme but valid values
        # Note: float('inf') removed - not valid JSON
        edge_case_payload = {
            "payload": {
                "ndarray": [[1e308, -1e308, 0, 0, 0]]  # Very large but valid numbers
            }
        }
        response = await async_client.post("/predict", json=edge_case_payload)

        # Should handle gracefully (may return valid predictions or error)
        assert response.status_code in [200, 400, 500]


class TestConcurrency:
    """Test concurrent request handling"""

    async def test_concurrent_predictions(self, async_client, sample_records_payload):
        import asyncio

        # Make multiple concurrent requests
        tasks = []
        for _ in range(5):
            task = async_client.post("/predict", json=sample_records_payload)
            tasks.append(task)

        responses = await asyncio.gather(*tasks)

        # All should succeed
        for response in responses:
            assert response.status_code == 200
            data = response.json()
            assert len(data["predictions"]) == 2

    async def test_mixed_endpoint_concurrency(self, async_client_preprocessing, sample_records_payload):
        import asyncio

        # Mix different endpoints (batch_predict removed - /predict handles batches)
        tasks = [
            async_client_preprocessing.get("/healthz"),
            async_client_preprocessing.post("/predict", json=sample_records_payload),
            async_client_preprocessing.post("/predict_proba", json=sample_records_payload),
            async_client_preprocessing.post("/predict", json=sample_records_payload),  # Test /predict concurrency
        ]

        responses = await asyncio.gather(*tasks)

        # All should succeed
        for response in responses:
            assert response.status_code == 200


class TestFeatureOrdering:
    """Test feature ordering behavior"""

    async def test_feature_order_consistency(self, async_client_preprocessing):
        # Test that feature ordering is respected
        payload1 = {
            "payload": {
                "records": [{"f1": 1, "f2": 2, "f3": 3, "f4": 4, "f5": 5}]
            }
        }

        payload2 = {
            "payload": {
                "records": [{"f5": 5, "f4": 4, "f3": 3, "f2": 2, "f1": 1}]  # Different order
            }
        }

        response1 = await async_client_preprocessing.post("/predict", json=payload1)
        response2 = await async_client_preprocessing.post("/predict", json=payload2)

        assert response1.status_code == 200
        assert response2.status_code == 200

        # Should give same predictions (feature order should be normalized)
        data1 = response1.json()
        data2 = response2.json()
        assert data1["predictions"] == data2["predictions"]

    async def test_missing_features_error(self, async_client_preprocessing):
        # Test with missing features
        incomplete_payload = {
            "payload": {
                "records": [{"f1": 1, "f2": 2}]  # Missing f3, f4, f5
            }
        }

        response = await async_client_preprocessing.post("/predict", json=incomplete_payload)
        # Should either succeed with defaults or fail gracefully
        assert response.status_code in [200, 400, 422]


class TestResponseValidation:
    """Test response format validation"""

    async def test_predict_response_schema(self, async_client, sample_records_payload):
        response = await async_client.post("/predict", json=sample_records_payload)
        data = response.json()

        # Required fields (metadata is optional, so not in required list)
        required_fields = ["predictions", "time_ms"]
        for field in required_fields:
            assert field in data

        # Type validation
        assert isinstance(data["predictions"], list)
        assert isinstance(data["time_ms"], (int, float))

        # metadata is optional
        assert "metadata" in data
        if data["metadata"] is not None:
            assert isinstance(data["metadata"], dict)

    async def test_health_response_schema(self, async_client):
        response = await async_client.get("/healthz")
        data = response.json()

        # Required fields
        assert "status" in data
        assert data["status"] == "ok"
        assert "model" in data

    async def test_content_type_headers(self, async_client, sample_records_payload):
        response = await async_client.post("/predict", json=sample_records_payload)
        assert "application/json" in response.headers["content-type"]