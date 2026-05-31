from pydantic_settings import BaseSettings, SettingsConfigDict

from shared.yaml_config import load_yaml


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bot_token: str = ""
    database_url: str = "postgresql+asyncpg://app:app@localhost:5432/cryptobot"
    redis_url: str = "redis://localhost:6379/0"
    crypto_pay_token: str = ""
    admin_telegram_ids: str = ""


settings = Settings()


def admin_ids() -> set[int]:
    raw = settings.admin_telegram_ids
    if not raw:
        cfg = load_yaml("app.yaml")
        raw = ",".join(str(x) for x in cfg.get("admin_telegram_ids", []))
    return {int(x.strip()) for x in raw.split(",") if x.strip().isdigit()}


def is_admin(telegram_id: int) -> bool:
    return telegram_id in admin_ids()
