"""
Stress Testing Framework

Comprehensive stress testing for the QUAN collections system:
1. Volume testing (high throughput)
2. Latency testing (response times)
3. Failure injection (chaos engineering)
4. Resource exhaustion testing
5. Concurrent load testing
6. Data consistency testing
7. Recovery testing
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any, Callable
import asyncio
import random
import time
from collections import defaultdict
import hashlib


class StressTestType(Enum):
    """Types of stress tests"""
    VOLUME = "volume"              # High volume throughput
    LATENCY = "latency"            # Response time under load
    SPIKE = "spike"                # Sudden load spike
    SOAK = "soak"                  # Extended duration
    CHAOS = "chaos"                # Random failures
    RESOURCE = "resource"          # Resource exhaustion
    CONCURRENT = "concurrent"       # Concurrent operations
    RECOVERY = "recovery"          # Failure recovery


class TestStatus(Enum):
    """Test execution status"""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"


@dataclass
class StressTestConfig:
    """Configuration for a stress test"""
    test_id: str
    test_type: StressTestType
    name: str
    description: str

    # Load configuration
    target_rps: int = 100          # Requests per second
    duration_seconds: int = 60     # Test duration
    ramp_up_seconds: int = 10      # Ramp up time
    concurrent_users: int = 10     # Simulated users

    # Thresholds
    max_latency_ms: float = 500    # Maximum acceptable latency
    max_error_rate: float = 0.01   # Maximum error rate (1%)
    min_throughput: int = 80       # Minimum throughput (% of target)

    # Chaos configuration
    failure_rate: float = 0.0      # Injected failure rate
    failure_types: list[str] = field(default_factory=list)


@dataclass
class StressTestResult:
    """Results from a stress test"""
    test_id: str
    test_type: StressTestType
    status: TestStatus

    # Timing
    started_at: datetime
    completed_at: datetime
    duration_seconds: float

    # Throughput metrics
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    actual_rps: float = 0.0

    # Latency metrics
    avg_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    max_latency_ms: float = 0.0

    # Error metrics
    error_rate: float = 0.0
    errors_by_type: dict[str, int] = field(default_factory=dict)

    # Resource metrics
    peak_memory_mb: float = 0.0
    peak_cpu_percent: float = 0.0

    # Assertions
    assertions_passed: int = 0
    assertions_failed: int = 0
    failure_reasons: list[str] = field(default_factory=list)


@dataclass
class LoadGenerator:
    """Generates load for stress testing"""
    name: str
    request_fn: Callable
    weight: float = 1.0


class LatencyTracker:
    """Tracks latency statistics"""

    def __init__(self):
        self.latencies: list[float] = []
        self.start_times: dict[str, float] = {}

    def start(self, request_id: str) -> None:
        """Start timing a request"""
        self.start_times[request_id] = time.time()

    def end(self, request_id: str) -> float:
        """End timing and record latency"""
        if request_id not in self.start_times:
            return 0.0

        latency = (time.time() - self.start_times[request_id]) * 1000  # ms
        self.latencies.append(latency)
        del self.start_times[request_id]
        return latency

    def get_statistics(self) -> dict[str, float]:
        """Get latency statistics"""
        if not self.latencies:
            return {}

        sorted_latencies = sorted(self.latencies)
        n = len(sorted_latencies)

        return {
            "count": n,
            "avg": sum(self.latencies) / n,
            "min": sorted_latencies[0],
            "max": sorted_latencies[-1],
            "p50": sorted_latencies[int(n * 0.50)],
            "p95": sorted_latencies[int(n * 0.95)],
            "p99": sorted_latencies[int(n * 0.99)] if n >= 100 else sorted_latencies[-1]
        }

    def reset(self) -> None:
        """Reset tracker"""
        self.latencies = []
        self.start_times = {}


class ChaosInjector:
    """Injects failures for chaos testing"""

    def __init__(self, failure_rate: float = 0.05):
        self.failure_rate = failure_rate
        self.enabled = False
        self.injected_failures: list[dict[str, Any]] = []
        self.failure_types = [
            "network_timeout",
            "service_unavailable",
            "database_error",
            "rate_limit",
            "invalid_response"
        ]

    def enable(self) -> None:
        """Enable chaos injection"""
        self.enabled = True

    def disable(self) -> None:
        """Disable chaos injection"""
        self.enabled = False

    def maybe_inject(self, request_id: str) -> tuple[bool, str | None]:
        """Maybe inject a failure"""
        if not self.enabled:
            return False, None

        if random.random() < self.failure_rate:
            failure_type = random.choice(self.failure_types)
            self.injected_failures.append({
                "request_id": request_id,
                "failure_type": failure_type,
                "timestamp": datetime.now().isoformat()
            })
            return True, failure_type

        return False, None

    def get_injection_stats(self) -> dict[str, Any]:
        """Get injection statistics"""
        by_type: dict[str, int] = defaultdict(int)
        for failure in self.injected_failures:
            by_type[failure["failure_type"]] += 1

        return {
            "total_injected": len(self.injected_failures),
            "by_type": dict(by_type)
        }


class StressTestRunner:
    """
    Executes stress tests against the QUAN system
    """

    def __init__(self):
        self.latency_tracker = LatencyTracker()
        self.chaos_injector = ChaosInjector()
        self.results: list[StressTestResult] = []
        self.active_test: StressTestConfig | None = None

        # Simulated system state
        self.system_state = {
            "accounts_processed": 0,
            "payments_processed": 0,
            "contacts_made": 0,
            "errors": 0
        }

    async def run_test(self, config: StressTestConfig) -> StressTestResult:
        """Run a stress test"""
        self.active_test = config
        self.latency_tracker.reset()

        # Initialize result
        started_at = datetime.now()
        result = StressTestResult(
            test_id=config.test_id,
            test_type=config.test_type,
            status=TestStatus.RUNNING,
            started_at=started_at,
            completed_at=started_at,
            duration_seconds=0.0
        )

        # Enable chaos if configured
        if config.failure_rate > 0:
            self.chaos_injector.failure_rate = config.failure_rate
            self.chaos_injector.enable()

        try:
            if config.test_type == StressTestType.VOLUME:
                await self._run_volume_test(config, result)
            elif config.test_type == StressTestType.LATENCY:
                await self._run_latency_test(config, result)
            elif config.test_type == StressTestType.SPIKE:
                await self._run_spike_test(config, result)
            elif config.test_type == StressTestType.SOAK:
                await self._run_soak_test(config, result)
            elif config.test_type == StressTestType.CHAOS:
                await self._run_chaos_test(config, result)
            elif config.test_type == StressTestType.CONCURRENT:
                await self._run_concurrent_test(config, result)
            elif config.test_type == StressTestType.RECOVERY:
                await self._run_recovery_test(config, result)

        except Exception as e:
            result.status = TestStatus.ERROR
            result.failure_reasons.append(f"Test error: {str(e)}")

        finally:
            self.chaos_injector.disable()
            result.completed_at = datetime.now()
            result.duration_seconds = (result.completed_at - result.started_at).total_seconds()

        # Calculate final metrics
        self._finalize_result(result, config)

        self.results.append(result)
        self.active_test = None

        return result

    async def _run_volume_test(
        self,
        config: StressTestConfig,
        result: StressTestResult
    ) -> None:
        """Run volume/throughput test"""
        interval = 1.0 / config.target_rps  # Time between requests
        end_time = time.time() + config.duration_seconds

        while time.time() < end_time:
            request_id = f"req_{result.total_requests}"

            # Execute request
            success, latency = await self._execute_request(request_id)

            result.total_requests += 1
            if success:
                result.successful_requests += 1
            else:
                result.failed_requests += 1

            # Maintain target rate
            await asyncio.sleep(interval)

    async def _run_latency_test(
        self,
        config: StressTestConfig,
        result: StressTestResult
    ) -> None:
        """Run latency-focused test"""
        # Lower throughput, focus on latency measurement
        target_rps = min(config.target_rps, 50)
        interval = 1.0 / target_rps

        end_time = time.time() + config.duration_seconds

        while time.time() < end_time:
            request_id = f"req_{result.total_requests}"

            # Execute with detailed timing
            self.latency_tracker.start(request_id)
            success, _ = await self._execute_request(request_id)
            latency = self.latency_tracker.end(request_id)

            result.total_requests += 1
            if success:
                result.successful_requests += 1
            else:
                result.failed_requests += 1

            await asyncio.sleep(interval)

    async def _run_spike_test(
        self,
        config: StressTestConfig,
        result: StressTestResult
    ) -> None:
        """Run spike load test"""
        # Normal load -> Spike -> Normal -> Spike pattern
        spike_multiplier = 5
        spike_duration = 10  # seconds

        phases = [
            ("normal", config.target_rps, 15),
            ("spike", config.target_rps * spike_multiplier, spike_duration),
            ("normal", config.target_rps, 15),
            ("spike", config.target_rps * spike_multiplier, spike_duration),
            ("normal", config.target_rps, 10)
        ]

        for phase_name, rps, duration in phases:
            interval = 1.0 / rps
            phase_end = time.time() + duration

            while time.time() < phase_end:
                request_id = f"req_{result.total_requests}"
                success, _ = await self._execute_request(request_id)

                result.total_requests += 1
                if success:
                    result.successful_requests += 1
                else:
                    result.failed_requests += 1

                await asyncio.sleep(interval)

    async def _run_soak_test(
        self,
        config: StressTestConfig,
        result: StressTestResult
    ) -> None:
        """Run extended duration soak test"""
        # Lower rate, longer duration
        interval = 1.0 / (config.target_rps * 0.7)
        end_time = time.time() + config.duration_seconds

        sample_interval = 60  # Sample metrics every minute
        last_sample = time.time()

        while time.time() < end_time:
            request_id = f"req_{result.total_requests}"
            success, _ = await self._execute_request(request_id)

            result.total_requests += 1
            if success:
                result.successful_requests += 1
            else:
                result.failed_requests += 1

            # Periodic sampling
            if time.time() - last_sample >= sample_interval:
                self._sample_resources(result)
                last_sample = time.time()

            await asyncio.sleep(interval)

    async def _run_chaos_test(
        self,
        config: StressTestConfig,
        result: StressTestResult
    ) -> None:
        """Run chaos/failure injection test"""
        self.chaos_injector.failure_rate = config.failure_rate or 0.10
        self.chaos_injector.enable()

        interval = 1.0 / config.target_rps
        end_time = time.time() + config.duration_seconds

        while time.time() < end_time:
            request_id = f"req_{result.total_requests}"

            # Check for injected failure
            injected, failure_type = self.chaos_injector.maybe_inject(request_id)

            if injected:
                result.failed_requests += 1
                result.errors_by_type[failure_type] = result.errors_by_type.get(failure_type, 0) + 1
            else:
                success, _ = await self._execute_request(request_id)
                if success:
                    result.successful_requests += 1
                else:
                    result.failed_requests += 1

            result.total_requests += 1
            await asyncio.sleep(interval)

    async def _run_concurrent_test(
        self,
        config: StressTestConfig,
        result: StressTestResult
    ) -> None:
        """Run concurrent operations test"""
        async def worker(worker_id: int, requests_per_worker: int):
            for i in range(requests_per_worker):
                request_id = f"worker_{worker_id}_req_{i}"
                success, _ = await self._execute_request(request_id)

                result.total_requests += 1
                if success:
                    result.successful_requests += 1
                else:
                    result.failed_requests += 1

        # Calculate requests per worker
        total_requests = config.target_rps * config.duration_seconds
        requests_per_worker = total_requests // config.concurrent_users

        # Create worker tasks
        tasks = [
            worker(i, requests_per_worker)
            for i in range(config.concurrent_users)
        ]

        # Run concurrently
        await asyncio.gather(*tasks)

    async def _run_recovery_test(
        self,
        config: StressTestConfig,
        result: StressTestResult
    ) -> None:
        """Run failure recovery test"""
        interval = 1.0 / config.target_rps

        # Phase 1: Normal operation
        phase1_end = time.time() + 20
        while time.time() < phase1_end:
            request_id = f"req_{result.total_requests}"
            success, _ = await self._execute_request(request_id)
            result.total_requests += 1
            if success:
                result.successful_requests += 1
            await asyncio.sleep(interval)

        # Phase 2: Inject failures
        self.chaos_injector.failure_rate = 0.5  # 50% failure
        self.chaos_injector.enable()

        phase2_end = time.time() + 10
        while time.time() < phase2_end:
            request_id = f"req_{result.total_requests}"
            injected, failure_type = self.chaos_injector.maybe_inject(request_id)
            if injected:
                result.failed_requests += 1
            else:
                success, _ = await self._execute_request(request_id)
                result.total_requests += 1
                if success:
                    result.successful_requests += 1
            await asyncio.sleep(interval)

        # Phase 3: Recovery
        self.chaos_injector.disable()
        recovery_start = time.time()

        phase3_end = time.time() + 20
        recovery_achieved = False
        while time.time() < phase3_end:
            request_id = f"req_{result.total_requests}"
            success, _ = await self._execute_request(request_id)
            result.total_requests += 1
            if success:
                result.successful_requests += 1
                if not recovery_achieved:
                    # Check if recovered (90%+ success in last 10)
                    recent_success = result.successful_requests / result.total_requests
                    if recent_success > 0.9:
                        recovery_achieved = True
                        recovery_time = time.time() - recovery_start

            await asyncio.sleep(interval)

    async def _execute_request(self, request_id: str) -> tuple[bool, float]:
        """Execute a simulated request"""
        self.latency_tracker.start(request_id)

        # Simulate processing
        base_latency = random.uniform(5, 50)  # 5-50ms base

        # Add variability based on load
        if self.active_test:
            load_factor = self.active_test.target_rps / 100
            base_latency *= (1 + load_factor * 0.5)

        await asyncio.sleep(base_latency / 1000)

        # Simulate occasional failures
        success = random.random() > 0.02  # 2% natural failure rate

        latency = self.latency_tracker.end(request_id)
        return success, latency

    def _sample_resources(self, result: StressTestResult) -> None:
        """Sample resource usage"""
        # Simulated resource metrics
        result.peak_memory_mb = max(result.peak_memory_mb, random.uniform(100, 500))
        result.peak_cpu_percent = max(result.peak_cpu_percent, random.uniform(20, 80))

    def _finalize_result(
        self,
        result: StressTestResult,
        config: StressTestConfig
    ) -> None:
        """Finalize result metrics and assertions"""
        # Calculate throughput
        if result.duration_seconds > 0:
            result.actual_rps = result.total_requests / result.duration_seconds

        # Calculate error rate
        if result.total_requests > 0:
            result.error_rate = result.failed_requests / result.total_requests

        # Get latency statistics
        latency_stats = self.latency_tracker.get_statistics()
        if latency_stats:
            result.avg_latency_ms = latency_stats.get("avg", 0)
            result.p50_latency_ms = latency_stats.get("p50", 0)
            result.p95_latency_ms = latency_stats.get("p95", 0)
            result.p99_latency_ms = latency_stats.get("p99", 0)
            result.max_latency_ms = latency_stats.get("max", 0)

        # Run assertions
        self._run_assertions(result, config)

    def _run_assertions(
        self,
        result: StressTestResult,
        config: StressTestConfig
    ) -> None:
        """Run test assertions"""
        # Latency assertion
        if result.p95_latency_ms <= config.max_latency_ms:
            result.assertions_passed += 1
        else:
            result.assertions_failed += 1
            result.failure_reasons.append(
                f"P95 latency {result.p95_latency_ms:.0f}ms exceeds max {config.max_latency_ms}ms"
            )

        # Error rate assertion
        if result.error_rate <= config.max_error_rate:
            result.assertions_passed += 1
        else:
            result.assertions_failed += 1
            result.failure_reasons.append(
                f"Error rate {result.error_rate:.2%} exceeds max {config.max_error_rate:.2%}"
            )

        # Throughput assertion
        throughput_pct = (result.actual_rps / config.target_rps) * 100 if config.target_rps > 0 else 0
        if throughput_pct >= config.min_throughput:
            result.assertions_passed += 1
        else:
            result.assertions_failed += 1
            result.failure_reasons.append(
                f"Throughput {throughput_pct:.0f}% below minimum {config.min_throughput}%"
            )

        # Determine overall status
        if result.assertions_failed == 0:
            result.status = TestStatus.PASSED
        else:
            result.status = TestStatus.FAILED

    def get_summary(self) -> dict[str, Any]:
        """Get summary of all test results"""
        passed = sum(1 for r in self.results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in self.results if r.status == TestStatus.FAILED)

        return {
            "total_tests": len(self.results),
            "passed": passed,
            "failed": failed,
            "pass_rate": passed / len(self.results) if self.results else 0,
            "tests": [
                {
                    "test_id": r.test_id,
                    "type": r.test_type.value,
                    "status": r.status.value,
                    "duration": r.duration_seconds,
                    "rps": r.actual_rps,
                    "error_rate": r.error_rate,
                    "p95_latency": r.p95_latency_ms
                }
                for r in self.results
            ]
        }


# Demonstration
if __name__ == "__main__":
    async def main():
        print("=== STRESS TESTING FRAMEWORK DEMO ===\n")

        runner = StressTestRunner()

        # Define tests
        tests = [
            StressTestConfig(
                test_id="vol_001",
                test_type=StressTestType.VOLUME,
                name="Volume Test",
                description="High throughput volume test",
                target_rps=100,
                duration_seconds=5,
                max_latency_ms=200,
                max_error_rate=0.05
            ),
            StressTestConfig(
                test_id="lat_001",
                test_type=StressTestType.LATENCY,
                name="Latency Test",
                description="Latency measurement test",
                target_rps=50,
                duration_seconds=5,
                max_latency_ms=100
            ),
            StressTestConfig(
                test_id="chaos_001",
                test_type=StressTestType.CHAOS,
                name="Chaos Test",
                description="Failure injection test",
                target_rps=50,
                duration_seconds=5,
                failure_rate=0.10,
                max_error_rate=0.15
            )
        ]

        # Run tests
        for config in tests:
            print(f"Running: {config.name}...")
            result = await runner.run_test(config)
            status = "✓ PASSED" if result.status == TestStatus.PASSED else "✗ FAILED"
            print(f"  {status}")
            print(f"  RPS: {result.actual_rps:.1f}, Error Rate: {result.error_rate:.2%}, P95: {result.p95_latency_ms:.0f}ms")
            if result.failure_reasons:
                for reason in result.failure_reasons:
                    print(f"  - {reason}")
            print()

        # Summary
        summary = runner.get_summary()
        print("=== SUMMARY ===")
        print(f"Total: {summary['total_tests']}, Passed: {summary['passed']}, Failed: {summary['failed']}")
        print(f"Pass Rate: {summary['pass_rate']:.0%}")

    asyncio.run(main())
