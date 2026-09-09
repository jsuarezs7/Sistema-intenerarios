from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    jwt_secret: str = Field(min_length=32)
    database_url: str
    rabbitmq_url: str = ""
    airport_service_url: str = "http://localhost:8001"
    outbox_poll_seconds: float = Field(default=2, gt=0)
