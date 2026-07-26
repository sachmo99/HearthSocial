from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

import shared

router = APIRouter()


# Resolve a character's portrait by name alone, regardless of which extension it was
# saved with, and serve it straight from disk (no frontend rebuild needed for new
# or uploaded avatars - upload_avatar writes here at runtime).
@router.get("/portraits/{slug}")
def get_portrait(slug: str):
    path = shared.resolve_portrait_path(slug)
    if path is None:
        raise HTTPException(status_code=404, detail="portrait not found")
    # Portraits can be replaced at runtime (re-upload) without the filename changing,
    # so browsers must always revalidate rather than trusting a stale cached copy.
    return FileResponse(path, headers={"Cache-Control": "no-cache"})
