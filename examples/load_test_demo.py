#!/usr/bin/env python3
"""
Live Metrics Demo Script

This script demonstrates live metrics collection by continuously hammering
the ML server with requests while displaying real-time metrics.

Usage:
    1. Start the ML server:
       ml_server examples/config.yaml

    2. Run this script:
       python examples/load_test_demo.py

    3. Open Prometheus metrics in browser:
       http://localhost:8000/metrics

    4. Optional: Set up monitoring stack:
       docker-compose -f docker-compose.monitoring.yml up -d
       - Prometheus: http://localhost:9090
       - Grafana: http://localhost:3000
"""

import asyncio
import aiohttp
import random
import time
import json
import argparse
import signal
import sys
from typing import Dict, List, Any
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime


class LoadTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = None
        self.running = False
        self.stats = {
            "requests_sent": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_response_time": 0,
            "start_time": time.time()
        }

    async def create_session(self):
        """Create aiohttp session"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            connector=aiohttp.TCPConnector(limit=100)
        )

    async def close_session(self):
        """Close aiohttp session"""
        if self.session:
            await self.session.close()

    def generate_sample_data(self) -> Dict[str, Any]:
        """Generate random sample data for predictions"""
        return {
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
                    for _ in range(random.randint(1, 5))
                ]
            }
        }

    async def make_prediction_request(self, endpoint: str = "/v1/test-classifier/predict") -> Dict[str, Any]:
        """Make a single prediction request"""
        if not self.session:
            await self.create_session()

        payload = self.generate_sample_data()
        start_time = time.time()

        try:
            async with self.session.post(
                f"{self.base_url}{endpoint}",
                json=payload
            ) as response:
                response_time = time.time() - start_time

                self.stats["requests_sent"] += 1
                self.stats["total_response_time"] += response_time

                if response.status == 200:
                    self.stats["successful_requests"] += 1
                    result = await response.json()
                    return {
                        "success": True,
                        "status_code": response.status,
                        "response_time": response_time,
                        "predictions": len(result.get("predictions", [])),
                        "server_time_ms": result.get("time_ms", 0)
                    }
                else:
                    self.stats["failed_requests"] += 1
                    return {
                        "success": False,
                        "status_code": response.status,
                        "response_time": response_time,
                        "error": await response.text()
                    }

        except Exception as e:
            self.stats["requests_sent"] += 1
            self.stats["failed_requests"] += 1
            return {
                "success": False,
                "error": str(e),
                "response_time": time.time() - start_time
            }

    async def get_metrics(self) -> str:
        """Fetch current Prometheus metrics"""
        if not self.session:
            await self.create_session()

        try:
            async with self.session.get(f"{self.base_url}/metrics") as response:
                if response.status == 200:
                    return await response.text()
                else:
                    return f"Error fetching metrics: {response.status}"
        except Exception as e:
            return f"Error fetching metrics: {e}"

    async def check_health(self) -> Dict[str, Any]:
        """Check server health"""
        if not self.session:
            await self.create_session()

        try:
            async with self.session.get(f"{self.base_url}/healthz") as response:
                if response.status == 200:
                    data = await response.json()
                    return {"healthy": True, "data": data}
                else:
                    return {"healthy": False, "status_code": response.status}
        except Exception as e:
            return {"healthy": False, "error": str(e)}

    def parse_metrics(self, metrics_text: str) -> Dict[str, Any]:
        """Parse key metrics from Prometheus format"""
        parsed = {}

        for line in metrics_text.split('\n'):
            if line.startswith('mlserver_requests_total'):
                # Extract request counts by endpoint and status
                if ('endpoint="/v1/' in line and '/predict"' in line and 'status_code="200"' in line):
                    try:
                        value = float(line.split()[-1])
                        parsed['successful_predictions'] = value
                    except:
                        pass
            elif line.startswith('mlserver_predictions_total'):
                # Total predictions made
                try:
                    value = float(line.split()[-1])
                    parsed['total_predictions'] = value
                except:
                    pass
            elif line.startswith('mlserver_active_requests'):
                # Active requests
                try:
                    value = float(line.split()[-1])
                    parsed['active_requests'] = value
                except:
                    pass

        return parsed

    async def continuous_load_worker(self, worker_id: int, requests_per_second: float):
        """Worker that continuously makes requests"""
        print(f"Starting worker {worker_id} with {requests_per_second} RPS")

        # Add random startup delay to prevent initial burst
        startup_delay = random.uniform(0, 0.5) * worker_id  # Stagger based on worker ID
        if startup_delay > 0:
            await asyncio.sleep(startup_delay)

        delay = 1.0 / requests_per_second if requests_per_second > 0 else 0.1

        while self.running:
            # Random endpoint selection
            # Try to detect endpoint from server
            # For now, use common endpoint pattern
            # Note: batch_predict removed - /predict handles both single and batch
            endpoint = "/v1/titanic-survival-predictor/predict"

            result = await self.make_prediction_request(endpoint)

            if not result["success"]:
                print(f"Worker {worker_id} request failed: {result.get('error', 'Unknown error')}")

            await asyncio.sleep(delay + random.uniform(0, 0.1))

    async def metrics_monitor(self, interval: int = 5):
        """Monitor and display metrics periodically"""
        print("\n=== Metrics Monitor Started ===")

        while self.running:
            try:
                # Get current metrics
                metrics_text = await self.get_metrics()
                parsed_metrics = self.parse_metrics(metrics_text)

                # Calculate our own stats
                elapsed = time.time() - self.stats["start_time"]
                avg_response_time = (
                    self.stats["total_response_time"] / max(self.stats["requests_sent"], 1)
                ) * 1000  # Convert to ms

                success_rate = (
                    self.stats["successful_requests"] / max(self.stats["requests_sent"], 1)
                ) * 100

                current_rps = self.stats["requests_sent"] / max(elapsed, 1)

                # Display dashboard
                print(f"\n{'=' * 60}")
                print(f"⏰ Time: {datetime.now().strftime('%H:%M:%S')} | Elapsed: {elapsed:.1f}s")
                print(f"📊 Load Test Stats:")
                print(f"   Requests Sent: {self.stats['requests_sent']}")
                print(f"   Success Rate: {success_rate:.1f}%")
                print(f"   Avg Response Time: {avg_response_time:.1f}ms")
                print(f"   Current RPS: {current_rps:.1f}")

                print(f"📈 Server Metrics:")
                for key, value in parsed_metrics.items():
                    print(f"   {key.replace('_', ' ').title()}: {value}")

                print(f"🔗 Metrics URL: {self.base_url}/metrics")
                print(f"{'=' * 60}")

            except Exception as e:
                print(f"Error in metrics monitor: {e}")

            await asyncio.sleep(interval)

    async def run_load_test(
        self,
        duration: int = 60,
        workers: int = 3,
        requests_per_second: float = 2.0,
        monitor_interval: int = 5
    ):
        """Run the complete load test"""

        print(f"\n🚀 Starting Live Metrics Demo")
        print(f"Target URL: {self.base_url}")
        print(f"Duration: {duration}s")
        print(f"Workers: {workers}")
        print(f"Target RPS per worker: {requests_per_second}")
        print(f"Monitor interval: {monitor_interval}s")

        # Check server health first
        health = await self.check_health()
        if not health["healthy"]:
            print(f"❌ Server health check failed: {health}")
            return False

        print(f"✅ Server healthy: {health['data']}")

        self.running = True

        try:
            # Start all tasks
            tasks = []

            # Start worker tasks
            for i in range(workers):
                task = asyncio.create_task(
                    self.continuous_load_worker(i, requests_per_second)
                )
                tasks.append(task)

            # Start metrics monitor
            monitor_task = asyncio.create_task(
                self.metrics_monitor(monitor_interval)
            )
            tasks.append(monitor_task)

            # Run for specified duration
            await asyncio.sleep(duration)

        except KeyboardInterrupt:
            print("\n⏹️ Interrupted by user")
        finally:
            print("\n🛑 Stopping load test...")
            self.running = False

            # Cancel all tasks
            for task in tasks:
                task.cancel()

            # Wait for tasks to complete
            await asyncio.gather(*tasks, return_exceptions=True)

            # Final metrics display
            await self.display_final_stats()

        return True

    async def display_final_stats(self):
        """Display final statistics"""
        elapsed = time.time() - self.stats["start_time"]
        avg_rps = self.stats["requests_sent"] / max(elapsed, 1)
        avg_response_time = (
            self.stats["total_response_time"] / max(self.stats["requests_sent"], 1)
        ) * 1000

        print(f"\n📊 Final Statistics:")
        print(f"   Total Runtime: {elapsed:.1f}s")
        print(f"   Total Requests: {self.stats['requests_sent']}")
        print(f"   Successful: {self.stats['successful_requests']}")
        print(f"   Failed: {self.stats['failed_requests']}")
        print(f"   Success Rate: {(self.stats['successful_requests'] / max(self.stats['requests_sent'], 1)) * 100:.1f}%")
        print(f"   Average RPS: {avg_rps:.1f}")
        print(f"   Average Response Time: {avg_response_time:.1f}ms")

        # Get final metrics
        try:
            final_metrics = await self.get_metrics()
            parsed = self.parse_metrics(final_metrics)
            print(f"\n📈 Final Server Metrics:")
            for key, value in parsed.items():
                print(f"   {key.replace('_', ' ').title()}: {value}")
        except Exception as e:
            print(f"   Could not fetch final metrics: {e}")


def setup_signal_handler(load_tester):
    """Setup signal handler for graceful shutdown"""
    def signal_handler(signum, frame):
        print(f"\n🔔 Received signal {signum}")
        load_tester.running = False

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


async def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="ML Server Load Test Demo")
    parser.add_argument("--url", default="http://localhost:8000",
                       help="Base URL of ML server")
    parser.add_argument("--duration", type=int, default=60,
                       help="Duration of test in seconds")
    parser.add_argument("--workers", type=int, default=3,
                       help="Number of worker coroutines")
    parser.add_argument("--rps", type=float, default=2.0,
                       help="Requests per second per worker")
    parser.add_argument("--monitor-interval", type=int, default=5,
                       help="Metrics monitoring interval in seconds")

    args = parser.parse_args()

    load_tester = LoadTester(args.url)
    setup_signal_handler(load_tester)

    try:
        await load_tester.create_session()
        success = await load_tester.run_load_test(
            duration=args.duration,
            workers=args.workers,
            requests_per_second=args.rps,
            monitor_interval=args.monitor_interval
        )

        if success:
            print("\n✅ Load test completed successfully")
            print(f"\n💡 Pro Tips:")
            print(f"   • View live metrics: {args.url}/metrics")
            print(f"   • Set up Prometheus: docker-compose -f docker-compose.monitoring.yml up -d")
            print(f"   • Prometheus UI: http://localhost:9090")
            print(f"   • Grafana dashboards: http://localhost:3000")
        else:
            print("\n❌ Load test failed")
            return 1

    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        return 1
    finally:
        await load_tester.close_session()

    return 0


if __name__ == "__main__":
    print("🔥 ML Server Live Metrics Demo")
    print("Press Ctrl+C to stop at any time\n")

    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n👋 Demo stopped by user")
        sys.exit(0)