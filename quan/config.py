"""Central configuration management for QUAN platform"""

from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Application
    app_name: str = "QUAN Recovery"
    environment: str = "development"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://quan:quan@localhost:5432/quan"
    redis_url: str = "redis://localhost:6379"

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_consumer_group: str = "quan-consumers"

    # External Services
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    twilio_phone_number: Optional[str] = None

    sendgrid_api_key: Optional[str] = None
    sendgrid_from_email: str = "collections@quanrecovery.com"

    stripe_secret_key: Optional[str] = None
    stripe_webhook_secret: Optional[str] = None

    # Google Cloud
    gcp_project_id: Optional[str] = None
    gcs_bucket: str = "quan-data"
    bigquery_dataset: str = "quan_analytics"

    # ML Models
    model_registry_path: str = "/models"
    quantum_engine_url: str = "localhost:50051"

    # Compliance
    max_weekly_contact_attempts: int = 7
    contact_hours_start: int = 8
    contact_hours_end: int = 21

    # Security
    secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Monitoring
    prometheus_port: int = 9090
    jaeger_endpoint: Optional[str] = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


settings = get_settings()
