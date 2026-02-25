"""Gunicorn configuration for cms_mock_soap."""

import os

bind = f"0.0.0.0:{os.getenv('SERVICE_PORT', '8004')}"
workers = int(os.getenv("GUNICORN_WORKERS", "2"))
worker_class = "uvicorn.workers.UvicornWorker"
worker_tmp_dir = "/dev/shm"
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
graceful_timeout = 30
keepalive = 5
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info").lower()
proc_name = "cms_mock_soap"
preload_app = True
max_requests = 1000
max_requests_jitter = 50
