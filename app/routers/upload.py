"""Media / fayl yuklash — lokal `uploads/` papkasiga saqlaydi."""
import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, HTTPException, UploadFile, status

from app.config import settings
from app.deps import CurrentUser

router = APIRouter(prefix="/api/upload", tags=["upload"])

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
CHUNK = 1024 * 1024  # 1 MB


@router.post("")
async def upload_file(file: UploadFile, _: CurrentUser) -> dict:
    original = Path(file.filename or "file")
    ext = original.suffix.lower()
    media_type = "image" if ext in IMAGE_EXTS else "file"

    # xavfsiz noyob nom
    stored_name = f"{uuid.uuid4().hex}{ext}"
    dest = settings.UPLOAD_DIR / stored_name

    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    size = 0
    async with aiofiles.open(dest, "wb") as out:
        while chunk := await file.read(CHUNK):
            size += len(chunk)
            if size > max_bytes:
                await out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(
                    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    f"Fayl juda katta (max {settings.MAX_UPLOAD_MB} MB)",
                )
            await out.write(chunk)

    return {
        "media_url": f"/uploads/{stored_name}",
        "media_type": media_type,
        "media_name": original.name,
        "size": size,
    }
