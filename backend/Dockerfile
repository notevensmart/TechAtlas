FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/backend

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend /app/backend
COPY ingestion /app/ingestion

WORKDIR /app/backend

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

