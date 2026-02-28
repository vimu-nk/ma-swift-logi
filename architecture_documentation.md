# SwiftTrack Middleware Architecture Documentation

## 1. Introduction

Swift Logistics (Pvt) Ltd. requires a highly scalable, resilient, and responsive "SwiftTrack" platform to integrate a heterogeneous ecosystem of backend systems (a legacy CMS via SOAP, a cloud-based ROS via REST, and an on-premise WMS via TCP/IP).

The primary challenge is replacing siloed, manual systems with a modern middleware platform capable of seamless, real-time tracking, high-volume asynchronous order processing, and fault-tolerant transaction management. This documentation details the design, rationale, and implementation of the proposed microservices-based middleware architecture that meets these operational requirements.

---

## 2. Solution Architecture

The SwiftTrack platform utilizes a **Microservices Architecture with Message-Oriented Middleware (RabbitMQ)** to ensure loose coupling, high availability, and easy independent scalability of its sub-domains.

### 2.1 Conceptual Architecture

Conceptually, the system acts as a central hub (Middleware) that orchestrates flow between front-facing clients (Web Portal & Driver App) and disparate backend systems.

High-level flow:

- Clients (Browser dashboards / Driver UI) connect through `api_gateway`.
- `order_service` persists canonical order state and emits domain events.
- `integration_service` orchestrates CMS (SOAP), WMS (TCP), and ROS (REST) calls.
- `notification_service` consumes events and republishes notification-ready updates.
- `api_gateway` bridges RabbitMQ notification events to WebSocket clients.

### 2.2 Implementation Architecture

The practical implementations map the concepts to specific decoupled Python/FastAPI services connected via RabbitMQ and backed by PostgreSQL.

**Docker Compose Layout:**

- **`api_gateway` (Port 8000)**: Sole entry point, handles JWT authentication, and routes traffic.
- **`order_service` (Port 8001)**: Core CRUD logic for Orders, handles database persistence (`swifttrack-postgres`), and emits domain events.
- **`integration_service` (Port 8002)**: The Saga Orchestrator. Consumes new orders and orchestrates the distributed API calls out to external endpoints, translating formats (JSON to SOAP/XML or TCP).
- **`notification_service` (Port 8003)**: Listens for tracking updates and prepares notification payloads (email/push/alert events).
- **Infrastructure**: PostgreSQL 16 for persistent state; RabbitMQ 3.13 for asynchronous queuing and publish/subscribe routing.

---

## 3. Alternative Architectures & Rationale

As part of the design process, two alternative architectures were considered before finalizing the microservices design:

### Alternative 1: Monolithic Architecture with Point-to-Point Integration

- **Description**: A single massive backend application handles orders, integration translations, and notifications. Connecting directly point-to-point to the CMS, ROS, and WMS synchronously.
- **Drawbacks**: Point-to-point synchronous integrations lead to catastrophic blocking. If the ROS is slow during "Black Friday" sales, the entire order intake API freezes, angering clients. The system would be a single point of failure and difficult to scale (you'd have to scale the whole monolith just because route optimization is overloaded).

### Alternative 2: Centralized Enterprise Service Bus (ESB)

- **Description**: Using a heavyweight ESB (like WSO2 or MuleSoft) to route, transform, and orchestrate all traffic and logic between the clients and the backends.
- **Drawbacks**: While great for transformation, centralized ESBs often become a monolithic bottleneck for logic ("smart pipes, dumb endpoints"). They are expensive to configure, hard to trace in modern CI/CD setups, and can introduce unwanted latency.

### Selected Architecture: Microservices + Lightweight Message Broker (Smart Endpoints, Dumb Pipes)

- **Rationale for Selection**: We selected a decentralized microservices approach joined by a lightweight message broker (RabbitMQ).
    - It fulfills **high-volume ingestion**: `order_service` instantly replies `202 Accepted` to clients and dumps the payload into RabbitMQ.
    - It provides **fault isolation**: If the `integration_service` crashes, the orders safely queue up in RabbitMQ until it restarts.
    - It provides **scalable flexibility**: We can horizontally scale the `integration_service` (to process more external API calls) completely independently of the `order_service` or `api_gateway`.

---

## 4. Architectural & Integration Patterns Used

The proposed solution applies several industry-standard enterprise integration patterns:

### 1. API Gateway Pattern

- **How it works**: The `api_gateway` service is the single ingress point into the cluster. It intercepts all frontend traffic.
- **Rationale**: Prevents clients from needing to know internal network topologies. It centralizes cross-cutting concerns (authentication, role-based authorization for Drivers vs. Clients) instead of duplicating auth logic in every microservice.

### 2. Publish/Subscribe (Pub-Sub) Pattern

- **How it works**: When `order_service` creates an order, it publishes an `order.created` event to a RabbitMQ Topic Exchange. Multiple services (like `integration_service` and `notification_service`) subscribe to this topic.
- **Rationale**: De-couples the order ingestion from the processing. The order service doesn't need to know _who_ requires the data, it just announces the state change.

### 3. Saga Pattern (Orchestration)

- **How it works**: Distributed transactions across external systems (CMS, WMS, ROS) are coordinated by the `integration_service` acting as an orchestrator. It executes steps sequentially and manages the state machine.

- **Rationale**: We cannot use strict ACID 2-Phase Commit (2PC) over HTTP/REST/SOAP. Saga handles distributed state gracefully. If step 3 (ROS) fails, the orchestrator publishes a failure event to trigger compensating logic (e.g., notifying the user or cancelling the WMS package prep).

### 4. Anti-Corruption Layer / Adapter Pattern

- **How it works**: The `integration_service` encapsulates all the messy translation logic. It adapts our internal SwiftTrack JSON standard to legacy SOAP/XML for the CMS and proprietary TCP socket streams for the WMS.
- **Rationale**: Protects our clean internal microservice data models from being polluted by legacy external schemas.

---

## 5. Addressing Specific Architectural Challenges

This section proves how the architecture explicitly solves the business challenges outline for "SwiftTrack".

### Challenge 1: Heterogeneous Systems Integration

- **Solution**: The `integration_service` is purpose-built for protocol translation. It speaks standard AMQP/JSON to internal RabbitMQ channels, but initiates outbound `httpx` SOAP XML calls to the CMS port 8004, `httpx` REST JSON calls to the ROS on port 8005, and raw Python socket streams to the WMS on port 9000.

### Challenge 2: Real-time Tracking and Notifications

- **Solution**: Tracking flows asynchronously. When a driver hits "Delivered", the `api_gateway` forwards the update to `order_service`. `order_service` updates the database and publishes `notification.status_changed` to RabbitMQ. `notification_service` consumes and republishes `notification.order_update`, and the `api_gateway` WebSocket bridge pushes updates to connected portal clients. This ensures the portal reflects change immediately without constant polling.

### Challenge 3: High-Volume, Asynchronous Processing

- **Solution**: During "Black Friday" surges, the `order_service` only performs one fast database `INSERT` and one RabbitMQ publish. It returns `HTTP 202 Accepted` immediately, _before_ engaging the slow external vendors (ROS/CMS). This guarantees the Client Portal UI never hangs or times out. RabbitMQ elegantly buffers the massive spike in traffic.

### Challenge 4: Distributed Transaction Management

- **Solution**: Leveraged via the Saga Orchestration pattern.
    - **Happy Path**: `order_service` -> RabbitMQ -> `integration_service` -> (`CMS` -> `WMS` -> `ROS`) -> Success update sent back to RabbitMQ.
    - **Failure Recovery**: If the ROS optimization fails because of an invalid address, the transaction cannot be left hanging. The `integration_service` halts the Saga and publishes an `order.saga_failed` event. The `order_service` listens for this, marks the order graph as `FAILED`, and the `notification_service` alerts the Client Portal that their address needs correction (a compensating action).

### Challenge 5: Scalability and Resilience

- **Solution**: Every component runs inside isolated Docker containers. Because the services hold no local state (stateless microservices), you can easily scale them by spinning up multiple instances of `integration_service` behind a load balancer, having them pull concurrently from the same rabbitmq queues (`Competing Consumers Pattern`). If a backend (like WMS) goes offline, the messages simply pile up in RabbitMQ without failing the ingestion API; once WMS recovers, `integration_service` resumes processing exactly where it left off.

---

## 6. Enhanced Delivery Workflow & Schema Architecture

Subsequent enhancements were applied to further align SwiftTrack with enterprise operational needs:

- **3-Strike Delivery Orchestration**: To prevent premature fulfillment failures, the internal state machine inside `update_order_status` was expanded. When a driver reports `DELIVERY_ATTEMPTED` and supplies reason notes via custom UI modals, the system transitions to an `AT_WAREHOUSE` holding state, dynamically replacing the assignment pool. A terminal `FAILED` status is only broadcast once `max_delivery_attempts` (3) is breached.
- **Schema Extension**: The backend database models (`SQLAlchemy`) and API Schemas (`Pydantic`) were seamlessly migrated via `Alembic` to propagate `sender_name`, `receiver_name`, and user-friendly `display_id` properties (e.g., `ODR-2A1B3C4D`). This retains the immutable core data link (UUID) whilst rendering recognizable identities for end-users.
- **UI Modernization**: Replaced unscalable visual assets (emojis) with professional scalable vectors (Phosphor Icons) and refactored the frontend logic stack to utilize custom asynchronous Promise-based DOM modals instead of thread-blocking OS prompt instances.

---

## 7. Data Flow & Database Architecture

To maintain the principles of microservices, data persistence is isolated. Centralizing the database can introduce a single point of failure and bottleneck cross-service communication.

- **`order_service` database**: Holds the canonical master data for the Order lifecycle ("Pending", "Delivered", driver bindings).
- **Data Synchronization**: No service directly queries another's database. Instead, data changes are replicated via RabbitMQ events (`order.created`, `notification.status_changed`).

---

## 8. Information Security & Zero-Trust Network

Protecting client data and business operational logic is paramount:

1.  **Authentication & Authorization:** The API Gateway mandates JWT (JSON Web Tokens). Clients only have access to their own Order IDs (enforced by the Gateway mapping JWT user identities to the query params), preventing data leakage between rival e-commerce vendors.
2.  **Internal Network Isolation (Zero Trust Concepts):** Services communicate on an isolated Docker network (`swifttrack-net`). In the current local Compose profile, multiple service ports are published for testing/inspection; production deployment should expose only the gateway (or reverse proxy) and keep internal ports private.
3.  **Encrypted Communications:** All external interactions (e.g., driver app over public 4G) should terminate via HTTPS/TLS at the API Gateway or a reverse proxy like NGINX mapping to `--port 8000` in production. Outbound calls to ROS/CMS from the `integration_service` should enforce SSL.
4.  **Credential Management:** Database passwords and RabbitMQ credentials are not hardcoded but strictly passed via `.env` file environment variables, ensuring they aren't leaked in version control.
5.  **Payload Validation:** Fast-API strictly enforces data types via Pydantic Models, which acts as a robust defense against malformed payload attacks and SQL Injection vectors before the data ever reaches the database layer.

---

## 9. Technology Stack & Implementation Details

The solution relies entirely on modern open-source technologies, strictly adhering to the assignment's constraints.

### Core Languages & Runtimes

- **Python 3.12**: The core programming language for all microservices, chosen for its mature ecosystem, async capabilities, and rapid development speed.
- **Docker & Docker Compose (v2)**: Containerization engine used to package services and manage the local deployment topology, ensuring environment parity between development and production.

### Frameworks & Libraries (Application Layer)

- **FastAPI (v0.115+)**: A high-performance web framework for building the REST APIs, chosen for its native async support (`asyncio`), automatic Swagger UI generation, and speed.
- **Uvicorn & Gunicorn**: `Uvicorn` provides the ASGI asynchronous web server implementation, managed by `Gunicorn` as the master process manager to handle worker scaling in production.
- **Pydantic (v2.x)**: Handles strict data validation, serialization, and settings management via `pydantic-settings`.
- **HTTPX**: An async HTTP client used by the API Gateway to proxy requests and by the Integration Service to make outbound REST and SOAP calls.

### Asynchronous Messaging & Integration

- **RabbitMQ (v3.13)**: The central message broker handling all publish/subscribe event routing.
- **aio-pika (v9.4+)**: A fully asynchronous Python client for RabbitMQ, allowing the services to publish and consume AMQP messages without blocking the FastAPI event loops.

### Data Persistence Layer

- **PostgreSQL (v16)**: The primary relational database used by the Order Service for ACID-compliant state storage.
- **SQLAlchemy 2.0 (Async)**: The Object-Relational Mapper (ORM) used for database interactions out of the Order Service.
- **asyncpg**: A high-performance async database driver for PostgreSQL.
- **Alembic**: Database migration tool used for tracking and applying schema changes.

### Security & Observability

- **python-jose**: Used by the API Gateway to decode and validate JSON Web Tokens (JWT) for authentication.
- **Structlog**: A structured logging library used across all services to output machine-readable JSON logs, crucial for tracing requests in a microservices environment.

### Development, Testing & Tooling

- **Poetry**: The modern dependency management and packaging tool used in place of standard `pip`/`requirements.txt` for deterministic builds.
- **Pytest & pytest-asyncio**: The testing framework utilized for writing unit and integration tests.
- **Ruff**: An extremely fast Python linter and code formatter used to maintain code quality and style standards.

---

## 10. Conclusion & Project Deliverable Summary

The "SwiftTrack" solution fulfills the requirements of the SCS2314 Assignment 4 by providing a tangible, runnable Dockerized prototype of a complex logistics pipeline.

By applying modern architectural patterns—specifically **Microservices**, **Saga Orchestration**, the **API Gateway Pattern**, and **Asynchronous Message Brokering**—the solution proves resilient against legacy system failures (CMS/WMS), is capable of massive scalability during peak e-commerce sales, and provides a highly responsive, real-time user experience for delivery tracking.
