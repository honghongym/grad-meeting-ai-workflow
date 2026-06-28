import os
from functools import lru_cache

from pydantic import Field

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:  # pragma: no cover - fallback for minimal test environments
    from pydantic import BaseModel as BaseSettings

    SettingsConfigDict = dict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./meeting_ai.db"
    openai_api_key: str = ""
    openai_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_provider: str = "bailian"
    extractor_model: str = "deepseek-v4-flash"
    planner_model: str = "qwen3.7-plus"
    embedding_model: str = "text-embedding-v4"
    embedding_dimension: int = 1536
    vector_backend: str = "pgvector"
    max_append_depth: int = 1
    extractor_concurrency: int = 3
    use_fake_llm: bool = Field(default=False)
    api_token: str = ""
    cors_allow_origins: str = "http://localhost:8000,chrome-extension://*"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    def __init__(self, **data):
        if BaseSettings.__name__ == "BaseModel":
            data = {
                "database_url": os.getenv("DATABASE_URL", data.get("database_url", "sqlite:///./meeting_ai.db")),
                "openai_api_key": os.getenv("OPENAI_API_KEY", data.get("openai_api_key", "")),
                "openai_base_url": os.getenv(
                    "OPENAI_BASE_URL",
                    data.get("openai_base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
                ),
                "llm_provider": os.getenv("LLM_PROVIDER", data.get("llm_provider", "bailian")),
                "extractor_model": os.getenv("EXTRACTOR_MODEL", data.get("extractor_model", "deepseek-v4-flash")),
                "planner_model": os.getenv("PLANNER_MODEL", data.get("planner_model", "qwen3.7-plus")),
                "embedding_model": os.getenv(
                    "EMBEDDING_MODEL", data.get("embedding_model", "text-embedding-v4")
                ),
                "embedding_dimension": int(
                    os.getenv("EMBEDDING_DIMENSION", data.get("embedding_dimension", 1536))
                ),
                "vector_backend": os.getenv("VECTOR_BACKEND", data.get("vector_backend", "pgvector")),
                "max_append_depth": int(os.getenv("MAX_APPEND_DEPTH", data.get("max_append_depth", 1))),
                "extractor_concurrency": int(
                    os.getenv("EXTRACTOR_CONCURRENCY", data.get("extractor_concurrency", 3))
                ),
                "use_fake_llm": os.getenv("USE_FAKE_LLM", str(data.get("use_fake_llm", "false"))).lower()
                in {"1", "true", "yes"},
                "api_token": os.getenv("API_TOKEN", data.get("api_token", "")),
                "cors_allow_origins": os.getenv(
                    "CORS_ALLOW_ORIGINS",
                    data.get("cors_allow_origins", "http://localhost:8000,chrome-extension://*"),
                ),
            }
        super().__init__(**data)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
