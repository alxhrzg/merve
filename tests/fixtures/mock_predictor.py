"""
Mock predictor for concurrency control testing.
"""
import time
import numpy as np


class MockPredictor:
    """A test predictor that simulates prediction time for concurrency testing."""

    def __init__(self, delay_seconds: float = 2.0):
        """Initialize the test predictor.

        Args:
            delay_seconds: How long to sleep during prediction to test concurrency
        """
        self.delay_seconds = delay_seconds

    def predict(self, X):
        """Make predictions with artificial delay to test concurrency."""
        # Simulate processing time to test concurrency control
        time.sleep(self.delay_seconds)

        if hasattr(X, 'shape'):
            n_samples = X.shape[0]
        else:
            n_samples = len(X)

        # Return dummy predictions (all 1s)
        return np.ones(n_samples, dtype=int)

    def predict_proba(self, X):
        """Make probability predictions."""
        time.sleep(self.delay_seconds)

        if hasattr(X, 'shape'):
            n_samples = X.shape[0]
        else:
            n_samples = len(X)

        # Return dummy probabilities (50/50)
        return np.full((n_samples, 2), 0.5)