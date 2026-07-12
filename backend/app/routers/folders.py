from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from app.database import get_db
from app.redis import get_redis
from app.models.user import User
from app.models.folder import Folder
from app.schemas.folder import FolderCreate, FolderResponse
from app.schemas.auth import MessageResponse
from app.dependencies import get_current_user
from app.middleware.rate_limiter import check_rate_limit

router = APIRouter()

@router.get(
    "",
    response_model=list[FolderResponse],
    summary="List all folders",
    description="Returns a list of folders created by the user.",
)
async def list_folders(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    if not await check_rate_limit(redis_client, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please wait.",
        )

    result = await db.execute(
        select(Folder)
        .where(Folder.user_id == current_user.id)
        .order_by(Folder.created_at.desc())
    )
    return result.scalars().all()


@router.post(
    "",
    response_model=FolderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a folder",
    description="Creates a new folder to organize conversation threads.",
)
async def create_folder(
    payload: FolderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    if not await check_rate_limit(redis_client, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please wait.",
        )

    # Check for duplicate folder name
    result = await db.execute(
        select(Folder).where(
            Folder.user_id == current_user.id,
            Folder.name == payload.name
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A folder with this name already exists.",
        )

    folder = Folder(
        user_id=current_user.id,
        name=payload.name,
    )
    db.add(folder)
    await db.commit()
    await db.refresh(folder)
    return folder


@router.patch(
    "/{folder_id}",
    response_model=FolderResponse,
    summary="Rename folder",
    description="Renames an existing folder.",
)
async def rename_folder(
    folder_id: str,
    payload: FolderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    if not await check_rate_limit(redis_client, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please wait.",
        )

    result = await db.execute(
        select(Folder).where(
            Folder.id == folder_id,
            Folder.user_id == current_user.id
        )
    )
    folder = result.scalar_one_or_none()
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found.",
        )

    folder.name = payload.name
    await db.commit()
    await db.refresh(folder)
    return folder


@router.delete(
    "/{folder_id}",
    response_model=MessageResponse,
    summary="Delete folder",
    description="Deletes a folder. Conversations inside are preserved and un-filed.",
)
async def delete_folder(
    folder_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    if not await check_rate_limit(redis_client, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please wait.",
        )

    result = await db.execute(
        select(Folder).where(
            Folder.id == folder_id,
            Folder.user_id == current_user.id
        )
    )
    folder = result.scalar_one_or_none()
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found.",
        )

    await db.delete(folder)
    await db.commit()
    return {"message": "Folder deleted successfully. Conversations inside have been un-filed."}
