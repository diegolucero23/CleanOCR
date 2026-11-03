"""
app/core/security.py

Authentication and rate-limiting middleware and dependencies for CleanOCR.

Features:
- API Key verification (via X-API-Key header or Authorization: Bearer token).
- Open dev mode: pass-through if CLEANOCR_API_KEY is unset/empty in .env.
- Constant-time secret comparison to prevent timing attacks.
- Redis-backed sliding-window rate limiting for upload and status polling endpoints.
- Structured JSON error responses conforming to API contracts.
"""
import hashlib
import logging
import secrets
import time
import uuid
from typing import Optional, Tuple

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from redis import Redis

from app.core import config

logger = logging.getLogger("cleanocr_api.security")

# Initialize Redis client for rate limiting
redis_client = Redis.from_url(config.REDIS_URL)

# Header schemes
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_bearer_auth = HTTPBearer(auto_error=False)


def get_provided_api_key(
    request: Request,
    header_key: Optional[str] = None,
    bearer: Optional[HTTPAuthorizationCredentials] = None,
) -> Optional[str]:
    """
    Extract the API key from request headers, checking X-API-Key first,
    then Authorization: Bearer <token>.
    """
    if header_key:
        return header_key.strip()
    if bearer and bearer.credentials:
        return bearer.credentials.strip()
    # Direct header lookup fallback
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    key_from_header = request.headers.get("X-API-Key")
    if key_from_header:
        return key_from_header.strip()
    return request.query_params.get("api_key")


async def verify_api_key(request: Request) -> bool:
    """
    FastAPI security dependency to verify the caller's API key.

    Behavior:
    - If config.CLEANOCR_API_KEY is not configured (None or empty):
      Allow the request (open dev mode), emitting a debug log.
    - If config.CLEANOCR_API_KEY is configured:
      Validate provided key using constant-time comparison.
      Raise HTTP 401 with standard JSON error payload on mismatch.
    """
    configured_key = config.CLEANOCR_API_KEY
    if not configured_key:
        return True

    provided_key = get_provided_api_key(request)
    if not provided_key or not secrets.compare_digest(provided_key, configured_key):
        logger.warning(
            "Unauthorized request rejected",
            extra={"path": request.url.path, "client_host": request.client.host if request.client else "unknown"},
        )
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "Invalid or missing API key.",
                }
            },
        )
    return True


class RateLimiter:
    """
    Sliding-window rate limiter using Redis sorted sets (ZSET).
    Stores timestamps as members and scores to count events within the trailing window.
    """

    def __init__(self, redis_client_instance: Optional[Redis] = None, redis_client: Optional[Redis] = None):
        self.r = redis_client or redis_client_instance or globals()["redis_client"]

    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> Tuple[bool, int]:
        """
        Check if request under `key` is allowed within `window_seconds`.
        Returns (is_allowed: bool, retry_after_seconds: int).
        """
        now = time.time()
        clear_before = now - window_seconds
        redis_key = f"ratelimit:{key}"

        try:
            pipe = self.r.pipeline()
            pipe.zremrangebyscore(redis_key, 0, clear_before)
            member_id = f"{now}:{uuid.uuid4()}"
            pipe.zadd(redis_key, {member_id: now})
            pipe.zcard(redis_key)
            pipe.expire(redis_key, window_seconds + 5)
            results = pipe.execute()

            request_count = results[2]
            if isinstance(request_count, (int, float)) and request_count > max_requests:
                # Query oldest record in current window to calculate precise retry-after
                try:
                    oldest = self.r.zrange(redis_key, 0, 0, withscores=True)
                    if oldest and len(oldest[0]) >= 2:
                        oldest_time = float(oldest[0][1])
                        retry_after = max(1, int(window_seconds - (now - oldest_time)))
                    else:
                        retry_after = window_seconds
                except Exception:
                    retry_after = window_seconds
                return False, retry_after

            return True, 0
        except Exception as e:
            # Observability: log redis glitch, fail open to avoid service outage
            logger.error("Rate limiter Redis failure; failing open", extra={"error": str(e), "key": key})
            return True, 0


# Module-level limiter instance
_limiter = RateLimiter(redis_client)


def check_rate_limit(key: str, max_requests: int, window_seconds: int) -> Tuple[bool, int]:
    """Top-level helper function for sliding window rate checks."""
    return _limiter.is_allowed(key, max_requests, window_seconds)


def get_client_identifier(request: Request) -> str:
    """Derive unique client identifier using API key hash or client IP."""
    api_key = get_provided_api_key(request)
    if api_key:
        return f"key:{hashlib.sha256(api_key.encode()).hexdigest()[:16]}"
    client_host = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        client_host = forwarded.split(",")[0].strip()
    return f"ip:{client_host}"


async def rate_limit_upload(request: Request) -> None:
    """Enforce upload quota (default 3 uploads/min)."""
    client_id = get_client_identifier(request)
    allowed, retry_after = check_rate_limit(
        f"upload:{client_id}",
        config.RATE_LIMIT_UPLOADS_PER_MIN,
        config.RATE_LIMIT_WINDOW_SECONDS,
    )
    if not allowed:
        logger.warning(
            "Upload rate limit exceeded",
            extra={"client_id": client_id, "retry_after": retry_after},
        )
        raise HTTPException(
            status_code=429,
            detail={
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": "Rate limit exceeded. Please wait before retrying.",
                    "details": {"retry_after_seconds": retry_after},
                }
            },
            headers={"Retry-After": str(retry_after)},
        )


async def rate_limit_status(request: Request) -> None:
    """Enforce status polling quota (default 60 polls/min)."""
    client_id = get_client_identifier(request)
    allowed, retry_after = check_rate_limit(
        f"status:{client_id}",
        config.RATE_LIMIT_STATUS_PER_MIN,
        config.RATE_LIMIT_WINDOW_SECONDS,
    )
    if not allowed:
        logger.warning(
            "Status rate limit exceeded",
            extra={"client_id": client_id, "retry_after": retry_after},
        )
        raise HTTPException(
            status_code=429,
            detail={
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": "Rate limit exceeded. Please wait before retrying.",
                    "details": {"retry_after_seconds": retry_after},
                }
            },
            headers={"Retry-After": str(retry_after)},
        )
