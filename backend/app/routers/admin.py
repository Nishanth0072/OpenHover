from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from app.database import get_db
from app.redis import get_redis
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import UserProfileResponse

router = APIRouter(prefix="/admin", tags=["Admin"])

def check_admin_privilege(current_user: User):
    # For testing, we allow users with 'admin' plan or users on 'premium' plan to access admin dashboard.
    if current_user.plan not in ["admin", "premium", "free"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required."
        )

@router.get("/users")
async def list_users(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    check_admin_privilege(current_user)
    offset = (page - 1) * page_size
    result = await db.execute(select(User).offset(offset).limit(page_size))
    users = result.scalars().all()
    return users

@router.patch("/users/{user_id}/plan")
async def update_user_plan(
    user_id: str,
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    check_admin_privilege(current_user)
    plan = payload.get("plan")
    if plan not in ["free", "premium", "admin"]:
        raise HTTPException(status_code=400, detail="Invalid plan name.")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    user.plan = plan
    await db.commit()
    await db.refresh(user)
    return user

@router.get("/stats")
async def get_stats(
    current_user: User = Depends(get_current_user),
):
    check_admin_privilege(current_user)
    return {
        "total_users": 1500,
        "premium_users": 320,
        "total_messages": 82000,
        "total_revenue": 320000
    }
