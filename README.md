# FileFlow

Distributed asynchronous file-processing platform with priority scheduling + dynamic aging, worker failure recovery, and real-time WebSocket progress updates.

---

## 1. What FileFlow Is

**FileFlow** is a production-style distributed asynchronous processing system designed to handle heavy media transformations (image resizing, compression, thumbnail generation, PDF text extraction, and first-page previews) reliably across a decoupled control plane (FastAPI) and scalable data plane (Python Workers).

Unlike toy CRUD apps, FileFlow implements:
- **Priority Aging**: Mathematical linear aging algorithm preventing low-priority starvation.
- **Worker Heartbeat & Fault Tolerance**: Automatic detection of dead workers and safe, distributed requeuing.
- **Idempotent Job Claiming**: Atomic state transitions protecting against duplicate message delivery.
- **Real-Time Live Progress**: Redis Pub/Sub bridged to WebSockets for sub-second browser telemetry.
- **Object Storage Abstraction**: S3-compatible signed URL downloads for zero-overhead binary transfers.

---

## 2. Architecture & Diagram

```
                                  +--------------------------+
                                  |      React Frontend      |
                                  |  (Modular SaaS Dashboard)|
                                  +-------------+------------+
                                                |
                               HTTP REST / Auth | WebSocket (/ws/{user_id})
                                                v
                                  +--------------------------+
                                  |     FastAPI Backend      |
                                  |   (Control & Validation) |
                                  +-----+-------+-------+----+
                                        |       |       |
                 +----------------------+       |       +----------------------+
                 v                              v                              v
      +----------------------+       +----------------------+       +----------------------+
      | PostgreSQL (Neon/DB) |       | Redis (Upstash/Local)|       | Object Store (R2/S3) |
      | - Metadata & State   |       | - Priority Queue     |       | - Original Files     |
      | - Indexes & Cascades |       | - Pub/Sub Progress   |       | - Processed Artifacts|
      | - Worker Registry    |       | - Distributed Locks  |       | - Presigned URLs     |
      +----------------------+       +----------+-----------+       +----------+-----------+
                 ^                              |                              |
                 |                              | ZPOPMAX                      | Binaries
                 |                              v                              v
                 |               +---------------------------------------------+
                 +---------------+            Python Worker Engine             |
                  Heartbeats /   | - Scheduler (Aging Score Evaluation)        |
                  State Updates  | - Heartbeat Service (10s intervals)         |
                                 | - Recovery Service (Redis Lock guarded)     |
                                 | - Processors:                               |
                                 |     * ImageProcessor (Resize/Compress/Thumb)|
                                 |     * PDFProcessor (Text/Preview)           |
                                 +---------------------------------------------+
```

---

## 3. Request Flow

1. **User Authentication**: Client authenticates via `POST /api/auth/login` to obtain an encrypted JWT.
2. **Binary Upload**: Client uploads a file (`JPG`, `PNG`, `WebP`, or `PDF`) to `POST /api/files/upload`. File binary is validated for magic bytes, sanitized, and stored directly in Object Storage (`users/{user_id}/files/{uuid}.ext`). Metadata is written to PostgreSQL.
3. **Job Dispatch**: Client submits `POST /api/jobs/` specifying operations and priority (`HIGH`, `NORMAL`, `LOW`). The job is saved as `QUEUED` in PostgreSQL and enqueued into a Redis Sorted Set with its calculated scheduling score.
4. **Worker Processing**:
   - Worker pops highest-scoring job via `ZPOPMAX`.
   - Atomically claims the job (`UPDATE jobs SET status='PROCESSING' WHERE status='QUEUED'`).
   - Streams progress updates (0%, 30%, 60%, 100%) to Redis Pub/Sub.
   - Saves processed deliverables to Object Storage and stores records in `results`.
   - Updates PostgreSQL status to `COMPLETED`.
5. **Real-time Updates**: FastAPI's background subscriber receives Pub/Sub updates and pushes JSON events down the active WebSocket connection to the browser.
6. **Result Retrieval**: Client fetches generated artifacts via `GET /api/results/{id}/download`, receiving a direct presigned URL.

---

## 4. Job Lifecycle State Machine

```
              +-----------------------------------------------+
              |                                               |
              v                                               |
          [QUEUED] ---------(Worker Claim)---------> [PROCESSING]
              |                                               |
              | (User Cancel)                      +----------+----------+
              v                                    v                     v
          [CANCELLED]                         [COMPLETED]             [FAILED]
                                                                         |
                                                                         | (Retry if retries < 3)
                                                                         +---------> [QUEUED]
```

- **Valid Transitions**:
  - `QUEUED -> PROCESSING`
  - `PROCESSING -> COMPLETED`
  - `PROCESSING -> FAILED`
  - `QUEUED -> CANCELLED`
  - `FAILED -> QUEUED`
- **Invalid Transitions (Guarded)**:
  - `COMPLETED -> PROCESSING` (Blocked)
  - `CANCELLED -> PROCESSING` (Blocked)
  - `CANCELLED -> QUEUED` (Blocked; cancelled jobs cannot be retried)

---

## 5. Priority Scheduling & Mathematical Aging Algorithm

Pure priority queues starve low-priority tasks indefinitely when high-priority tasks continuously arrive. FileFlow implements linear priority aging:

### Formula
At any evaluation moment $t$:
$$\text{Effective Priority}(t) = \text{priority\_weight} + \alpha \times (t - t_{\text{created}})$$

Factoring out the common term $\alpha \times t$:
$$\text{Effective Priority}(t) = [\text{priority\_weight} - \alpha \times t_{\text{created}}] + \alpha \times t$$

Since $\alpha \times t$ increases at the exact same rate for all items in the queue, the sorting order is mathematically preserved by the static ranking score:
$$\text{Ranking Score} = \text{priority\_weight} - (\alpha \times t_{\text{created}})$$

- **Priority Weights**:
  - `HIGH`: 100
  - `NORMAL`: 50
  - `LOW`: 20
- **Aging Rate ($\alpha$)**: 1.0 point per second waited.

#### Proof of Starvation Prevention:
Suppose:
- **Job A** (`LOW`, weight 20) arrives at $T = 0$.
- **Job B** (`HIGH`, weight 100) arrives at $T = 90$.

At $T = 90$:
- Job A has waited 90 seconds. Its effective score is $20 + (1.0 \times 90) = 110$.
- Job B has just arrived. Its effective score is $100 + (1.0 \times 0) = 100$.
- **Outcome**: $110 > 100 \implies$ Job A is popped before Job B. Starvation is prevented.

---

## 6. Retry System

- Maximum automatic/manual retries: **3**.
- On worker processing failure:
  - If `retry_count < max_retries`: automatically increments `retry_count += 1`, resets `progress = 0.0`, sets status to `QUEUED`, and re-enqueues into Redis with its original creation timestamp to preserve its aged priority.
  - If `retry_count >= max_retries`: marked `FAILED` with explicit error message.
- User manual retry (`POST /api/jobs/{id}/retry`):
  - Only allowed for `FAILED` jobs.
  - Checks `retry_count < max_retries` (4th retry rejected with HTTP 400).

---

## 7. Worker Heartbeat & Safe Stale Recovery

- **Heartbeat Service**: Every 10 seconds, each worker writes `worker_id`, `status` (`BUSY` or `IDLE`), `current_job_id`, and `last_heartbeat` to PostgreSQL.
- **Distributed Stale Recovery**: Every 30 seconds, workers run a recovery cycle protected by a Redis distributed lock (`SET recovery_lock <worker_id> NX EX 25`) to prevent race conditions across multiple worker instances.
- If a worker's heartbeat is older than 60 seconds and its status is `BUSY`:
  1. The assigned job is inspected.
  2. If recoverable (`retry_count < max_retries`), `retry_count` is incremented and the job is re-enqueued.
  3. If unrecoverable, the job is marked `FAILED`.
  4. The dead worker record is marked `DEAD`.

---

## 8. Idempotency

- **Atomic State Claiming**: Workers do not rely on Redis pop alone. When popping a job, they execute:
  ```sql
  UPDATE jobs SET status = 'PROCESSING', started_at = NOW(), progress = 0.0
  WHERE id = :job_id AND status = 'QUEUED';
  ```
  If `rowcount == 0`, another worker already claimed the job or it was cancelled. The worker safely aborts.
- **Idempotent Artifact Storage**: If a retried job runs again, previous records in `results` are atomically deleted before new results are inserted.

---

## 9. Real-Time WebSocket Progress

```text
Worker (Pushes update) -> Redis Pub/Sub ('job_updates') -> FastAPI (Background subscriber) -> WebSocket (/ws/{user_id}) -> React Client
```
Progress updates update live without page reload at key transformation checkpoints (0%, 30%, 60%, 100%).

---

## 10. Database Schema

PostgreSQL tables with appropriate indexes:

- **`users`**: `id`, `email`, `password_hash`, `created_at`
- **`files`**: `id`, `user_id`, `original_name`, `storage_key`, `mime_type`, `extension`, `size`, `created_at`, `updated_at`, `deleted`
  - *Indexes*: `(user_id, created_at DESC)`
- **`jobs`**: `id`, `user_id`, `file_id`, `operations`, `priority`, `status`, `progress`, `retry_count`, `max_retries`, `error_message`, `created_at`, `started_at`, `completed_at`, `updated_at`
  - *Indexes*: `(user_id, created_at DESC)`, `(status, created_at)`, `(priority, created_at)`
- **`results`**: `id`, `job_id`, `type`, `storage_key`, `file_name`, `result_metadata`, `created_at`
  - *Indexes*: `job_id`
- **`workers`**: `id`, `status`, `current_job_id`, `last_heartbeat`, `created_at`
  - *Indexes*: `(last_heartbeat, status)`

---

## 11. Local Setup

### Prerequisites
- Python 3.12+
- Node.js 18+
- Docker & Docker Compose (or access to PostgreSQL, Redis, MinIO/S3)

### Quickstart with Docker Compose
```bash
# 1. Start all services (PostgreSQL, Redis, MinIO, Backend, Worker, Frontend)
docker-compose up --build -d

# Frontend: http://localhost:3000
# Backend API: http://localhost:8000/docs
# MinIO Console: http://localhost:9001 (minioadmin / minioadmin123)
```

### Manual Development Setup
```bash
# 1. Environment file
cp .env.example .env

# 2. Backend
cd backend
python -m venv .venv
source .venv/bin/activate  # Or on Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# 3. Worker (in a separate terminal)
cd worker
python worker.py

# 4. Frontend (in a separate terminal)
cd frontend
npm install
npm start
```

---

## 12. Deployment Architecture

| Component | Target Provider | Free Tier Support |
|-----------|-----------------|-------------------|
| **Frontend** | Vercel / Netlify | Free tier static hosting |
| **Backend** | Render / Railway / Fly.io | Free tier Web Service |
| **Worker** | Render / Railway / Fly.io | Background Worker |
| **Database** | Neon.tech / Supabase | Free tier PostgreSQL (Serverless) |
| **Queue** | Upstash | Free tier Serverless Redis |
| **Storage** | Cloudflare R2 | 10 GB free monthly S3-compatible |

---

## 13. API Endpoints

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `POST` | `/api/auth/register` | Register new user account | No |
| `POST` | `/api/auth/login` | Login and obtain JWT token | No |
| `GET` | `/api/auth/me` | Fetch authenticated profile | Yes |
| `POST` | `/api/files/upload` | Upload binary (magic bytes validation) | Yes |
| `GET` | `/api/files/` | List authenticated user files | Yes |
| `GET` | `/api/files/{id}` | Get file metadata | Yes |
| `POST` | `/api/jobs/` | Dispatch job to priority queue | Yes |
| `GET` | `/api/jobs/` | List user processing jobs | Yes |
| `GET` | `/api/jobs/{id}` | Inspect job state & telemetry | Yes |
| `POST` | `/api/jobs/{id}/retry` | Retry failed job (max 3) | Yes |
| `POST` | `/api/jobs/{id}/cancel` | Cancel queued job | Yes |
| `GET` | `/api/jobs/{id}/results`| List processed artifacts with presigned URLs | Yes |
| `GET` | `/api/results/{id}/download`| Direct presigned download endpoint | Yes |
| `WS` | `/ws/{user_id}` | WebSocket stream for live progress | Yes |

---

## 14. Testing

A complete automated test suite is located in `/tests`:

```bash
# Run full suite
python -m pytest tests/ -v
```

### Test Coverage
- `tests/test_foundation.py`: Settings, Neon DB, Upstash Redis, Cloudflare R2 connectivity.
- `tests/test_database.py`: Schema creation, composite indexes, cascades, CRUD.
- `tests/test_auth.py`: Registration, duplicate prevention, password hashing, JWT expiration, unauthorized access.
- `tests/test_files.py`: MIME type validation, file signatures (magic bytes), path traversal sanitization, user isolation.
- `tests/test_jobs.py`: Job dispatch, operation validation, queue synchronization, cancellation, retry limits.
- `tests/test_scheduling.py`: Priority ordering, mathematical linear aging, starvation prevention.
- `tests/test_worker.py`: End-to-end ImageProcessor and PDFProcessor execution, atomic claiming, heartbeat, stale worker recovery.
