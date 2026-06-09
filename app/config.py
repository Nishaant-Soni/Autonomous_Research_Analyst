from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, read from environment variables / `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/research"
    openai_api_key: str = ""
    tavily_api_key: str = ""
    langsmith_api_key: str = ""
    langsmith_project: str = "autonomous-research-analyst"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    max_iterations: int = 2
    llm_timeout_seconds: float = 120.0
    llm_max_retries: int = 2


settings = Settings()
