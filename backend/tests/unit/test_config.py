from config.settings import Settings


def test_settings_read_environment_variables(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@db:5432/farm")
    monkeypatch.setenv("REDIS_URL", "redis://cache:6379/2")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret")
    monkeypatch.setenv("BHASHINI_USER_ID", "user-123")
    monkeypatch.setenv("BHASHINI_API_KEY", "api-secret")

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql+asyncpg://user:pass@db:5432/farm"
    assert settings.redis_url == "redis://cache:6379/2"
    assert settings.jwt_secret_key.get_secret_value() == "test-secret"
    assert settings.bhashini_user_id == "user-123"
    assert settings.bhashini_api_key.get_secret_value() == "api-secret"


def test_settings_use_fallbacks_when_environment_is_missing(monkeypatch):
    for name in (
        "DATABASE_URL",
        "REDIS_URL",
        "JWT_SECRET_KEY",
        "BHASHINI_USER_ID",
        "BHASHINI_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = Settings(_env_file=None)

    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.jwt_secret_key.get_secret_value()
    assert settings.bhashini_user_id is None
    assert settings.bhashini_api_key is None
