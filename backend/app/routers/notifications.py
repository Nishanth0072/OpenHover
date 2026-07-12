from fastapi import APIRouter, Depends, HTTPException, status
import redis.asyncio as aioredis
from app.redis import get_redis
from app.dependencies import get_current_user
from app.models.user import User
from app.middleware.rate_limiter import check_rate_limit

router = APIRouter(tags=["Notifications & Support"])

# In-memory mock notifications store
MOCK_NOTIFICATIONS = [
    {
        "id": "notif_001",
        "title": "Welcome to Open-Brain!",
        "message": "Start typing prompts to get assistant answers.",
        "read": False
    },
    {
        "id": "notif_002",
        "title": "New Model Available",
        "message": "We have added Gemma 3:4b to the Ollama provider list.",
        "read": False
    }
]

@router.get("/notifications")
async def get_notifications(
    current_user: User = Depends(get_current_user),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    if not await check_rate_limit(redis_client, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please wait.",
        )
    return MOCK_NOTIFICATIONS

@router.patch("/notifications/{id}/read")
async def mark_notification_read(
    id: str,
    current_user: User = Depends(get_current_user),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    if not await check_rate_limit(redis_client, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please wait.",
        )
    for n in MOCK_NOTIFICATIONS:
        if n["id"] == id:
            n["read"] = True
            return n
    raise HTTPException(status_code=404, detail="Notification not found.")

@router.post("/support/contact")
async def submit_support_contact(payload: dict):
    name = payload.get("name")
    email = payload.get("email")
    message = payload.get("message")
    if not name or not email or not message:
        raise HTTPException(status_code=400, detail="Missing required support fields.")
    return {"message": "Support ticket created successfully."}

@router.get("/legal/terms")
async def get_terms():
    return {
        "title": "Terms of Service",
        "content": "By using Open-Brain, you agree to these basic terms...",
        "version": "1.0.0"
    }

@router.get("/legal/privacy")
async def get_privacy():
    return {
        "title": "Privacy Policy",
        "content": "We value your privacy. We process prompts locally and securely...",
        "version": "1.0.0"
    }
