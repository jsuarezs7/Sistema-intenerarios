from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    jwt_secret: str = Field(min_length=32)
    demo_username: str = Field(min_length=1, max_length=128)
    demo_password: str = Field(min_length=12)
    airport_service_url: str = "http://localhost:8001"
    itinerary_service_url: str = "http://localhost:8002"
    report_service_url: str = "http://localhost:8003"
    redis_url: str = "redis://localhost:6379/0"
    rate_limit: int = Field(default=120, ge=1)
    login_rate_limit: int = Field(default=10, ge=1)
    frontend_dir: str = "../../frontend"
