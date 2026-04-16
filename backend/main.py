import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── Startup validation — exits with a clear message if .env is incomplete ──
from backend.config import load_config
cfg = load_config(strict=True)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.middleware.security import SecurityHeadersMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("k")

app = FastAPI(
    title="K — Voice Assistant",
    version="1.0.0",
    docs_url="/docs",     # disable in prod by setting to None
    redoc_url=None,
)

# Security headers on every response
app.add_middleware(SecurityHeadersMiddleware)

# CORS — localhost only
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        cfg.frontend_origin,
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# ── Routers ────────────────────────────────────────────────────────────────
from backend.routes import auth, command, events  # noqa: E402

app.include_router(auth.router,    prefix="/auth",   tags=["auth"])
app.include_router(command.router,                   tags=["command"])
app.include_router(events.router,  prefix="/events", tags=["events"])

# ── Frontend static files ──────────────────────────────────────────────────
_frontend = Path(__file__).parent.parent / "frontend"
if _frontend.exists():
    app.mount("/static", StaticFiles(directory=str(_frontend)), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_frontend():
        return FileResponse(
            str(_frontend / "index.html"),
            headers={"Cache-Control": "no-store"},
        )


# ── Startup / shutdown hooks ───────────────────────────────────────────────
@app.on_event("startup")
async def on_startup():
    log.info("K is starting up…")
    # Ensure token directory exists with correct permissions
    from backend.services.token_store import _ensure_token_dir
    _ensure_token_dir()
    log.info("Token directory ready")
    log.info("K is ready at http://localhost:%s", cfg.port)


@app.on_event("shutdown")
async def on_shutdown():
    log.info("K is shutting down")


# ── Health ─────────────────────────────────────────────────────────────────
@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok", "service": "K Voice Assistant"}
