from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import db
import llama_client
from llama_client import LlamaServerUnavailable
from routers import chat, characters, feed, portraits, sessions

app = FastAPI()
# CORS middleware removed since frontend is served from same origin

app.include_router(characters.router)
app.include_router(sessions.router)
app.include_router(chat.router)
app.include_router(feed.router)
app.include_router(portraits.router)


@app.exception_handler(LlamaServerUnavailable)
async def llama_unavailable_handler(request: Request, exc: LlamaServerUnavailable):
    return JSONResponse(
        status_code=503,
        content={"detail": "The AI model server is unavailable - make sure llama-server is running."},
    )


@app.on_event("startup")
def startup() -> None:
    conn = db.get_db()
    db.sync_characters_from_disk(conn)


@app.get("/api/health")
async def health_check():
    ok = await llama_client.health()
    return {"llama_server": ok}


# Serve built frontend static files
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

    @app.get("/{path:path}")
    async def serve_spa(path: str):
        # Serve index.html for all routes except /api and /assets
        if path.startswith("api/"):
            raise HTTPException(status_code=404)
        file_path = frontend_dist / path if path else frontend_dist / "index.html"
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(frontend_dist / "index.html")
