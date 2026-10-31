"""Application settings loaded from environment variables and ``.env``."""

from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore",
        hide_input_in_errors=True,
    )

    app_name: str = "Field Shift API"
    environment: str = "development"
    debug: bool = False
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5433/field_shift"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret_key: SecretStr = Field(default=SecretStr("change-this-development-secret"), alias="JWT_SECRET_KEY")
    admin_api_key: SecretStr | None = None
    agronomist_reviewer_keys: dict[str, SecretStr] = Field(default_factory=dict)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=60, ge=60, le=1440)
    otp_expire_seconds: int = Field(default=300, gt=0)
    otp_resend_cooldown_seconds: int = Field(default=60, gt=0)
    otp_attempt_limit: int = Field(default=5, ge=1, le=20)
    otp_attempt_window_seconds: int = Field(default=300, gt=0)
    otp_send_limit_per_ip: int = Field(default=10, ge=1)
    otp_send_window_seconds: int = Field(default=3600, gt=0)
    otp_provider: str = "development"
    bhashini_user_id: str | None = None
    bhashini_api_key: SecretStr | None = None
    bhashini_pipeline_id: str | None = None
    bhashini_config_url: str = "https://meity-auth.ulcacontrib.org/ulca/apis/v0/model/getModelsPipeline"
    bhashini_asr_service_id: str | None = None
    bhashini_tts_service_id: str | None = None
    bhashini_translation_service_id: str | None = None
    sms_gateway_url: str | None = None
    sms_gateway_api_key: SecretStr | None = None
    sms_sender_id: str | None = None
    whatsapp_gateway_url: str | None = None
    whatsapp_gateway_api_key: SecretStr | None = None
    whatsapp_sender_id: str | None = None
    nasa_appeears_api_url: str = "https://appeears.earthdatacloud.nasa.gov/api/"
    nasa_earthdata_username: str | None = None
    nasa_earthdata_password: SecretStr | None = None
    nasa_smap_product: str = "SPL3SMP_E.006"
    nasa_smap_max_range_days: int = Field(default=90, ge=1, le=365)
    nasa_smap_poll_interval_seconds: int = Field(default=5, ge=1, le=60)
    nasa_smap_max_wait_seconds: int = Field(default=900, ge=10, le=1800)
    sentinel2_process_url: str | None = None
    sentinel2_token_url: str = "https://services.sentinel-hub.com/auth/realms/main/protocol/openid-connect/token"
    sentinel2_client_id: str | None = None
    sentinel2_client_secret: SecretStr | None = None
    agristack_base_url: str | None = None
    agristack_token_url: str | None = None
    agristack_client_id: str | None = None
    agristack_client_secret: SecretStr | None = None
    soil_card_ocr_url: str | None = None
    soil_card_ocr_api_key: SecretStr | None = None
    object_storage_endpoint_url: str | None = None
    object_storage_region: str = "us-east-1"
    object_storage_bucket: str | None = None
    object_storage_access_key_id: str | None = None
    object_storage_secret_access_key: SecretStr | None = None
    object_storage_secure: bool = True
    clamav_host: str | None = None
    clamav_port: int = Field(default=3310, ge=1, le=65535)
    soil_card_max_upload_bytes: int = Field(default=10_485_760, ge=1024, le=52_428_800)
    soil_card_retention_days: int = Field(default=30, ge=1, le=3650)
    soil_card_ocr_confidence_threshold: float = Field(default=0.80, ge=0, le=1)
    agmarknet_api_url: str | None = None
    agmarknet_resource_id: str | None = None
    agmarknet_api_key: SecretStr | None = None
    agmarknet_default_price_unit: str | None = None
    agmarknet_page_size: int = Field(default=1000, ge=1, le=10000)
    agmarknet_max_pages: int = Field(default=20, ge=1, le=100)
    weather_provider: str = "open_meteo"
    open_meteo_api_url: str = "https://api.open-meteo.com/v1/forecast"
    weather_cache_seconds: int = Field(default=1800, ge=60, le=86400)
    weather_freshness_seconds: int = Field(default=3600, ge=60, le=172800)
    alert_max_attempts: int = Field(default=5, ge=1, le=20)
    alert_retry_base_seconds: int = Field(default=300, ge=30, le=86400)
    sowing_window_alert_threshold_days: int = Field(default=3, ge=0, le=30)
    reminder_sms_enabled: bool = True
    reminder_whatsapp_enabled: bool = True
    db_pool_size: int = Field(default=5, ge=1)
    db_max_overflow: int = Field(default=10, ge=0)

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        try:
            url = make_url(value)
        except Exception as exc:
            raise ValueError("DATABASE_URL must be a valid SQLAlchemy URL") from exc
        if url.get_backend_name() != "postgresql" or url.get_driver_name() != "asyncpg":
            raise ValueError("DATABASE_URL must use the postgresql+asyncpg driver")
        if not url.host or not url.database:
            raise ValueError("DATABASE_URL must include a host and database name")
        return value

    def validate_runtime_configuration(self) -> list[str]:
        """Validate security-sensitive settings and return missing optional providers."""
        if self.otp_provider not in {"development", "sms"}:
            raise ValueError("OTP_PROVIDER must be development or sms")
        if self.weather_provider != "open_meteo":
            raise ValueError("WEATHER_PROVIDER must be open_meteo")
        if self.environment.strip().lower() in {"production", "prod"}:
            secret = self.jwt_secret_key.get_secret_value()
            if len(secret) < 32 or secret.lower() in {
                "change-this-development-secret", "replace-with-a-long-random-secret", "secret"
            }:
                raise ValueError("JWT_SECRET_KEY must be at least 32 characters in production")
            if self.otp_provider != "sms":
                raise ValueError("OTP_PROVIDER must be sms in production")
            if not self.sms_gateway_url or not self.sms_gateway_api_key:
                raise ValueError("SMS gateway URL and API key are required for production OTP delivery")
            if not all((self.object_storage_bucket, self.object_storage_access_key_id,
                        self.object_storage_secret_access_key, self.clamav_host)):
                raise ValueError("Private object storage and ClamAV are required for production soil-card uploads")
        if self.otp_provider == "development" and self.environment.strip().lower() not in {
            "development", "dev", "test", "testing"
        }:
            raise ValueError("The development OTP provider is only available in development or test")

        provider_settings = {
            "Bhashini": (self.bhashini_user_id, self.bhashini_api_key, self.bhashini_pipeline_id),
            "SMS gateway": (self.sms_gateway_url, self.sms_gateway_api_key),
            "WhatsApp gateway": (self.whatsapp_gateway_url, self.whatsapp_gateway_api_key),
            "NASA AppEEARS SMAP": (self.nasa_earthdata_username, self.nasa_earthdata_password),
            "Sentinel-2": (self.sentinel2_process_url, self.sentinel2_client_id, self.sentinel2_client_secret),
            "AgriStack": (self.agristack_base_url, self.agristack_client_id, self.agristack_client_secret),
            "Soil card OCR": (self.soil_card_ocr_url, self.soil_card_ocr_api_key),
            "Private soil-card object storage": (self.object_storage_bucket, self.object_storage_access_key_id,
                                                  self.object_storage_secret_access_key),
            "ClamAV scanner": (self.clamav_host,),
            "Agmarknet": (self.agmarknet_api_url, self.agmarknet_resource_id),
        }
        return [name for name, values in provider_settings.items() if not all(values)]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
