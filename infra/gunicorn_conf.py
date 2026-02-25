"""Gunicorn configuration for production ASGI deployment.

Usage:
    gunicorn app.main:app -c gunicorn_conf.py
"""

import multiprocessing
import os

# ── Server Socket ─────────────────────────────
bind = f"0.0.0.0:{os.getenv('SERVICE_PORT', '8000')}"

# ── Worker Processes ──────────────────────────
workers = int(os.getenv("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "uvicorn.workers.UvicornWorker"
worker_tmp_dir = "/dev/shm"

# ── Timeouts ──────────────────────────────────
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))

# ── Logging ───────────────────────────────────
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info").lower()

# ── Process Naming ────────────────────────────
proc_name = os.getenv("SERVICE_NAME", "swifttrack")

# ── Security ──────────────────────────────────
limit_request_line = 8190
limit_request_fields = 100
limit_request_field_size = 8190

# ── Server Mechanics ─────────────────────────
preload_app = True
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "1000"))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", "50"))
