from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    jwt_secret: str = Field(min_length=32)
    redis_url: str = "redis://localhost:6379/0"
    airport_api_url: str = "https://api-colombia.com/api/v1/Airport"
    cache_ttl: int = Field(default=3600, gt=0)
    stale_cache_ttl: int = Field(default=86400, gt=0)
    http_timeout: float = Field(default=8, gt=0)
