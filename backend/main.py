from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
from database import init_db
from routers import auth, files, jobs
import websocket

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # Start Redis subscriber for job updates
    task = asyncio.create_task(websocket.redis_subscriber())
    yield
    task.cancel()

app = FastAPI(
    title="FileFlow API",
    description="Distributed asynchronous file-processing platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(files.router, prefix="/api/files", tags=["files"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(websocket.router)


@app.get("/")
async def root():
    return {"message": "FileFlow API is running"}


@app.get("/health")
async def health():
    return {"status": "ok"}
