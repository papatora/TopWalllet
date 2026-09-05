FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt psycopg2-binary

COPY config/ ./config/
COPY src/ ./src/

# results/, logs/, data/ are mounted as volumes
CMD ["python", "-m", "src.cli", "pipeline"]
