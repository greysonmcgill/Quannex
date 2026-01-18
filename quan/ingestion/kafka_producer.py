"""Kafka producer for streaming account data"""

import json
import asyncio
from typing import Any, Dict, Optional
from datetime import datetime
import logging

from quan.config import settings

logger = logging.getLogger(__name__)


class KafkaProducerClient:
    """Async Kafka producer for account streaming"""

    def __init__(self):
        self._producer = None
        self._connected = False

    async def connect(self) -> None:
        """Initialize Kafka producer connection"""
        try:
            from aiokafka import AIOKafkaProducer

            self._producer = AIOKafkaProducer(
                bootstrap_servers=settings.kafka_bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
                acks="all",
                retries=3,
                retry_backoff_ms=100,
            )
            await self._producer.start()
            self._connected = True
            logger.info("Kafka producer connected")
        except ImportError:
            logger.warning("aiokafka not installed, using mock producer")
            self._connected = False
        except Exception as e:
            logger.error(f"Failed to connect Kafka producer: {e}")
            self._connected = False

    async def disconnect(self) -> None:
        """Close Kafka producer connection"""
        if self._producer:
            await self._producer.stop()
            self._connected = False
            logger.info("Kafka producer disconnected")

    async def send(
        self,
        topic: str,
        value: Dict[str, Any],
        key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> bool:
        """Send message to Kafka topic"""

        # Add metadata
        value["_ingested_at"] = datetime.utcnow().isoformat()
        value["_topic"] = topic

        if not self._connected:
            # Fallback: log the message
            logger.info(f"Kafka message (not sent): {topic} - {key}")
            return False

        try:
            kafka_headers = None
            if headers:
                kafka_headers = [(k, v.encode("utf-8")) for k, v in headers.items()]

            await self._producer.send_and_wait(
                topic=topic,
                value=value,
                key=key,
                headers=kafka_headers,
            )
            logger.debug(f"Sent to {topic}: {key}")
            return True

        except Exception as e:
            logger.error(f"Failed to send to Kafka: {e}")
            return False

    async def send_batch(
        self,
        topic: str,
        messages: list[Dict[str, Any]],
        key_field: str = "account_id",
    ) -> int:
        """Send batch of messages to Kafka topic"""

        sent_count = 0
        for msg in messages:
            key = msg.get(key_field)
            success = await self.send(topic, msg, key)
            if success:
                sent_count += 1

        return sent_count


# Kafka Topics Configuration
KAFKA_TOPICS = {
    "accounts_new": "quan.accounts.new",
    "accounts_enriched": "quan.accounts.enriched",
    "accounts_scored": "quan.accounts.scored",
    "contacts": "quan.contacts",
    "payments": "quan.payments",
    "events": "quan.events",
    "compliance": "quan.compliance",
    "dlq": "quan.dead-letter",
}


class KafkaConsumerClient:
    """Async Kafka consumer for processing streams"""

    def __init__(self, topics: list[str], group_id: str):
        self._topics = topics
        self._group_id = group_id
        self._consumer = None
        self._running = False

    async def start(self, handler) -> None:
        """Start consuming messages"""
        try:
            from aiokafka import AIOKafkaConsumer

            self._consumer = AIOKafkaConsumer(
                *self._topics,
                bootstrap_servers=settings.kafka_bootstrap_servers,
                group_id=self._group_id,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                auto_offset_reset="earliest",
                enable_auto_commit=True,
            )
            await self._consumer.start()
            self._running = True

            logger.info(f"Kafka consumer started for topics: {self._topics}")

            async for msg in self._consumer:
                if not self._running:
                    break
                try:
                    await handler(msg.topic, msg.key, msg.value)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    # Send to dead letter queue
                    await self._send_to_dlq(msg)

        except ImportError:
            logger.warning("aiokafka not installed")
        except Exception as e:
            logger.error(f"Kafka consumer error: {e}")
        finally:
            await self.stop()

    async def stop(self) -> None:
        """Stop consuming messages"""
        self._running = False
        if self._consumer:
            await self._consumer.stop()
            logger.info("Kafka consumer stopped")

    async def _send_to_dlq(self, msg) -> None:
        """Send failed message to dead letter queue"""
        producer = KafkaProducerClient()
        await producer.connect()
        await producer.send(
            topic=KAFKA_TOPICS["dlq"],
            value={
                "original_topic": msg.topic,
                "original_key": msg.key.decode("utf-8") if msg.key else None,
                "original_value": msg.value,
                "error_time": datetime.utcnow().isoformat(),
            },
        )
        await producer.disconnect()
