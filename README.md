# SwiftTrack — Middleware Architecture

Production-grade microservices middleware for logistics order processing.

## Architecture

| Service | Port | Purpose |
|---------|------|---------|
| `api_gateway` | 8000 | HTTP entry point, routes to downstream services |
| `order_service` | 8001 | Order management (PostgreSQL + RabbitMQ) |
| `integration_service` | 8002 | Orchestrates calls to external systems |
| `notification_service` | 8003 | Consumes events, sends notifications |
| `cms_mock_soap` | 8004 | Mock SOAP CMS endpoint |
| `ros_mock_rest` | 8005 | Mock REST ROS endpoint |
| `wms_mock_tcp` | 9000/9001 | Mock TCP WMS (9000=TCP, 9001=health) |

**Infrastructure:** PostgreSQL 16, RabbitMQ 3.13 (management UI at `:15672`)

## Quick Start

```bash
# 1. Copy environment file
cp .env.example .env

# 2. Build all images
docker compose build

# 3. Start everything
docker compose up -d

# 4. Check service health
curl http://localhost:8000/health/live

# 5. View logs
docker compose logs -f api_gateway

# 6. Stop
docker compose down
```

## Tech Stack

- Python 3.12 · FastAPI · Pydantic v2
- SQLAlchemy 2.x (async) · Alembic
- aio-pika (async RabbitMQ) · httpx
- Structlog · Poetry · Docker multi-stage builds
- Gunicorn + Uvicorn (production ASGI)
