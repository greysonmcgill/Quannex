"""Data ingestion layer for QUAN platform"""

from .api_gateway import QuanIngestion, router as ingestion_router
from .validators import BNPLValidator, BankValidator, SubscriptionValidator
from .kafka_producer import KafkaProducerClient

__all__ = [
    "QuanIngestion",
    "ingestion_router",
    "BNPLValidator",
    "BankValidator",
    "SubscriptionValidator",
    "KafkaProducerClient",
]
