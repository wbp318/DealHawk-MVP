FROM python:3.13-slim

WORKDIR /app

# Install system dependencies for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy full project
COPY . .

# Default command — app server
CMD ["sh", "-c", "alembic upgrade head && uvicorn backend.api.app:app --host 0.0.0.0 --port 8000"]
