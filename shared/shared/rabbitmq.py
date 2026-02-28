"""Shared RabbitMQ publisher/consumer utilities."""

from __future__ import annotations

import json
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable

import aio_pika
import structlog

logger = structlog.get_logger()

EVENT_VERSION = "1.0"


class RabbitMQClient:
    """Async RabbitMQ client with publish/consume support."""

    def __init__(self, url: str, service_name: str = "unknown"):
        self._url = url
        self._service_name = service_name
        self._connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._channel: aio_pika.abc.AbstractChannel | None = None
        self._exchange: aio_pika.abc.AbstractExchange | None = None

    async def connect(self) -> None:
        """Establish connection and declare exchange."""
        retries = 30
        delay_seconds = 2
        last_error: Exception | None = None

        for attempt in range(1, retries + 1):
            try:
                self._connection = await aio_pika.connect_robust(self._url)
                break
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "rabbitmq_connect_retry",
                    service=self._service_name,
                    attempt=attempt,
                    retries=retries,
                    delay_seconds=delay_seconds,
                    error=str(exc),
                )
                if attempt == retries:
                    raise
                await asyncio.sleep(delay_seconds)

        if self._connection is None:
            raise RuntimeError(
                f"Failed to establish RabbitMQ connection for {self._service_name}: {last_error}"
            )

        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=10)

        # Shared topic exchange for all order events
        self._exchange = await self._channel.declare_exchange(
            "swifttrack.events",
            aio_pika.ExchangeType.TOPIC,
            durable=True,
        )
        logger.info("rabbitmq_connected", service=self._service_name)

    async def close(self) -> None:
        """Gracefully close connection."""
        if self._connection and not self._connection.is_closed:
            await self._connection.close()
            logger.info("rabbitmq_disconnected", service=self._service_name)

    async def publish(
        self,
        routing_key: str,
        body: dict[str, Any],
    ) -> None:
        """Publish a JSON message to the topic exchange (legacy, no headers)."""
        if not self._exchange:
            raise RuntimeError("RabbitMQ not connected — call connect() first")

        message = aio_pika.Message(
            body=json.dumps(body, default=str).encode(),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        await self._exchange.publish(message, routing_key=routing_key)
        logger.info(
            "rabbitmq_published",
            routing_key=routing_key,
            service=self._service_name,
        )

    async def publish_event(
        self,
        routing_key: str,
        body: dict[str, Any],
        *,
        correlation_id: str | None = None,
        headers: dict[str, Any] | None = None,
    ) -> str:
        """
        Publish a JSON message with correlation / tracing headers.

        Auto-generates ``correlation_id`` and ``request_id`` when not
        supplied.  Always stamps ``timestamp`` and ``event_version``.

        Returns the correlation_id used.
        """
        if not self._exchange:
            raise RuntimeError("RabbitMQ not connected — call connect() first")

        cid = correlation_id or str(uuid.uuid4())
        rid = str(uuid.uuid4())
        ts = datetime.now(timezone.utc).isoformat()

        msg_headers: dict[str, Any] = {
            "correlation_id": cid,
            "request_id": rid,
            "timestamp": ts,
            "event_version": EVENT_VERSION,
            "source_service": self._service_name,
            **(headers or {}),
        }

        message = aio_pika.Message(
            body=json.dumps(body, default=str).encode(),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            correlation_id=cid,
            message_id=rid,
            timestamp=datetime.now(timezone.utc),
            headers=msg_headers,
        )
        await self._exchange.publish(message, routing_key=routing_key)
        logger.info(
            "rabbitmq_published",
            routing_key=routing_key,
            correlation_id=cid,
            request_id=rid,
            service=self._service_name,
        )
        return cid

    async def consume(
        self,
        queue_name: str,
        routing_keys: list[str],
        handler: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> asyncio.Task:
        """
        Declare a durable queue, bind it to routing keys, and start consuming.
        Returns the consumer asyncio.Task so callers can cancel it on shutdown.
        """
        if not self._channel or not self._exchange:
            raise RuntimeError("RabbitMQ not connected — call connect() first")

        queue = await self._channel.declare_queue(queue_name, durable=True)
        for key in routing_keys:
            await queue.bind(self._exchange, routing_key=key)

        async def _process(message: aio_pika.abc.AbstractIncomingMessage) -> None:
            async with message.process():
                cid = self._extract_correlation_id(message)
                bound_logger = logger.bind(
                    correlation_id=cid,
                    routing_key=message.routing_key,
                    queue=queue_name,
                    service=self._service_name,
                )
                try:
                    body = json.loads(message.body.decode())
                    bound_logger.info("rabbitmq_received")
                    # Inject correlation_id into payload so handlers can access it
                    body.setdefault("_correlation_id", cid)
                    await handler(body)
                except Exception:
                    bound_logger.exception("rabbitmq_handler_error")

        task = asyncio.create_task(self._consume_loop(queue, _process))
        logger.info(
            "rabbitmq_consumer_started",
            queue=queue_name,
            routing_keys=routing_keys,
            service=self._service_name,
        )
        return task

    async def _consume_loop(
        self,
        queue: aio_pika.abc.AbstractQueue,
        callback: Callable,
    ) -> None:
        """Internal consume loop."""
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                await callback(message)

    # ── Retry / DLX / DLQ support ───────────────────────

    async def consume_with_retry(
        self,
        queue_name: str,
        routing_keys: list[str],
        handler: Callable[[dict[str, Any]], Awaitable[None]],
        *,
        max_retries: int = 3,
        retry_ttl: int = 30_000,
    ) -> asyncio.Task:
        """
        Consume with automatic retry and dead-letter support.

        Topology created:
          main queue  ──(nack)──►  swifttrack.dlx  ──►  {queue}.retry (TTL)
          {queue}.retry  ──(TTL expires)──►  swifttrack.events  ──►  main queue
          max retries exceeded  ──►  swifttrack.dlq  ──►  {queue}.dlq

        Args:
            queue_name:   Name of the main consumer queue.
            routing_keys: Topic routing keys to bind.
            handler:      Async handler; raise to trigger retry.
            max_retries:  Max retry attempts before DLQ (default 3).
            retry_ttl:    Retry delay in milliseconds (default 30 000).
        """
        if not self._channel or not self._exchange:
            raise RuntimeError("RabbitMQ not connected — call connect() first")

        # ── 1. Declare DLX (receives nack'd messages) ────
        dlx = await self._channel.declare_exchange(
            "swifttrack.dlx",
            aio_pika.ExchangeType.TOPIC,
            durable=True,
        )

        # ── 2. Declare retry queue ───────────────────────
        #   - Messages sit here for `retry_ttl` ms
        #   - On expiry they route back to main exchange
        retry_queue_name = f"{queue_name}.retry"
        await self._channel.declare_queue(
            retry_queue_name,
            durable=True,
            arguments={
                "x-dead-letter-exchange": "swifttrack.events",
                "x-message-ttl": retry_ttl,
            },
        )
        # Bind retry queue to DLX with same routing keys
        retry_queue = await self._channel.get_queue(retry_queue_name)
        for key in routing_keys:
            await retry_queue.bind(dlx, routing_key=key)

        # ── 3. Declare DLQ exchange + queue ──────────────
        dlq_exchange = await self._channel.declare_exchange(
            "swifttrack.dlq",
            aio_pika.ExchangeType.FANOUT,
            durable=True,
        )
        dlq_queue_name = f"{queue_name}.dlq"
        dlq_queue = await self._channel.declare_queue(
            dlq_queue_name,
            durable=True,
        )
        await dlq_queue.bind(dlq_exchange)

        # ── 4. Declare main queue with DLX argument ──────
        main_queue = await self._channel.declare_queue(
            queue_name,
            durable=True,
            arguments={
                "x-dead-letter-exchange": "swifttrack.dlx",
            },
        )
        for key in routing_keys:
            await main_queue.bind(self._exchange, routing_key=key)

        logger.info(
            "rabbitmq_retry_topology_ready",
            main_queue=queue_name,
            retry_queue=retry_queue_name,
            dlq=dlq_queue_name,
            max_retries=max_retries,
            retry_ttl_ms=retry_ttl,
            service=self._service_name,
        )

        # ── 5. Consumer with manual ack/nack ─────────────
        async def _process_with_retry(
            message: aio_pika.abc.AbstractIncomingMessage,
        ) -> None:
            retry_count = self._get_retry_count(message, queue_name)
            cid = self._extract_correlation_id(message)
            bound_logger = logger.bind(
                correlation_id=cid,
                routing_key=message.routing_key,
                queue=queue_name,
                retry=retry_count,
                service=self._service_name,
            )

            try:
                body = json.loads(message.body.decode())
                bound_logger.info("rabbitmq_received")
                body.setdefault("_correlation_id", cid)
                await handler(body)
                await message.ack()

            except Exception:
                bound_logger.exception("rabbitmq_handler_error")

                if retry_count >= max_retries:
                    # Max retries exceeded → send to DLQ
                    logger.warning(
                        "rabbitmq_max_retries_exceeded",
                        routing_key=message.routing_key,
                        queue=queue_name,
                        retry=retry_count,
                        service=self._service_name,
                    )
                    await message.ack()  # ack to remove from main queue
                    await dlq_exchange.publish(
                        aio_pika.Message(
                            body=message.body,
                            content_type=message.content_type,
                            headers={
                                **(message.headers or {}),
                                "x-original-routing-key": message.routing_key,
                                "x-retry-count": retry_count,
                                "x-service": self._service_name,
                            },
                            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                        ),
                        routing_key="",
                    )
                else:
                    # nack with requeue=False → goes to DLX → retry queue
                    await message.nack(requeue=False)

        task = asyncio.create_task(self._consume_loop(main_queue, _process_with_retry))
        logger.info(
            "rabbitmq_consumer_started",
            queue=queue_name,
            routing_keys=routing_keys,
            mode="retry",
            service=self._service_name,
        )
        return task

    @staticmethod
    def _get_retry_count(
        message: aio_pika.abc.AbstractIncomingMessage,
        queue_name: str,
    ) -> int:
        """Extract retry count from the x-death header (set by RabbitMQ DLX)."""
        x_death = (message.headers or {}).get("x-death")
        if not x_death or not isinstance(x_death, list):
            return 0
        for entry in x_death:
            if isinstance(entry, dict) and entry.get("queue") == queue_name:
                return int(entry.get("count", 0))
        return 0

    @staticmethod
    def _extract_correlation_id(
        message: aio_pika.abc.AbstractIncomingMessage,
    ) -> str:
        """Extract correlation_id from message (header → property → generate)."""
        # 1. Check custom header
        cid = (message.headers or {}).get("correlation_id")
        if cid:
            return str(cid)
        # 2. Check AMQP property
        if message.correlation_id:
            return message.correlation_id
        # 3. Fallback: generate a new one
        return str(uuid.uuid4())
