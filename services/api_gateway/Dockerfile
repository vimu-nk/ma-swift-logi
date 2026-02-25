# ── Stage 1: Builder ──────────────────────────
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_NO_INTERACTION=1

RUN pip install --no-cache-dir poetry==1.8.*

# Use /app so venv shebangs match the runtime WORKDIR
WORKDIR /app

# Install dependencies first (layer caching)
COPY services/api_gateway/pyproject.toml ./
RUN poetry lock --no-update && \
    poetry install --only main --no-root

# Copy service code and shared lib
COPY services/api_gateway/app/ app/
COPY services/api_gateway/gunicorn_conf.py ./
COPY services/api_gateway/static/ static/
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
COPY --from=builder /app/static static
COPY --from=builder /app/shared shared

USER appuser

EXPOSE 8000

CMD ["gunicorn", "app.main:app", "-c", "gunicorn_conf.py"]
