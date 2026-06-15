"""应用配置：通过环境变量 / .env 注入，集中管理。"""
from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 基础
    APP_NAME: str = "agent-demo"
    ENV: Literal["dev", "test", "prod"] = "dev"
    DEBUG: bool = True
    API_PREFIX: str = "/api/v1"

    # 服务
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # MySQL
    MYSQL_HOST: str = "127.0.0.1"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = "root"
    MYSQL_DB: str = "agent_demo"
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_RECYCLE: int = 3600

    # Redis
    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str | None = None

    # 日志
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "logs"
    LOG_RETENTION: str = "14 days"
    LOG_ROTATION: str = "00:00"

    # 安全 / JWT
    SECRET_KEY: str = "CHANGE_ME_IN_PROD_please_use_a_long_random_string"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # 真实 LLM（Gemini via google-genai）
    GOOGLE_API_KEYS: str = ""  # CSV 多 key
    GEMINI_BACKEND: Literal["vertex_ai", "google_ai"] = "vertex_ai"
    GOOGLE_CLOUD_LOCATION: str = "us-central1"
    LLM_MODEL: str = "gemini-3.1-pro-preview"
    LLM_TIMEOUT_SEC: float = 120.0
    LLM_THINKING_LEVEL: Literal["low", "high"] = "low"  # demo 用 low 更快；要质量改 high

    # 真实生图（portrait_gen 网关）
    PORTRAIT_GEN_BASE_URL: str = ""
    PORTRAIT_GEN_PROVIDER: str = "openai"
    PORTRAIT_GEN_MODEL_ID: str = "openai:t2i_image_2"
    PORTRAIT_GEN_MODEL: str = "text2image_gpt_image_2"
    IMAGE_WIDTH: int = 512
    IMAGE_HEIGHT: int = 768
    IMAGE_GEN_TIMEOUT_SEC: float = 300.0
    IMAGE_GEN_CONCURRENCY: int = 4  # 进程内并发上限（替代跨 Pod Redis 信号量）

    @property
    def google_api_keys_list(self) -> list[str]:
        return [k.strip() for k in self.GOOGLE_API_KEYS.split(",") if k.strip()]

    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        return (
            f"mysql+aiomysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}?charset=utf8mb4"
        )

    @computed_field
    @property
    def REDIS_URL(self) -> str:
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
