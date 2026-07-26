from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

import config

router = APIRouter()

PORTRAIT_EXTENSIONS = ("jpg", "jpeg", "png", "webp")


# Resolve a character's portrait by name alone, regardless of which extension it was
# saved with, and serve it straight from disk (no frontend rebuild needed for new
# or uploaded avatars - upload_avatar writes here at runtime).
@router.get("/portraits/{slug}")
def get_portrait(slug: str):
    for ext in PORTRAIT_EXTENSIONS:
        path = config.PORTRAITS_DIR / f"{slug}.{ext}"
        if path.is_file():
            # Portraits can be replaced at runtime (re-upload) without the filename changing,
            # so browsers must always revalidate rather than trusting a stale cached copy.
            return FileResponse(path, headers={"Cache-Control": "no-cache"})
    raise HTTPException(status_code=404, detail="portrait not found")
