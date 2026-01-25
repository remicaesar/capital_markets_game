"""
FastAPI application setup for Capital Markets Game web UI
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from web.routes import router as game_router

# Get the directory where this file is located
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


def create_app() -> FastAPI:
    """Create and configure the FastAPI application"""

    app = FastAPI(
        title="Capital Markets Game",
        description="An ultra-realistic stock market simulation game",
        version="1.0.0"
    )

    # Add CORS middleware for development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routes
    app.include_router(game_router)

    # Serve static files
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    async def serve_index():
        """Serve the main HTML page"""
        return FileResponse(str(STATIC_DIR / "index.html"))

    @app.get("/health")
    async def health_check():
        """Health check endpoint"""
        return {"status": "healthy", "game": "Capital Markets Game"}

    return app


# Create the app instance
app = create_app()
