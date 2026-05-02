from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    mongo_uri: str = Field(validation_alias=AliasChoices("MONGO_URI", "MONGO_URL"))
    db_name: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
