# SwiftTrack — Middleware Architecture

Production-grade microservices middleware for logistics order processing.

## Architecture Documentation

A highly detailed architectural breakdown, specifically addressing the **SCS2314 Assignment 4** challenges, integration strategies, and the choice of Microservices over Monolithic/ESB solutions can be found here:
📄 [**architecture_documentation.md**](./architecture_documentation.md)

## Architecture

| Service                | Port      | Purpose                                         |
| ---------------------- | --------- | ----------------------------------------------- |
| `api_gateway`          | 8000      | HTTP entry point, routes to downstream services |
| `order_service`        | 8001      | Order management (PostgreSQL + RabbitMQ)        |
| `integration_service`  | 8002      | Orchestrates calls to external systems          |
| `notification_service` | 8003      | Consumes events, sends notifications            |
| `cms_mock_soap`        | 8004      | Mock SOAP CMS endpoint                          |
| `ros_mock_rest`        | 8005      | Mock REST ROS endpoint                          |
| `wms_mock_tcp`         | 9000/9001 | Mock TCP WMS (9000=TCP, 9001=health)            |

**Infrastructure:** PostgreSQL 16, RabbitMQ 3.13 (management UI at `:15672`)

## Quick Start

```bash
# 1. Copy environment file
# Linux/macOS
cp .env.example .env

# Windows PowerShell
Copy-Item .env.example .env

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

## Access Points

- Landing page: `http://localhost:8000/`
- Login: `http://localhost:8000/login`
- Client dashboard: `http://localhost:8000/client`
- Driver dashboard: `http://localhost:8000/driver`
- Pickup dashboard: `http://localhost:8000/pickup`
- Delivery dashboard: `http://localhost:8000/delivery`
- Admin dashboard: `http://localhost:8000/admin`
- API docs (debug): `http://localhost:8000/docs`
- RabbitMQ management: `http://localhost:15672`

## API Endpoint Summary (`api_gateway`)

### Auth

- `POST /api/auth/login` — issue JWT access token
- `GET /api/auth/me` — current authenticated user

### Orders

- `POST /api/orders` — create a new order (returns `202 Accepted`)
- `GET /api/orders` — list orders (`status`, `client_id`, `driver_id_any`, pagination)
- `GET /api/orders/{order_id}` — fetch a single order
- `PATCH /api/orders/{order_id}/status` — update order status (driver/admin roles)

### Real-time Tracking (WebSocket)

- `WS /ws/tracking/{client_id}` — subscribe to live order updates

All `/api/orders*` routes require `Authorization: Bearer <token>`.

## Notes

- `order_service` runs Alembic migrations automatically on container startup.
- For local development, Docker Compose publishes service ports (`8000`–`8005`, `9000`, `9001`) to the host; for production, restrict exposure behind a reverse proxy/firewall.

## Features

- **Modernized UI**: Built with responsive Glassmorphism design and Phosphor Icons for professional dashboards.
- **Enhanced Order Management**: Granular tracking for `sender_name` and `receiver_name` appended to an intuitive `ODR-XXXXXXXX` display ID format.
- **Delivery Management Modal Workflows**: Employs non-blocking internal DOM modals for driver interactions.
- **3-Strike Delivery Logic**: Sophisticated state machine handling failed delivery attempts by gracefully resetting overarching statuses to `AT_WAREHOUSE` before failing out logic circuits.

## Tech Stack

- **Core**: Python 3.12 · FastAPI · Pydantic v2
- **Data**: PostgreSQL 16 · SQLAlchemy 2.0 (async) · asyncpg · Alembic
- **Messaging**: RabbitMQ 3.13 · aio-pika
- **Integration**: httpx · python-jose (JWT)
- **Infrastructure**: Docker Compose (multi-stage builds) · Gunicorn + Uvicorn
- **Dev Tools**: Poetry · Pytest · Ruff
