FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ backend/
COPY simulator/ simulator/
COPY ml/ ml/
COPY dbc/ dbc/
COPY scripts/ scripts/

# Default command is overridden per-service in docker-compose.
CMD ["python", "scripts/run_backend.py"]
