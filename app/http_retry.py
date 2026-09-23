import time
import logging
import httpx

logger = logging.getLogger("http_retry")

RETRYABLE_EXCEPTIONS = (
    httpx.ReadError,
    httpx.ReadTimeout,
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.RemoteProtocolError,
    httpx.WriteError,
    httpx.PoolTimeout,
)


def call_with_retry(func, *args, max_retries: int = 5, delay_seconds: float = 60.0, **kwargs):
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            return func(*args, **kwargs)
        except RETRYABLE_EXCEPTIONS as exc:
            last_exc = exc
            logger.warning(
                "Loi ket noi mang (lan %s/%s), cho %ss roi thu lai: %s",
                attempt, max_retries, delay_seconds, exc,
            )
            if attempt < max_retries:
                time.sleep(delay_seconds)
        except httpx.HTTPStatusError as exc:
            if exc.response is not None and exc.response.status_code >= 500:
                last_exc = exc
                logger.warning(
                    "Loi server %s (lan %s/%s), cho %ss roi thu lai: %s",
                    exc.response.status_code, attempt, max_retries, delay_seconds, exc,
                )
                if attempt < max_retries:
                    time.sleep(delay_seconds)
            else:
                raise
    raise last_exc