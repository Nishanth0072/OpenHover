"""
Open-Brain Backend — FastAPI Dependencies

Shared dependencies injected into route handlers via FastAPI's Depends().
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from app.database import get_db
from app.redis import get_redis
from app.models.user import User
from app.services.auth_service import decode_token, validate_token_version, is_access_token_blacklisted


# Bearer token extractor
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
) -> User:
    """
    Dependency that extracts and validates the JWT from the Authorization header.

    Implements token_version checking from the edge cases plan:
    - Decodes the JWT
    - Verifies token_version against Redis/DB
    - Returns the User ORM object

    Raises 401 if the token is invalid, expired, or the version is stale.
    """
    token = credentials.credentials

    # Decode the JWT
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Ensure it's an access token
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type. Expected access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    token_version = payload.get("token_version")
    jti = payload.get("jti")

    if not user_id or token_version is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token payload.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if this specific access token has been blacklisted (single-session logout)
    if jti and await is_access_token_blacklisted(redis_client, jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This session has been logged out.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate token_version (instant revocation check)
    is_valid = await validate_token_version(user_id, token_version, redis_client, db)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has been revoked. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch user from database
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Attach the decoded token payload so routes can access jti/exp for logout
    user._token_payload = payload

    return user
