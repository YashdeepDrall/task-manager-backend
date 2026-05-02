from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.database import close_mongo_connection, connect_to_mongo
from app.routers import auth, dashboard, projects, tasks


FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
FRONTEND_ASSETS = FRONTEND_DIST / "assets"
FRONTEND_INDEX = FRONTEND_DIST / "index.html"

app = FastAPI(
    title="Project & Task Management API",
    description="Full-stack project and task management system built with FastAPI and MongoDB.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event() -> None:
    await connect_to_mongo()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await close_mongo_connection()


app.include_router(auth.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


if FRONTEND_ASSETS.exists():
    app.mount(
        "/assets",
        StaticFiles(directory=FRONTEND_ASSETS),
        name="frontend-assets",
    )


if FRONTEND_INDEX.exists():
    @app.get("/", include_in_schema=False)
    async def serve_frontend_index() -> FileResponse:
        return FileResponse(FRONTEND_INDEX)

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend_app(full_path: str) -> FileResponse:
        requested_file = FRONTEND_DIST / full_path
        if requested_file.is_file():
            return FileResponse(requested_file)
        return FileResponse(FRONTEND_INDEX)
