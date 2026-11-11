from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    public_app_url: str = "http://localhost:3000"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    llm_provider: str = "mock"
    llm_fallback_provider: str | None = None
    llm_provider_mode: str = "fixed"

    qwen_api_key: str | None = None
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen-plus"

    doubao_api_key: str | None = None
    doubao_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    doubao_model: str | None = None

    llm_request_timeout_seconds: int = 60
    llm_max_retries: int = 2


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
