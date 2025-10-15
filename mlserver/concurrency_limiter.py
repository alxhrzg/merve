"""
Concurrency limiter for protecting compute-intensive model predictions.
Designed for Kubernetes pod deployment where scaling happens across pods.
"""
import asyncio
import threading
from typing import Optional
from fastapi import HTTPException


class PredictionSemaphore:
    """
    Semaphore to limit concurrent predictions to protect compute-intensive models.

    In Kubernetes deployments, each pod handles one prediction at a time,
    with scaling happening by adding more pods rather than handling concurrent
    requests within a single pod.
    """

    def __init__(self, max_concurrent: int = 1, timeout: float = 0):
        """
        Initialize the prediction semaphore.

        Args:
            max_concurrent: Maximum concurrent predictions (default 1 for single model protection)
            timeout: How long to wait for semaphore (0 = immediate rejection)
        """
        self._semaphore = threading.Semaphore(max_concurrent)
        self._max_concurrent = max_concurrent
        self._timeout = timeout
        self._active_predictions = 0
        self._lock = threading.Lock()

    def acquire_nowait(self) -> bool:
        """Try to acquire semaphore without waiting."""
        acquired = self._semaphore.acquire(blocking=False)
        if acquired:
            with self._lock:
                self._active_predictions += 1
        return acquired

    def release(self):
        """Release the semaphore."""
        self._semaphore.release()
        with self._lock:
            self._active_predictions -= 1

    @property
    def active_predictions(self) -> int:
        """Get current number of active predictions."""
        with self._lock:
            return self._active_predictions

    @property
    def is_available(self) -> bool:
        """Check if prediction slot is available."""
        return self._active_predictions < self._max_concurrent


class PredictionLimiter:
    """
    Context manager for limiting concurrent predictions.
    """

    def __init__(self, semaphore: PredictionSemaphore,
                 rejection_message: str = "Server is currently processing another prediction. Please retry later."):
        self._semaphore = semaphore
        self._rejection_message = rejection_message
        self._acquired = False

    def __enter__(self):
        """Acquire semaphore or raise HTTP 503 if busy."""
        self._acquired = self._semaphore.acquire_nowait()
        if not self._acquired:
            raise HTTPException(
                status_code=503,  # Service Unavailable
                detail=self._rejection_message,
                headers={"Retry-After": "5"}  # Suggest retry after 5 seconds
            )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Release semaphore if acquired."""
        if self._acquired:
            self._semaphore.release()
            self._acquired = False


class AsyncPredictionLimiter:
    """
    Async context manager for limiting concurrent predictions.
    """

    def __init__(self, semaphore: asyncio.Semaphore, max_concurrent: int = 1,
                 rejection_message: str = "Server is currently processing another prediction. Please retry later."):
        self._semaphore = semaphore
        self._max_concurrent = max_concurrent
        self._rejection_message = rejection_message
        self._acquired = False

    async def __aenter__(self):
        """Try to acquire semaphore without waiting."""
        try:
            # Try to acquire with zero timeout
            self._acquired = await asyncio.wait_for(
                self._semaphore.acquire(),
                timeout=0.001  # Near-instant timeout
            )
        except asyncio.TimeoutError:
            self._acquired = False

        if not self._acquired:
            raise HTTPException(
                status_code=503,
                detail=self._rejection_message,
                headers={"Retry-After": "5"}
            )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Release semaphore if acquired."""
        if self._acquired:
            self._semaphore.release()
            self._acquired = False


def create_prediction_limiter(max_concurrent_predictions: int = 1,
                             async_mode: bool = False) -> tuple:
    """
    Create appropriate prediction limiter based on mode.

    Args:
        max_concurrent_predictions: Max concurrent predictions (1 for single model protection)
        async_mode: Whether to use async limiter

    Returns:
        Tuple of (semaphore, limiter_class)
    """
    if async_mode:
        semaphore = asyncio.Semaphore(max_concurrent_predictions)
        return semaphore, lambda: AsyncPredictionLimiter(semaphore, max_concurrent_predictions)
    else:
        semaphore = PredictionSemaphore(max_concurrent_predictions)
        return semaphore, lambda: PredictionLimiter(semaphore)