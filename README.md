# FileFlow

Distributed asynchronous file-processing platform with priority scheduling + aging, worker recovery, and live progress.

## Architecture
```
React (Vercel) → FastAPI → PostgreSQL (metadata)
                         → Redis (priority sorted set + Pub/Sub)
                         → MinIO / S3 (files + results)
                         → Python Workers
```

## Features
- JWT auth
- File upload (images + PDFs) → MinIO
- Priority job queue with aging (Redis sorted set)
- Image processing (resize, compress, thumbnail)
- PDF processing (extract text, first-page preview)
- Retry (max 3) + cancel
- Worker heartbeat + stale job recovery
- Live progress via WebSocket (Redis Pub/Sub bridge)
- Presigned result downloads
- Idempotent job claiming

## Local Setup

```bash
# 1. Infrastructure
docker-compose up -d

# 2. Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
uvicorn main:app --reload --port 8000

# 3. Worker (new terminal)
cd worker
PYTHONPATH=../backend python worker.py

# 4. Frontend
cd frontend
npm install
npm start
```

MinIO console: http://localhost:9001 (minioadmin / minioadmin123)

## Interview Talking Points
- Why priority + aging? Pure priority starves low-priority jobs.
- At-least-once delivery + idempotent processing.
- Worker failure detection via heartbeat and automatic requeue.
- Separation of control plane (FastAPI) and data plane (workers).
- Object storage abstraction (MinIO local → S3-compatible in prod).

## Deployment Notes
- Frontend → Vercel
- FastAPI → Render / Railway / Fly.io free tier
- Worker → same or a long-running free instance
- PostgreSQL → Neon / Supabase free
- Redis → Upstash free
- Object storage → Cloudflare R2 / Backblaze B2 free tier
