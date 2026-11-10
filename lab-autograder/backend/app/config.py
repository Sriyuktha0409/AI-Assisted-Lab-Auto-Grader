from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SECRET = "dev-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"  # set to "production" in deployments
    database_url: str = "sqlite:///./autograder.db"
    secret_key: str = DEFAULT_SECRET
    access_token_minutes: int = 12 * 60
    cors_origins: str = "http://localhost:5173"

    # Registering as an instructor requires this invite code. Empty = disabled.
    instructor_invite_code: str = ""

    # Sandbox
    sandbox_mode: str = "local"  # "local" (dev/CI only) or "docker"
    sandbox_image: str = "gcc:13"
    # Directory for per-submission work dirs. In docker mode with a containerised API this
    # must be a path that exists identically on the host (bind-mounted at the same path).
    sandbox_workdir_root: str = ""
    compile_timeout_s: int = 15
    max_code_bytes: int = 20_000
    max_output_bytes: int = 64 * 1024
    submissions_per_minute: int = 10

    # LLM hints (optional). Without a key the rule-based hint generator is used.
    anthropic_api_key: str = ""
    hint_model: str = "claude-sonnet-5-5"
    hint_timeout_s: float = 20.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
