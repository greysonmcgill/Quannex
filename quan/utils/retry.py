"""
QUAN Recovery - Retry Utilities

This module provides reusable retry logic with various backoff strategies.
Use these utilities instead of implementing retry logic inline.

Usage:
    from quan.utils.retry import retry, RetryConfig, ExponentialBackoff

    @retry(max_attempts=3, backoff=ExponentialBackoff())
    async def process_payment():
        ...

    # Or with configuration
    config = RetryConfig(max_attempts=5, exceptions=(PaymentError,))
    result = await retry_async(process_payment, config=config)
"""

import asyncio
import functools
import logging
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Awaitable,
    Callable,
    List,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")
ExceptionTypes = Union[Type[Exception], Tuple[Type[Exception], ...]]


# =============================================================================
# BACKOFF STRATEGIES
# =============================================================================

class BackoffStrategy(ABC):
    """Base class for backoff strategies"""

    @abstractmethod
    def get_delay(self, attempt: int) -> float:
        """
        Calculate delay before next retry.

        Args:
            attempt: Current attempt number (1-indexed)

        Returns:
            Delay in seconds
        """
        pass


@dataclass
class ConstantBackoff(BackoffStrategy):
    """Fixed delay between retries"""

    delay: float = 1.0  # seconds

    def get_delay(self, attempt: int) -> float:
        return self.delay


@dataclass
class LinearBackoff(BackoffStrategy):
    """Linearly increasing delay"""

    initial_delay: float = 1.0
    increment: float = 1.0
    max_delay: float = 60.0

    def get_delay(self, attempt: int) -> float:
        delay = self.initial_delay + (attempt - 1) * self.increment
        return min(delay, self.max_delay)


@dataclass
class ExponentialBackoff(BackoffStrategy):
    """
    Exponential backoff with optional jitter.

    Delay = min(base * (multiplier ^ attempt) + jitter, max_delay)
    """

    base: float = 1.0
    multiplier: float = 2.0
    max_delay: float = 60.0
    jitter: bool = True
    jitter_factor: float = 0.1  # +/- 10%

    def get_delay(self, attempt: int) -> float:
        delay = self.base * (self.multiplier ** (attempt - 1))
        delay = min(delay, self.max_delay)

        if self.jitter:
            jitter_range = delay * self.jitter_factor
            delay += random.uniform(-jitter_range, jitter_range)

        return max(0, delay)


@dataclass
class FibonacciBackoff(BackoffStrategy):
    """Fibonacci sequence backoff"""

    initial_delay: float = 1.0
    max_delay: float = 60.0

    def get_delay(self, attempt: int) -> float:
        a, b = 0, 1
        for _ in range(attempt):
            a, b = b, a + b
        delay = a * self.initial_delay
        return min(delay, self.max_delay)


@dataclass
class ScheduledBackoff(BackoffStrategy):
    """
    Predefined delay schedule.

    Useful for payment retries with specific timing requirements.
    """

    delays: List[float] = field(default_factory=lambda: [60, 300, 1800, 3600, 86400])

    def get_delay(self, attempt: int) -> float:
        if attempt <= 0:
            return 0
        if attempt <= len(self.delays):
            return self.delays[attempt - 1]
        return self.delays[-1]


# =============================================================================
# RETRY CONFIGURATION
# =============================================================================

class RetryDecision(Enum):
    """Decision on whether to retry"""
    RETRY = "retry"
    STOP = "stop"
    RAISE = "raise"


@dataclass
class RetryConfig:
    """Configuration for retry behavior"""

    # Basic settings
    max_attempts: int = 3
    backoff: BackoffStrategy = field(default_factory=ExponentialBackoff)

    # Exception handling
    exceptions: ExceptionTypes = Exception
    fatal_exceptions: Optional[ExceptionTypes] = None

    # Callbacks
    on_retry: Optional[Callable[[Exception, int], None]] = None
    on_success: Optional[Callable[[Any, int], None]] = None
    on_failure: Optional[Callable[[Exception, int], None]] = None

    # Retry predicate (custom logic)
    should_retry: Optional[Callable[[Exception, int], RetryDecision]] = None

    # Timeout
    timeout: Optional[float] = None  # Total timeout in seconds


@dataclass
class RetryState:
    """State tracking for retry operations"""

    attempt: int = 0
    start_time: datetime = field(default_factory=datetime.now)
    last_exception: Optional[Exception] = None
    total_delay: float = 0.0

    @property
    def elapsed(self) -> float:
        return (datetime.now() - self.start_time).total_seconds()


@dataclass
class RetryResult:
    """Result of a retry operation"""

    success: bool
    value: Any = None
    exception: Optional[Exception] = None
    attempts: int = 0
    total_time: float = 0.0


# =============================================================================
# RETRY FUNCTIONS
# =============================================================================

def retry(
    max_attempts: int = 3,
    backoff: Optional[BackoffStrategy] = None,
    exceptions: ExceptionTypes = Exception,
    on_retry: Optional[Callable[[Exception, int], None]] = None,
):
    """
    Decorator for retrying synchronous functions.

    Args:
        max_attempts: Maximum number of attempts
        backoff: Backoff strategy (default: ExponentialBackoff)
        exceptions: Exception types to catch and retry
        on_retry: Callback called before each retry

    Example:
        @retry(max_attempts=3, exceptions=(ConnectionError, TimeoutError))
        def fetch_data():
            return requests.get(url)
    """
    if backoff is None:
        backoff = ExponentialBackoff()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception: Optional[Exception] = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        delay = backoff.get_delay(attempt)
                        logger.warning(
                            f"Attempt {attempt}/{max_attempts} failed: {e}. "
                            f"Retrying in {delay:.2f}s"
                        )
                        if on_retry:
                            on_retry(e, attempt)
                        time.sleep(delay)
                    else:
                        logger.error(f"All {max_attempts} attempts failed")

            raise last_exception  # type: ignore

        return wrapper
    return decorator


def retry_async(
    max_attempts: int = 3,
    backoff: Optional[BackoffStrategy] = None,
    exceptions: ExceptionTypes = Exception,
    on_retry: Optional[Callable[[Exception, int], None]] = None,
):
    """
    Decorator for retrying async functions.

    Args:
        max_attempts: Maximum number of attempts
        backoff: Backoff strategy (default: ExponentialBackoff)
        exceptions: Exception types to catch and retry
        on_retry: Callback called before each retry

    Example:
        @retry_async(max_attempts=3)
        async def fetch_data():
            return await client.get(url)
    """
    if backoff is None:
        backoff = ExponentialBackoff()

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception: Optional[Exception] = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        delay = backoff.get_delay(attempt)
                        logger.warning(
                            f"Attempt {attempt}/{max_attempts} failed: {e}. "
                            f"Retrying in {delay:.2f}s"
                        )
                        if on_retry:
                            on_retry(e, attempt)
                        await asyncio.sleep(delay)
                    else:
                        logger.error(f"All {max_attempts} attempts failed")

            raise last_exception  # type: ignore

        return wrapper
    return decorator


async def execute_with_retry(
    func: Callable[..., Awaitable[T]],
    *args,
    config: Optional[RetryConfig] = None,
    **kwargs,
) -> RetryResult:
    """
    Execute an async function with retry logic.

    This is the most flexible retry interface, supporting all configuration
    options including custom retry predicates and timeouts.

    Args:
        func: Async function to execute
        *args: Positional arguments for func
        config: Retry configuration
        **kwargs: Keyword arguments for func

    Returns:
        RetryResult with success status, value or exception, and statistics

    Example:
        result = await execute_with_retry(
            process_payment,
            payment_id,
            config=RetryConfig(max_attempts=5, timeout=30.0)
        )
        if result.success:
            print(f"Success after {result.attempts} attempts")
    """
    if config is None:
        config = RetryConfig()

    state = RetryState()

    while state.attempt < config.max_attempts:
        state.attempt += 1

        # Check timeout
        if config.timeout and state.elapsed > config.timeout:
            return RetryResult(
                success=False,
                exception=TimeoutError(f"Retry timeout after {state.elapsed:.2f}s"),
                attempts=state.attempt,
                total_time=state.elapsed,
            )

        try:
            result = await func(*args, **kwargs)

            if config.on_success:
                config.on_success(result, state.attempt)

            return RetryResult(
                success=True,
                value=result,
                attempts=state.attempt,
                total_time=state.elapsed,
            )

        except Exception as e:
            state.last_exception = e

            # Check fatal exceptions
            if config.fatal_exceptions and isinstance(e, config.fatal_exceptions):
                logger.error(f"Fatal exception encountered: {e}")
                return RetryResult(
                    success=False,
                    exception=e,
                    attempts=state.attempt,
                    total_time=state.elapsed,
                )

            # Check if we should retry this exception type
            if not isinstance(e, config.exceptions):
                raise

            # Custom retry predicate
            if config.should_retry:
                decision = config.should_retry(e, state.attempt)
                if decision == RetryDecision.STOP:
                    break
                elif decision == RetryDecision.RAISE:
                    raise

            # Check if we have attempts remaining
            if state.attempt >= config.max_attempts:
                break

            # Calculate and apply delay
            delay = config.backoff.get_delay(state.attempt)
            state.total_delay += delay

            logger.warning(
                f"Attempt {state.attempt}/{config.max_attempts} failed: {e}. "
                f"Retrying in {delay:.2f}s"
            )

            if config.on_retry:
                config.on_retry(e, state.attempt)

            await asyncio.sleep(delay)

    # All attempts exhausted
    if config.on_failure:
        config.on_failure(state.last_exception, state.attempt)  # type: ignore

    return RetryResult(
        success=False,
        exception=state.last_exception,
        attempts=state.attempt,
        total_time=state.elapsed,
    )


# =============================================================================
# SPECIALIZED RETRY HELPERS
# =============================================================================

class PaymentRetryStrategy:
    """
    Specialized retry strategy for payment processing.

    Implements smart retry based on failure reason.
    """

    # Standard payment retry delays
    RETRY_DELAYS = [60, 300, 1800, 3600, 14400, 86400]  # 1m, 5m, 30m, 1h, 4h, 24h

    # Failure reasons that should not retry
    NO_RETRY_REASONS = frozenset([
        "fraud_suspected",
        "account_frozen",
        "card_lost_stolen",
        "do_not_honor",
    ])

    # Failure reasons that need card update
    CARD_UPDATE_REASONS = frozenset([
        "card_expired",
        "invalid_card",
        "invalid_cvv",
    ])

    # Failure reasons that may work with a different method
    ALTERNATIVE_METHOD_REASONS = frozenset([
        "insufficient_funds",
        "card_declined",
        "account_closed",
    ])

    @classmethod
    def should_retry(cls, failure_reason: str, attempt: int) -> RetryDecision:
        """Determine if payment should be retried based on failure reason"""
        reason_lower = failure_reason.lower()

        if reason_lower in cls.NO_RETRY_REASONS:
            return RetryDecision.STOP

        if reason_lower in cls.CARD_UPDATE_REASONS:
            return RetryDecision.STOP  # Need user action

        if reason_lower in cls.ALTERNATIVE_METHOD_REASONS and attempt > 2:
            return RetryDecision.STOP  # After 2 attempts, need alternative

        return RetryDecision.RETRY

    @classmethod
    def get_config(cls, max_attempts: int = 6) -> RetryConfig:
        """Get retry configuration for payment processing"""
        return RetryConfig(
            max_attempts=max_attempts,
            backoff=ScheduledBackoff(delays=cls.RETRY_DELAYS[:max_attempts]),
            timeout=86400 * 3,  # 3 days max
        )


# =============================================================================
# CIRCUIT BREAKER
# =============================================================================

class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreaker:
    """
    Circuit breaker pattern for external service calls.

    Prevents cascade failures by stopping requests to failing services.
    """

    failure_threshold: int = 5
    recovery_timeout: float = 30.0  # seconds
    half_open_max_calls: int = 1

    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _last_failure_time: Optional[float] = field(default=None, init=False)
    _half_open_calls: int = field(default=0, init=False)

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if (
                self._last_failure_time
                and time.time() - self._last_failure_time > self.recovery_timeout
            ):
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
        return self._state

    def record_success(self) -> None:
        """Record a successful call"""
        self._failure_count = 0
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.CLOSED
            logger.info("Circuit breaker closed after successful test")

    def record_failure(self) -> None:
        """Record a failed call"""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
            logger.warning("Circuit breaker re-opened after test failure")
        elif self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(
                f"Circuit breaker opened after {self._failure_count} failures"
            )

    def allow_request(self) -> bool:
        """Check if a request should be allowed"""
        state = self.state  # This may transition from OPEN to HALF_OPEN

        if state == CircuitState.CLOSED:
            return True

        if state == CircuitState.HALF_OPEN:
            if self._half_open_calls < self.half_open_max_calls:
                self._half_open_calls += 1
                return True
            return False

        return False  # OPEN


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Backoff strategies
    "BackoffStrategy",
    "ConstantBackoff",
    "LinearBackoff",
    "ExponentialBackoff",
    "FibonacciBackoff",
    "ScheduledBackoff",
    # Configuration
    "RetryConfig",
    "RetryState",
    "RetryResult",
    "RetryDecision",
    # Decorators
    "retry",
    "retry_async",
    # Functions
    "execute_with_retry",
    # Specialized
    "PaymentRetryStrategy",
    # Circuit breaker
    "CircuitState",
    "CircuitBreaker",
]
