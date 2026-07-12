import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import FileResponse
import redis.asyncio as aioredis

from app.redis import get_redis
from app.dependencies import get_current_user
from app.models.user import User
from app.middleware.rate_limiter import check_rate_limit

router = APIRouter(tags=["Attachments"])

UPLOAD_DIR = "data/attachments"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/chats/{chat_id}/attachments", status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    chat_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    if not await check_rate_limit(redis_client, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please wait.",
        )

    file_id = f"att_{uuid.uuid4().hex[:10]}"
    extension = os.path.splitext(file.filename)[1]
    saved_filename = f"{file_id}{extension}"
    filepath = os.path.join(UPLOAD_DIR, saved_filename)
    
    with open(filepath, "wb") as buffer:
        buffer.write(await file.read())
        
    return {
        "id": file_id,
        "filename": file.filename,
        "content_type": file.content_type,
        "size_bytes": os.path.getsize(filepath),
        "url": f"http://localhost:8000/attachments/{saved_filename}"
    }

@router.get("/attachments/{filename}")
async def download_attachment(
    filename: str,
    current_user: User = Depends(get_current_user),
):
    filepath = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Attachment not found")
    return FileResponse(filepath)

@router.delete("/attachments/{filename}")
async def delete_attachment(
    filename: str,
    current_user: User = Depends(get_current_user),
):
    filepath = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Attachment not found")
    os.remove(filepath)
    return {"message": "Attachment deleted."}
