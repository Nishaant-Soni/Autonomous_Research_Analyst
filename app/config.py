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

    # Phase 6: auth (plan 6.2). jwt_secret defaults to "" so existing tests that don't
    # set JWT_SECRET still import cleanly; auth endpoints raise clearly at call time if empty.
    jwt_secret: str = ""
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    # False for local http://localhost dev — Secure cookies are dropped by browsers on non-HTTPS.
    cookie_secure: bool = False

    # Rate limiting (slowapi). On by default; disabled in the test suite so repeated
    # TestClient calls don't trip the limiter. Per-endpoint limits live in app/api/ratelimit.py.
    rate_limit_enabled: bool = True


settings = Settings()
