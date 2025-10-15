"""
Locust load testing file for ML Server

Usage:
    # Start server first
    ml_server examples/config.yaml

    # Run load test
    locust -f tests/load/locustfile.py --host=http://localhost:8000

    # Or headless mode
    locust -f tests/load/locustfile.py --host=http://localhost:8000 \
           --users 10 --spawn-rate 2 --run-time 60s --headless
"""

import random
import json
from locust import HttpUser, task, between


class MLServerUser(HttpUser):
    """Simulated user for ML Server load testing"""

    # Wait between 1-3 seconds between requests
    wait_time = between(1, 3)

    def on_start(self):
        """Initialize test data when user starts"""
        # Check if server is healthy
        response = self.client.get("/healthz")
        if response.status_code != 200:
            print(f"Warning: Server health check failed: {response.status_code}")

        # Pre-generate some test data
        self.records_payloads = self._generate_records_payloads()
        self.ndarray_payloads = self._generate_ndarray_payloads()
        self.single_payloads = self._generate_single_payloads()

    def _generate_records_payloads(self):
        """Generate various records format payloads"""
        payloads = []

        # Small batch
        payloads.append({
            "payload": {
                "records": [
                    {
                        "pclass": random.choice([1, 2, 3]),
                        "sex": random.choice(["male", "female"]),
                        "age": random.uniform(1, 80),
                        "sibsp": random.randint(0, 3),
                        "parch": random.randint(0, 2),
                        "fare": random.uniform(5, 500),
                        "embarked": random.choice(["S", "C", "Q"]),
                        "who": random.choice(["man", "woman", "child"]),
                        "adult_male": random.choice([True, False]),
                        "alone": random.choice([True, False])
                    }
                    for _ in range(random.randint(1, 3))
                ]
            }
        })

        # Medium batch
        payloads.append({
            "payload": {
                "records": [
                    {
                        "pclass": random.choice([1, 2, 3]),
                        "sex": random.choice(["male", "female"]),
                        "age": random.uniform(1, 80),
                        "sibsp": random.randint(0, 3),
                        "parch": random.randint(0, 2),
                        "fare": random.uniform(5, 500),
                        "embarked": random.choice(["S", "C", "Q"]),
                        "who": random.choice(["man", "woman", "child"]),
                        "adult_male": random.choice([True, False]),
                        "alone": random.choice([True, False])
                    }
                    for _ in range(random.randint(5, 15))
                ]
            }
        })

        return payloads

    def _generate_ndarray_payloads(self):
        """Generate ndarray format payloads"""
        payloads = []

        # Small array
        payloads.append({
            "payload": {
                "ndarray": [
                    [
                        random.choice([1, 2, 3]),  # pclass
                        random.choice(["male", "female"]),  # sex
                        random.uniform(1, 80),  # age
                        random.randint(0, 3),  # sibsp
                        random.randint(0, 2),  # parch
                        random.uniform(5, 500),  # fare
                        random.choice(["S", "C", "Q"]),  # embarked
                        random.choice(["man", "woman", "child"]),  # who
                        random.choice([True, False]),  # adult_male
                        random.choice([True, False])  # alone
                    ]
                    for _ in range(random.randint(1, 5))
                ]
            }
        })

        return payloads

    def _generate_single_payloads(self):
        """Generate single record payloads"""
        payloads = []

        payloads.append({
            "payload": {
                "features": {
                    "pclass": random.choice([1, 2, 3]),
                    "sex": random.choice(["male", "female"]),
                    "age": random.uniform(1, 80),
                    "sibsp": random.randint(0, 3),
                    "parch": random.randint(0, 2),
                    "fare": random.uniform(5, 500),
                    "embarked": random.choice(["S", "C", "Q"]),
                    "who": random.choice(["man", "woman", "child"]),
                    "adult_male": random.choice([True, False]),
                    "alone": random.choice([True, False])
                }
            }
        })

        return payloads

    @task(10)
    def predict_records(self):
        """Test predict endpoint with records format (most common)"""
        payload = random.choice(self.records_payloads)

        with self.client.post(
            "/predict",
            json=payload,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "predictions" in data and "time_ms" in data:
                        response.success()
                    else:
                        response.failure("Invalid response structure")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(5)
    def predict_ndarray(self):
        """Test predict endpoint with ndarray format"""
        payload = random.choice(self.ndarray_payloads)

        with self.client.post(
            "/predict",
            json=payload,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "predictions" in data:
                        response.success()
                    else:
                        response.failure("Invalid response structure")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(3)
    def predict_single(self):
        """Test predict endpoint with single record"""
        payload = random.choice(self.single_payloads)

        with self.client.post(
            "/predict",
            json=payload,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(4)
    def predict_proba(self):
        """Test predict_proba endpoint"""
        payload = random.choice(self.records_payloads)

        with self.client.post(
            "/predict_proba",
            json=payload,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "probabilities" in data:
                        response.success()
                    else:
                        response.failure("Invalid response structure")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(2)
    def batch_predict(self):
        """Test batch predict endpoint"""
        # Generate larger batch for batch endpoint
        batch_payload = {
            "payload": {
                "records": [
                    {
                        "pclass": random.choice([1, 2, 3]),
                        "sex": random.choice(["male", "female"]),
                        "age": random.uniform(1, 80),
                        "sibsp": random.randint(0, 3),
                        "parch": random.randint(0, 2),
                        "fare": random.uniform(5, 500),
                        "embarked": random.choice(["S", "C", "Q"]),
                        "who": random.choice(["man", "woman", "child"]),
                        "adult_male": random.choice([True, False]),
                        "alone": random.choice([True, False])
                    }
                    for _ in range(random.randint(10, 50))
                ]
            }
        }

        with self.client.post(
            "/batch_predict",
            json=batch_payload,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "predictions" in data and len(data["predictions"]) > 0:
                        response.success()
                    else:
                        response.failure("Invalid batch response")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(2)
    def health_check(self):
        """Test health endpoint"""
        with self.client.get("/healthz", catch_response=True) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get("status") == "ok":
                        response.success()
                    else:
                        response.failure("Unhealthy status")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(1)
    def metrics_check(self):
        """Test metrics endpoint (if available)"""
        with self.client.get("/metrics", catch_response=True) as response:
            if response.status_code == 200:
                if "mlserver_" in response.text:
                    response.success()
                else:
                    response.failure("Invalid metrics format")
            elif response.status_code == 404:
                # Metrics might be disabled, that's ok
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")

    def test_error_handling(self):
        """Test error conditions (called less frequently)"""
        # Test invalid payload
        invalid_payloads = [
            {},  # Empty payload
            {"payload": {}},  # Empty nested payload
            {"payload": {"invalid": "format"}},  # Invalid format
            {"payload": {"records": []}},  # Empty records
        ]

        payload = random.choice(invalid_payloads)

        # These should fail gracefully (400/422, not 500)
        response = self.client.post("/predict", json=payload)
        if response.status_code in [400, 422]:
            # Expected error codes
            pass
        elif response.status_code == 500:
            print(f"Unexpected server error with payload: {payload}")

    @task(1)
    def occasional_error_test(self):
        """Occasionally test error handling"""
        if random.random() < 0.1:  # 10% chance
            self.test_error_handling()


class HighLoadUser(HttpUser):
    """High-intensity user for stress testing"""

    wait_time = between(0.1, 0.5)  # Very fast requests

    def on_start(self):
        # Simple fast payload
        self.payload = {
            "payload": {
                "records": [
                    {
                        "pclass": 1,
                        "sex": "male",
                        "age": 30,
                        "sibsp": 0,
                        "parch": 0,
                        "fare": 100,
                        "embarked": "S",
                        "who": "man",
                        "adult_male": True,
                        "alone": True
                    }
                ]
            }
        }

    @task
    def fast_predict(self):
        """Fast predictions for stress testing"""
        self.client.post("/predict", json=self.payload)


class MetricsObserver(HttpUser):
    """User that primarily observes metrics for monitoring"""

    wait_time = between(5, 10)  # Check metrics every 5-10 seconds

    @task(1)
    def observe_metrics(self):
        """Continuously observe metrics"""
        response = self.client.get("/metrics")
        if response.status_code == 200:
            # Could parse and log specific metrics
            content = response.text

            # Extract some key metrics for logging
            if "mlserver_requests_total" in content:
                # Metrics are being generated
                pass

    @task(1)
    def health_monitoring(self):
        """Monitor server health"""
        response = self.client.get("/healthz")
        if response.status_code != 200:
            print(f"Health check failed: {response.status_code}")


# Example custom user classes for different scenarios
class LightUser(MLServerUser):
    """Light usage user"""
    wait_time = between(5, 15)


class HeavyUser(MLServerUser):
    """Heavy usage user"""
    wait_time = between(0.5, 2)

    @task(20)  # Much higher weight
    def heavy_predict(self):
        """Make lots of predictions"""
        return self.predict_records()


if __name__ == "__main__":
    # This won't run when used with locust command, but useful for testing
    print("Locust file loaded. Use 'locust -f locustfile.py --host=http://localhost:8000' to start testing.")
    print("\nAvailable user types:")
    print("- MLServerUser: Balanced testing of all endpoints")
    print("- HighLoadUser: High-intensity stress testing")
    print("- MetricsObserver: Metrics monitoring")
    print("- LightUser: Light usage patterns")
    print("- HeavyUser: Heavy usage patterns")