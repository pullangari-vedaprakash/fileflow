from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Set
import asyncio
import json
import redis.asyncio as redis
from config import get_settings

settings = get_settings()
router = APIRouter()

# Simple in-memory connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)

    def disconnect(self, websocket: WebSocket, user_id: int):
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)

    async def send_to_user(self, user_id: int, message: dict):
        if user_id in self.active_connections:
            dead = []
            for ws in self.active_connections[user_id]:
                try:
                    await ws.send_json(message)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self.active_connections[user_id].discard(ws)


manager = ConnectionManager()


@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    await manager.connect(websocket, user_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)


async def notify_job_update(user_id: int, job_id: int, status: str, progress: float = None, error: str = None):
    payload = {
        "type": "job_update",
        "job_id": job_id,
        "status": status,
        "progress": progress,
        "error": error,
    }
    await manager.send_to_user(user_id, payload)


# Redis Pub/Sub listener (started from main.py lifespan)
async def redis_subscriber():
    r = redis.from_url(settings.redis_url, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe("job_updates")
    async for message in pubsub.listen():
        if message["type"] == "message":
            try:
                data = json.loads(message["data"])
                user_id = data.get("user_id")
                if user_id:
                    await manager.send_to_user(user_id, data)
            except Exception:
                pass
