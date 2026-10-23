from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
from database import init_db
from routers import auth, files, jobs, results
import websocket


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # Start background Redis subscriber for real-time WebSocket job updates
    subscriber_task = asyncio.create_task(websocket.redis_subscriber())
    yield
    subscriber_task.cancel()
    try:
        await subscriber_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="FileFlow API",
    description="Distributed asynchronous file-processing platform with priority aging",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Support both /api/<resource> (frontend convention) and /<resource> (standard REST spec)
for prefix in ["/api", ""]:
    app.include_router(auth.router, prefix=f"{prefix}/auth", tags=["auth"])
    app.include_router(files.router, prefix=f"{prefix}/files", tags=["files"])
    app.include_router(jobs.router, prefix=f"{prefix}/jobs", tags=["jobs"])
    app.include_router(results.router, prefix=f"{prefix}/results", tags=["results"])

app.include_router(websocket.router)


@app.get("/")
async def root():
    return {
        "service": "FileFlow API",
        "status": "online",
        "version": "1.0.0",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
