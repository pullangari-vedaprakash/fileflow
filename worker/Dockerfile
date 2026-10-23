FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend for shared models, database & config modules
COPY ../backend /app/backend
COPY . /app/worker

WORKDIR /app/worker
ENV PYTHONPATH=/app/backend:/app/worker

CMD ["python", "worker.py"]
