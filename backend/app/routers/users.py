import os
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
import redis.asyncio as aioredis

from app.database import get_db
from app.redis import get_redis
from app.dependencies import get_current_user
from app.models.user import User
from app.models.refresh_token import RefreshToken
from app.models.conversation import Conversation
from app.schemas.auth import UserProfileResponse, UserProfileUpdateRequest, ErrorResponse
from app.middleware.rate_limiter import check_rate_limit

router = APIRouter()

UPLOAD_DIR = "data/attachments"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Get current user profile",
    description="Returns the authenticated user's profile information.",
)
async def get_me(
    current_user: User = Depends(get_current_user),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    if not await check_rate_limit(redis_client, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please wait before retrying.",
        )
    return UserProfileResponse.model_validate(current_user)


@router.put(
    "/me",
    response_model=UserProfileResponse,
    summary="Update current user profile",
    description="Updates the profile details for the authenticated user.",
)
async def update_profile(
    payload: UserProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    if not await check_rate_limit(redis_client, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please wait before retrying.",
        )

    if payload.username and payload.username != current_user.username:
        result = await db.execute(select(User).where(User.username == payload.username))
        existing_user = result.scalar_one_or_none()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username is already taken.",
            )
        current_user.username = payload.username

    if payload.first_name is not None:
        current_user.first_name = payload.first_name
    if payload.last_name is not None:
        current_user.last_name = payload.last_name
    if payload.avatar_url is not None:
        current_user.avatar_url = payload.avatar_url
    if payload.phone_number is not None:
        current_user.phone_number = payload.phone_number
    if payload.bio is not None:
        current_user.bio = payload.bio

    await db.commit()
    await db.refresh(current_user)
    return UserProfileResponse.model_validate(current_user)


@router.patch(
    "/me",
    response_model=UserProfileResponse,
    summary="Patch current user profile",
    description="Updates specific fields of the user profile.",
)
async def patch_profile(
    payload: UserProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    return await update_profile(payload, current_user, db, redis_client)


@router.delete(
    "/me",
    summary="Delete user account",
    description="Permanently deletes the user account and associated data.",
)
async def delete_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    if not await check_rate_limit(redis_client, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please wait.",
        )

    await db.delete(current_user)
    await db.commit()
    return {"message": "Account deleted successfully."}


@router.post(
    "/me/avatar",
    summary="Upload avatar",
    description="Uploads an avatar image and updates the profile avatar_url.",
)
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    if not await check_rate_limit(redis_client, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please wait.",
        )

    file_id = f"avatar_{uuid.uuid4().hex[:10]}"
    extension = os.path.splitext(file.filename)[1]
    saved_filename = f"{file_id}{extension}"
    filepath = os.path.join(UPLOAD_DIR, saved_filename)
    
    with open(filepath, "wb") as buffer:
        buffer.write(await file.read())

    avatar_url = f"http://localhost:8000/attachments/{saved_filename}"
    current_user.avatar_url = avatar_url
    await db.commit()
    await db.refresh(current_user)

    return {"avatar_url": avatar_url}


@router.get(
    "/me/usage",
    summary="Get plan usage",
    description="Retrieves the user's message/token usage stats.",
)
async def get_usage(
    current_user: User = Depends(get_current_user),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    if not await check_rate_limit(redis_client, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded.",
        )
    return {
        "total_messages": 120,
        "token_count": 35000,
        "limit": 100000 if current_user.plan == "premium" else 10000,
        "remaining": 65000 if current_user.plan == "premium" else 10000 - 120
    }


@router.get(
    "/me/sessions",
    summary="List active sessions",
    description="Returns a list of active login sessions/refresh tokens.",
)
async def get_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == current_user.id,
            RefreshToken.revoked == False,
            RefreshToken.expires_at > datetime.now(timezone.utc)
        )
    )
    tokens = result.scalars().all()
    return [
        {
            "session_id": t.id,
            "created_at": t.created_at.isoformat(),
            "expires_at": t.expires_at.isoformat()
        }
        for t in tokens
    ]


@router.delete(
    "/me/sessions/{session_id}",
    summary="Revoke session",
    description="Revokes a specific session/refresh token.",
)
async def revoke_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.id == session_id,
            RefreshToken.user_id == current_user.id
        )
    )
    token = result.scalar_one_or_none()
    if not token:
        raise HTTPException(status_code=404, detail="Session not found.")
    
    token.revoked = True
    await db.commit()
    return {"message": "Session successfully revoked."}


@router.get(
    "/me/export",
    summary="Export user data",
    description="Exports all user account data and chat history in JSON format.",
)
async def export_data(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Fetch user details + conversations
    result = await db.execute(
        select(User)
        .options(selectinload(User.conversations).selectinload(Conversation.messages))
        .where(User.id == current_user.id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    data = {
        "user_id": user.id,
        "email": user.email,
        "plan": user.plan,
        "created_at": user.created_at.isoformat(),
        "conversations": [
            {
                "chat_id": c.id,
                "title": c.title,
                "created_at": c.created_at.isoformat(),
                "messages": [
                    {
                        "id": m.id,
                        "role": m.role,
                        "content": m.content,
                        "created_at": m.created_at.isoformat()
                    }
                    for m in c.messages
                ]
            }
            for c in user.conversations
        ]
    }
    return data
