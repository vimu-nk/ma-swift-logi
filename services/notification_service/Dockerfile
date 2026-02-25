# ── Stage 1: Builder ──────────────────────────
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_NO_INTERACTION=1

RUN pip install --no-cache-dir poetry==1.8.*

WORKDIR /app

COPY services/notification_service/pyproject.toml ./
RUN poetry lock --no-update && \
    poetry install --only main --no-root

COPY services/notification_service/app/ app/
COPY services/notification_service/gunicorn_conf.py ./
COPY shared/shared/ shared/

# ── Stage 2: Runtime ─────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

WORKDIR /app

COPY --from=builder /app/.venv .venv
COPY --from=builder /app/app app
COPY --from=builder /app/gunicorn_conf.py .
COPY --from=builder /app/shared shared

USER appuser

EXPOSE 8003

CMD ["gunicorn", "app.main:app", "-c", "gunicorn_conf.py"]
