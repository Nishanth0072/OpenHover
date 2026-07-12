from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis
from datetime import datetime, timezone

from app.database import get_db
from app.redis import get_redis
from app.dependencies import get_current_user
from app.models.user import User
from app.middleware.rate_limiter import check_rate_limit

router = APIRouter(prefix="/billing", tags=["Billing"])

@router.get("/plans")
async def get_plans():
    return [
        {
            "id": "premium",
            "name": "Premium Plan",
            "price": 1000,
            "currency": "USD"
        }
    ]

@router.post("/subscribe")
async def subscribe(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    if not await check_rate_limit(redis_client, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please wait.",
        )

    plan_id = payload.get("plan_id")
    if plan_id != "premium":
        raise HTTPException(status_code=400, detail="Invalid plan selected.")

    # Update user plan directly (Mock payment success)
    current_user.plan = "premium"
    await db.commit()
    await db.refresh(current_user)

    return {
        "checkout_url": f"http://localhost:8000/billing/mock-success?user_id={current_user.id}"
    }

@router.post("/cancel")
async def cancel_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    if not await check_rate_limit(redis_client, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please wait.",
        )

    current_user.plan = "free"
    await db.commit()
    await db.refresh(current_user)
    return {"message": "Subscription cancelled successfully."}

@router.post("/webhook")
async def stripe_webhook():
    return {"status": "success"}

@router.get("/invoices")
async def get_invoices(
    current_user: User = Depends(get_current_user),
):
    if current_user.plan != "premium":
        return []
    return [
        {
            "id": "inv_12345",
            "amount": 1000,
            "date": datetime.now(timezone.utc).isoformat(),
            "pdf_url": "http://localhost:8000/billing/invoices/inv_12345.pdf"
        }
    ]
