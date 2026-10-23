# FileFlow — System Architecture & Design

FileFlow is a production-grade distributed asynchronous file-processing platform engineered with priority scheduling, linear waiting-time aging, distributed worker heartbeat recovery, and real-time WebSocket progress dispatching.

---

## High-Level System Architecture

```text
                                 +-------------------------+
                                 |     React Frontend      |
                                 |  (Modular SaaS Client)  |
                                 +------------+------------+
                                              |
                              HTTP REST / JWT | WebSocket (/ws/{user_id})
                                              v
                                 +-------------------------+
                                 |     FastAPI Backend     |
                                 | (API, Auth, Validation) |
                                 +----+-------+-------+----+
                                      |       |       |
                 +--------------------+       |       +--------------------+
                 v                            v                            v
      +--------------------+       +--------------------+       +--------------------+
      | PostgreSQL (Neon)  |       |   Redis (Upstash)  |       | Object Store (R2)  |
      | - Users            |       | - ZSET Priority Q  |       | - Raw Uploads      |
      | - Files            |       | - Pub/Sub Channel  |       | - Derived Artifacts|
      | - Jobs & Results   |       | - Distributed Lock |       | - Presigned URLs   |
      | - Worker Registry  |       +----------+---------+       +----------+---------+
      +--------------------+                  |                            |
                 ^                            | ZPOPMAX                    | Download / Upload
                 |                            v                            v
                 |               +---------------------------------------------+
                 +---------------+            Python Worker Engine             |
                  Heartbeats /   | - Scheduler (Virtual Aging Scoring)         |
                  State Updates  | - Heartbeat Service (10s intervals)         |
                                 | - Stale Recovery (Distributed Lock)         |
                                 | - Modular Processors:                       |
                                 |     * ImageProcessor (Resize/Compress/Thumb)|
                                 |     * PDFProcessor (Text/Preview)           |
                                 +---------------------------------------------+
```

---

## Core System Subsystems

### 1. Job Lifecycle State Machine

Strict state transitions prevent arbitrary states and race conditions:

```text
    +-----------------------------------------------+
    |                                               |
    v                                               |
[QUEUED] ---------(Worker Claim)---------> [PROCESSING]
    |                                               |
    | (User Cancel)                      +----------+----------+
    v                                    v                     v
[CANCELLED]                         [COMPLETED]             [FAILED]
                                                               |
                                                               | (User Retry if retries < 3)
                                                               +---------> [QUEUED]
```

- **Illegal transitions prevented**:
  - `COMPLETED -> PROCESSING` (Rejected)
  - `CANCELLED -> PROCESSING` (Rejected)
  - `CANCELLED -> QUEUED` (Rejected; cannot retry a cancelled job)

---

### 2. Priority Scheduling & Mathematical Linear Aging

To eliminate starvation of `LOW` and `NORMAL` jobs in high-throughput environments, FileFlow implements linear priority aging:

- **Base Weights**:
  - `HIGH`: 100.0
  - `NORMAL`: 50.0
  - `LOW`: 20.0
- **Aging Rate ($\alpha$)**: 1.0 point per second waited.

#### Mathematical Formulation:
At any evaluation moment $t$:
$$P_{\text{eff}}(t) = \text{priority\_weight} + \alpha \cdot (t - t_{\text{created}})$$
Factoring out the shared time term $\alpha \cdot t$:
$$P_{\text{eff}}(t) = [\text{priority\_weight} - \alpha \cdot t_{\text{created}}] + \alpha \cdot t$$
Because $\alpha \cdot t$ is identical for every job in the queue at time $t$, the relative ordering is strictly preserved by the static ranking score:
$$\text{Score} = \text{priority\_weight} - (\alpha \cdot t_{\text{created}})$$

Jobs are popped from Redis using `ZPOPMAX`:
- A `LOW` job (20) created at $t=0$ achieves an effective score of 110 after 90 seconds.
- A newly arrived `HIGH` job (100) created at $t=90$ has an effective score of 100.
- Result: **The older LOW job outranks the new HIGH job ($110 > 100$), mathematically preventing starvation.**

---

### 3. Distributed Heartbeat & Stale Worker Recovery

1. **Heartbeat Loop**:
   - Each worker periodically updates its record in the `workers` table every 10 seconds (`last_heartbeat`, `status="BUSY"|"IDLE"`, `current_job_id`).
2. **Distributed Stale Recovery**:
   - To safely support multiple workers without duplicate requeueing, the recovery service acquires a Redis distributed lock (`SET recovery_lock <worker_id> NX EX 25`).
   - If a worker's heartbeat is older than 60 seconds and its status is `BUSY`, its active job is inspected:
     - If `retry_count < max_retries`: `retry_count` is incremented, the job is marked `QUEUED`, and re-enqueued in Redis with its original creation timestamp so it retains aged queue position.
     - If `retry_count >= max_retries`: marked `FAILED`.
   - The stale worker is marked `DEAD`.

---

### 4. Idempotency & Safe Job Claiming

- **Atomic Job Claiming**:
  Workers claim jobs directly in PostgreSQL via atomic row updates:
  ```sql
  UPDATE jobs 
  SET status = 'PROCESSING', started_at = NOW(), progress = 0.0
  WHERE id = :job_id AND status = 'QUEUED';
  ```
  If `rowcount == 0`, another worker already claimed the job or it was cancelled. The worker safely skips execution.
- **Idempotent Artifact Persistence**:
  Before writing derived results on retried runs, existing result records for that `job_id` are purged:
  ```sql
  DELETE FROM results WHERE job_id = :job_id;
  ```
