"""Production wrapper: AEGIS API plus the exported frontend."""

from pathlib import Path

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.app.main import app


ROOT = Path(__file__).resolve().parent
FRONTEND_OUT = ROOT / "frontend" / "out"

if FRONTEND_OUT.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_OUT, html=True), name="frontend")
else:

    @app.get("/")
    async def missing_export() -> FileResponse:
        return FileResponse(ROOT / "README.md")
