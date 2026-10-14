FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend backend
COPY database database
COPY legal-data legal-data

RUN useradd --create-home formlaw && mkdir -p /data/storage && chown -R formlaw /data /srv
USER formlaw
WORKDIR /srv/backend

# Apply migrations, then serve. Seeding demo data is a separate, explicit step (DEMO_MODE only).
CMD ["sh", "-c", "python -m alembic upgrade head && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"]
