"""
Redis-backed rate limiting.

Per SECURITY.md §6 / API_SPEC.md: auth endpoints are rate-limited per IP
(unauthenticated). MVP scope for Redis is rate limiting ONLY — no WS
pub/sub yet (approved decision #5). Uses a simple fixed-window counter,
which is sufficient for the limits API_SPEC.md defines and cheap in Redis
(a single INCR + EXPIRE per request).

No lockout behavior is implemented anywhere in this module — rate limiting
only, per explicit instruction not to invent account-lockout functionality.
"""
from redis.asyncio import Redis
from fastapi import Request

from app.core.config import get_settings
from app.core.exceptions import RateLimitedError

_redis_client: Redis | None = None


def get_redis() -> Redis:
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def enforce_rate_limit(request: Request, *, bucket: str, limit_per_minute: int) -> None:
    """Fixed 60s window keyed by (bucket, client IP). Raises RateLimitedError
    (mapped to 429 + Retry-After by the global error handler) when exceeded."""
    redis = get_redis()
    ip = _client_ip(request)
    key = f"ratelimit:{bucket}:{ip}"

    current = await redis.incr(key)
    if current == 1:
        await redis.expire(key, 60)

    if current > limit_per_minute:
        ttl = await redis.ttl(key)
        raise RateLimitedError(retry_after_seconds=max(ttl, 1))


def rate_limiter(bucket: str, limit_per_minute: int):
    """Factory producing a FastAPI dependency for a specific endpoint's limit."""

    async def _dependency(request: Request) -> None:
        await enforce_rate_limit(request, bucket=bucket, limit_per_minute=limit_per_minute)

    return _dependency
