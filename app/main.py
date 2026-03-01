"""iDiag — main entry point.

Launches FastAPI server in a background thread, then opens pywebview window.
Falls back to browser-only mode if pywebview is unavailable.
"""

import asyncio
import contextlib
import logging
import sys
import threading
import time
from pathlib import Path
from typing import Generator

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api import devices, diagnostics, inventory, verification, websocket
from app.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# -- FastAPI app --

app = FastAPI(title="iDiag", version=settings.app_version)

# Routes
app.include_router(devices.router)
app.include_router(diagnostics.router)
app.include_router(verification.router)
app.include_router(inventory.router)
app.include_router(websocket.router)

# Static files
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Templates
templates_dir = Path(__file__).parent / "static"
templates = Jinja2Templates(directory=str(templates_dir))


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "app_name": settings.app_name,
        "version": settings.app_version,
    })


@app.on_event("startup")
async def startup():
    """Start background device polling."""
    asyncio.create_task(websocket.device_poll_loop())
    logger.info("iDiag v%s started on http://%s:%d", settings.app_version, settings.host, settings.port)


# -- Uvicorn background server --

class BackgroundServer(uvicorn.Server):
    @contextlib.contextmanager
    def run_in_thread(self) -> Generator:
        thread = threading.Thread(target=self.run, daemon=True)
        thread.start()
        try:
            while not self.started:
                time.sleep(0.01)
            yield
        finally:
            self.should_exit = True
            thread.join(timeout=5)


def main():
    config = uvicorn.Config(
        app=app,
        host=settings.host,
        port=settings.port,
        log_level="info",
    )
    server = BackgroundServer(config=config)

    with server.run_in_thread():
        url = f"http://{settings.host}:{settings.port}/"

        # Try pywebview first (native window)
        try:
            import webview
            window = webview.create_window(
                title=f"{settings.app_name} v{settings.app_version}",
                url=url,
                width=1280,
                height=900,
                resizable=True,
            )
            # gui="gtk" on Linux, auto-detect on other platforms
            gui_backend = "gtk" if sys.platform == "linux" else None
            webview.start(gui=gui_backend, debug=settings.debug)
        except ImportError:
            logger.warning("pywebview not available, running in browser-only mode")
            logger.info("Open %s in your browser", url)
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass

    logger.info("iDiag shutting down")


if __name__ == "__main__":
    main()
