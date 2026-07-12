"""
Open-Brain Backend — Authentication Service

Handles password hashing, JWT creation/validation, token rotation,
and token_version-based session revocation.
"""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from loguru import logger
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from app.config import settings
from app.models.user import User
from app.models.refresh_token import RefreshToken


# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def _hash_token(token: str) -> str:
    """Create a SHA-256 hash of a token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(user_id: str, token_version: int) -> str:
    """
    Create a short-lived JWT access token.

    Embeds token_version for instant revocation per edge cases plan.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "token_version": token_version,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: str, token_version: int) -> tuple[str, datetime]:
    """
    Create a long-lived JWT refresh token.

    Returns (token_string, expiration_datetime).
    """
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=settings.refresh_token_expire_days)
    payload = {
        "sub": user_id,
        "token_version": token_version,
        "type": "refresh",
        "iat": now,
        "exp": expires_at,
        "jti": str(uuid.uuid4()),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, expires_at


def decode_token(token: str) -> Optional[dict]:
    """
    Decode and validate a JWT token.

    Returns the payload dict or None if invalid/expired.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.debug("Token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.debug(f"Invalid token: {e}")
        return None


# ---------------------------------------------------------------------------
# MFA / OTP helpers
# ---------------------------------------------------------------------------

def create_mfa_token(user_id: str, email: str) -> str:
    """
    Create a short-lived JWT used as an MFA challenge token.

    This token proves the user passed password validation and is valid
    for otp_expire_minutes (default 5 min). It CANNOT be used as an
    access or refresh token — its type is 'mfa_challenge'.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "type": "mfa_challenge",
        "iat": now,
        "exp": now + timedelta(minutes=settings.otp_expire_minutes),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def generate_otp() -> str:
    """Generate a cryptographically random 6-digit OTP code."""
    import secrets
    return f"{secrets.randbelow(1_000_000):06d}"


async def store_otp(
    redis_client,
    key_prefix: str,
    identifier: str,
    otp: str,
) -> None:
    """
    Store an OTP in Redis with a TTL of otp_expire_minutes.

    Key format: otp:{key_prefix}:{identifier}
    """
    redis_key = f"otp:{key_prefix}:{identifier}"
    await redis_client.setex(
        redis_key,
        settings.otp_expire_minutes * 60,
        otp,
    )


async def verify_otp(
    redis_client,
    key_prefix: str,
    identifier: str,
    otp: str,
    *,
    delete_on_success: bool = True,
    max_attempts: int = 5,
) -> bool:
    """
    Verify an OTP against the value stored in Redis.

    Returns True if the OTP matches. On success the key is deleted
    (unless delete_on_success=False) to prevent replay.

    Implements brute-force protection: after max_attempts failed tries,
    the OTP is deleted (locked out) and subsequent attempts return False.
    """
    redis_key = f"otp:{key_prefix}:{identifier}"
    attempts_key = f"otp_attempts:{key_prefix}:{identifier}"

    stored = await redis_client.get(redis_key)
    if stored is None:
        return False

    # Check if already locked out due to too many failed attempts
    current_attempts = await redis_client.get(attempts_key)
    if current_attempts is not None and int(current_attempts) >= max_attempts:
        # Lockout: delete the OTP so it can never be used
        await redis_client.delete(redis_key, attempts_key)
        logger.warning(f"OTP locked out for {key_prefix}:{identifier} after {max_attempts} failed attempts")
        return False

    if stored != otp:
        # Increment failed attempt counter (expires with the OTP)
        pipe = redis_client.pipeline()
        pipe.incr(attempts_key)
        pipe.expire(attempts_key, settings.otp_expire_minutes * 60)
        results = await pipe.execute()
        new_count = results[0]

        if new_count >= max_attempts:
            # Just hit the limit: delete the OTP immediately
            await redis_client.delete(redis_key, attempts_key)
            logger.warning(f"OTP locked out for {key_prefix}:{identifier} after {max_attempts} failed attempts")

        return False

    # Success: clean up OTP and attempts counter
    if delete_on_success:
        await redis_client.delete(redis_key, attempts_key)
    return True


async def validate_token_version(
    user_id: str,
    token_version: int,
    redis_client: aioredis.Redis,
    db: AsyncSession,
) -> bool:
    """
    Validate a token's version against the cached/stored version.

    Implements the token_version strategy from the edge cases plan:
    1. Check Redis cache first (fast path)
    2. Fall back to PostgreSQL if not cached
    3. Reject if versions don't match
    """
    redis_key = f"user:{user_id}:token_version"

    # Try Redis first
    cached_version = await redis_client.get(redis_key)
    if cached_version is not None:
        return int(cached_version) == token_version

    # Fallback to database
    result = await db.execute(select(User.token_version).where(User.id == user_id))
    db_version = result.scalar_one_or_none()
    if db_version is None:
        return False

    # Cache in Redis for 5 minutes
    await redis_client.setex(redis_key, 300, str(db_version))

    return db_version == token_version


async def store_refresh_token(
    db: AsyncSession,
    user_id: str,
    token: str,
    expires_at: datetime,
) -> RefreshToken:
    """Store a hashed refresh token in the database."""
    refresh_token_record = RefreshToken(
        user_id=user_id,
        token_hash=_hash_token(token),
        expires_at=expires_at,
    )
    db.add(refresh_token_record)
    await db.flush()
    return refresh_token_record


async def revoke_refresh_token(db: AsyncSession, token: str) -> bool:
    """Revoke a specific refresh token by marking it as revoked."""
    token_hash = _hash_token(token)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked == False,  # noqa: E712
        )
    )
    refresh_token = result.scalar_one_or_none()
    if refresh_token:
        refresh_token.revoked = True
        await db.flush()
        return True
    return False


async def is_refresh_token_valid(db: AsyncSession, token: str) -> bool:
    """Check if a refresh token is valid (exists and not revoked)."""
    token_hash = _hash_token(token)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked == False,  # noqa: E712
        )
    )
    refresh_token = result.scalar_one_or_none()
    if refresh_token is None:
        return False
    # Check expiration
    if refresh_token.expires_at < datetime.now(timezone.utc):
        return False
    return True


async def revoke_all_user_tokens(
    db: AsyncSession,
    redis_client: aioredis.Redis,
    user_id: str,
) -> None:
    """
    Bump token_version to instantly invalidate ALL tokens for a user.

    Used for "logout all devices" or password change.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user:
        user.token_version += 1
        await db.flush()
        # Update Redis cache immediately
        redis_key = f"user:{user_id}:token_version"
        await redis_client.setex(redis_key, 300, str(user.token_version))
        logger.info(f"Revoked all tokens for user {user_id} (version → {user.token_version})")


async def check_login_rate_limit(
    redis_client: aioredis.Redis,
    email: str,
) -> bool:
    """
    Check if login attempts are rate-limited for an email.

    Returns True if the request is allowed, False if rate-limited.
    """
    key = f"login_attempts:{email}"
    attempts = await redis_client.get(key)
    if attempts and int(attempts) >= 5:
        return False
    return True


async def increment_login_attempts(
    redis_client: aioredis.Redis,
    email: str,
) -> None:
    """Increment failed login attempt counter (expires after 15 minutes)."""
    key = f"login_attempts:{email}"
    pipe = redis_client.pipeline()
    pipe.incr(key)
    pipe.expire(key, 900)  # 15 minutes
    await pipe.execute()


async def reset_login_attempts(
    redis_client: aioredis.Redis,
    email: str,
) -> None:
    """Reset login attempt counter on successful login."""
    key = f"login_attempts:{email}"
    await redis_client.delete(key)


# ---------------------------------------------------------------------------
# Access Token Blacklist (Single-Session Logout)
# ---------------------------------------------------------------------------

async def blacklist_access_token(
    redis_client: aioredis.Redis,
    jti: str,
    expires_at_unix: int,
) -> None:
    """
    Blacklist an access token by its JTI (JWT ID) in Redis.

    The key auto-expires when the token itself would have expired,
    so blacklisted entries don't accumulate indefinitely.
    """
    now = int(datetime.now(timezone.utc).timestamp())
    ttl = expires_at_unix - now
    if ttl <= 0:
        return  # Token already expired, no need to blacklist

    redis_key = f"blacklist:access:{jti}"
    await redis_client.setex(redis_key, ttl, "1")
    logger.info(f"Blacklisted access token {jti} (TTL: {ttl}s)")


async def is_access_token_blacklisted(
    redis_client: aioredis.Redis,
    jti: str,
) -> bool:
    """Check if an access token's JTI has been blacklisted."""
    redis_key = f"blacklist:access:{jti}"
    return await redis_client.exists(redis_key) > 0


async def revoke_current_session(
    db: AsyncSession,
    redis_client: aioredis.Redis,
    access_token_jti: str,
    access_token_exp: int,
    refresh_token_raw: str | None = None,
) -> None:
    """
    Revoke only the current session (single-device logout).

    1. Blacklists the current access token's JTI in Redis.
    2. Revokes the specific refresh token in the database (if provided).
    Does NOT bump token_version — other devices stay logged in.
    """
    # Blacklist the access token
    await blacklist_access_token(redis_client, access_token_jti, access_token_exp)

    # Revoke the specific refresh token if provided
    if refresh_token_raw:
        await revoke_refresh_token(db, refresh_token_raw)

