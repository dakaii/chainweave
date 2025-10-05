"""Configuration management for ChainWeave application."""

from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class HeliusConfig(BaseSettings):
    """Helius API configuration."""

    api_key: str = Field(default="", description="Helius API key")
    webhook_url: str = Field(default="http://localhost:8000/webhook/helius")
    rpc_url: str = Field(default="https://mainnet.helius.xyz")

    model_config = SettingsConfigDict(env_prefix="HELIUS_")


class GCPConfig(BaseSettings):
    """Google Cloud Platform configuration."""

    project_id: str = Field(default="test-project", description="GCP Project ID")
    region: str = Field(default="us-central1")
    zone: str = Field(default="us-central1-a")
    credentials_path: Optional[str] = Field(default=None, alias="GOOGLE_APPLICATION_CREDENTIALS")

    model_config = SettingsConfigDict(env_prefix="GCP_")


class BigQueryConfig(BaseSettings):
    """BigQuery configuration."""

    dataset: str = Field(default="chainweave_dev")
    location: str = Field(default="us-central1")
    table_prefix: str = Field(default="nft_")

    model_config = SettingsConfigDict(env_prefix="BIGQUERY_")


class PubSubConfig(BaseSettings):
    """Pub/Sub configuration."""

    topic: str = Field(default="nft-events-dev")
    subscription: str = Field(default="nft-processor-dev")
    dead_letter_topic: str = Field(default="nft-events-dlq")

    model_config = SettingsConfigDict(env_prefix="PUBSUB_")


class CloudRunConfig(BaseSettings):
    """Cloud Run services configuration."""

    webhook_service_url: str = Field(default="https://chainweave-webhook-service.run.app")
    dashboard_service_url: str = Field(default="https://chainweave-dashboard-service.run.app")

    model_config = SettingsConfigDict(env_prefix="")


class StreamlitConfig(BaseSettings):
    """Streamlit dashboard configuration."""

    server_port: int = Field(default=8501)
    server_address: str = Field(default="0.0.0.0")
    theme_primary_color: str = Field(default="#1f77b4")
    theme_background_color: str = Field(default="#ffffff")

    model_config = SettingsConfigDict(env_prefix="STREAMLIT_")


class WhaleConfig(BaseSettings):
    """Whale detection configuration."""

    volume_threshold_sol: float = Field(default=100.0)
    nft_count_threshold: int = Field(default=50)
    alert_cooldown_hours: int = Field(default=6)

    model_config = SettingsConfigDict(env_prefix="WHALE_")


class PerformanceConfig(BaseSettings):
    """Performance and scaling configuration."""

    max_concurrent_requests: int = Field(default=100)
    request_timeout_seconds: int = Field(default=30)
    bigquery_job_timeout_seconds: int = Field(default=300)

    model_config = SettingsConfigDict(env_prefix="")


class DataRetentionConfig(BaseSettings):
    """Data retention policies."""

    data_retention_days: int = Field(default=90)
    aggregate_retention_days: int = Field(default=365)

    model_config = SettingsConfigDict(env_prefix="")


class SecurityConfig(BaseSettings):
    """Security configuration."""

    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8501"]
    )
    api_rate_limit_per_minute: int = Field(default=60)

    model_config = SettingsConfigDict(env_prefix="")

    def __init__(self, **kwargs):
        if "cors_origins" in kwargs and isinstance(kwargs["cors_origins"], str):
            kwargs["cors_origins"] = kwargs["cors_origins"].split(",")
        super().__init__(**kwargs)


class AppConfig(BaseSettings):
    """Main application configuration."""

    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")
    debug: bool = Field(default=True)

    # Sub-configurations
    helius: HeliusConfig = Field(default_factory=HeliusConfig)
    gcp: GCPConfig = Field(default_factory=GCPConfig)
    bigquery: BigQueryConfig = Field(default_factory=BigQueryConfig)
    pubsub: PubSubConfig = Field(default_factory=PubSubConfig)
    cloud_run: CloudRunConfig = Field(default_factory=CloudRunConfig)
    streamlit: StreamlitConfig = Field(default_factory=StreamlitConfig)
    whale: WhaleConfig = Field(default_factory=WhaleConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)
    data_retention: DataRetentionConfig = Field(default_factory=DataRetentionConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Initialize sub-configurations with environment variables
        self.helius = HeliusConfig()
        self.gcp = GCPConfig()
        self.bigquery = BigQueryConfig()
        self.pubsub = PubSubConfig()
        self.cloud_run = CloudRunConfig()
        self.streamlit = StreamlitConfig()
        self.whale = WhaleConfig()
        self.performance = PerformanceConfig()
        self.data_retention = DataRetentionConfig()
        self.security = SecurityConfig()


# Global configuration instance
config = AppConfig()
