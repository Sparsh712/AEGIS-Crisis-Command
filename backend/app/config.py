"""Application settings for the AEGIS backend.

Level 0 deliberately keeps configuration small and environment-based.  The
settings object is cached so the FastAPI app and the LLM wrapper use the same
values for the lifetime of a process.
"""

from functools import lru_cache
import os

from dotenv import load_dotenv
from pydantic import BaseModel, Field


load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Settings(BaseModel):
    """Runtime configuration loaded from environment variables."""

    llm_provider: str = Field(default_factory=lambda: os.getenv("LLM_PROVIDER", "fake"))
    llm_model: str = Field(default_factory=lambda: os.getenv("LLM_MODEL", "aegis-fake"))
    llm_api_key: str | None = Field(default_factory=lambda: os.getenv("LLM_API_KEY"))
    frontend_origin: str = Field(
        default_factory=lambda: os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
    )
    fixture_only: bool = Field(default_factory=lambda: _env_bool("FIXTURE_ONLY"))
    fake_llm: bool = Field(default_factory=lambda: _env_bool("FAKE_LLM", default=True))
    trace_interval_seconds: float = Field(
        default_factory=lambda: float(os.getenv("AEGIS_TRACE_INTERVAL_SECONDS", "2")),
        gt=0,
    )

    @property
    def cors_origins(self) -> list[str]:
        """Return comma-separated frontend origins in FastAPI's expected form."""

        return [origin.strip() for origin in self.frontend_origin.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and cache process settings.

    Tests can call ``get_settings.cache_clear()`` after changing environment
    variables, which mirrors a fresh process without adding test-only code.
    """

    return Settings()


settings = get_settings()
