"""Central configuration for the Korean Market Analyzer.

Loaded once from environment variables / a local ``.env`` file via
pydantic-settings. Import the module-level singleton::

    from config.settings import settings
    print(settings.db_url)

Factor weights live here so the scoring model has a single source of truth;
they are tuned in Phase 5 (backtest) but start at the values from CLAUDE.md.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = two levels up from this file (config/settings.py -> project/).
PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]
DATA_DIR: Path = PROJECT_ROOT / "data"
RAW_DIR: Path = DATA_DIR / "raw"
PROCESSED_DIR: Path = DATA_DIR / "processed"
REPORTS_DIR: Path = PROJECT_ROOT / "reports"


class FactorWeights(BaseModel):
    """Weights for the four factor groups blended into the composite score.

    Must sum to 1.0 (validated). Defaults are the CLAUDE.md starting point;
    re-tune via the Phase 5 backtest, not by guessing.
    """

    fundamental: float = 0.35
    supply_demand: float = 0.25
    technical: float = 0.25
    sentiment: float = 0.15

    @model_validator(mode="after")
    def _must_sum_to_one(self) -> "FactorWeights":
        total = self.fundamental + self.supply_demand + self.technical + self.sentiment
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Factor weights must sum to 1.0, got {total:.6f}")
        return self

    def as_dict(self) -> dict[str, float]:
        return {
            "fundamental": self.fundamental,
            "supply_demand": self.supply_demand,
            "technical": self.technical,
            "sentiment": self.sentiment,
        }


class Settings(BaseSettings):
    """Runtime settings, sourced from env / .env (prefix ``KMA_`` where noted)."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- secrets (no KMA_ prefix; these are the conventional names) ---
    dart_api_key: SecretStr | None = Field(default=None, alias="DART_API_KEY")
    anthropic_api_key: SecretStr | None = Field(default=None, alias="ANTHROPIC_API_KEY")

    # --- storage ---
    db_url: str = Field(default="sqlite:///data/market.db", alias="KMA_DB_URL")

    # --- llm ---
    anthropic_model: str = Field(default="claude-opus-4-8", alias="KMA_ANTHROPIC_MODEL")

    # --- ops ---
    log_level: str = Field(default="INFO", alias="KMA_LOG_LEVEL")
    timezone: str = Field(default="Asia/Seoul", alias="KMA_TIMEZONE")

    # --- scoring ---
    factor_weights: FactorWeights = Field(default_factory=FactorWeights)

    @field_validator("log_level")
    @classmethod
    def _normalize_log_level(cls, v: str) -> str:
        v = v.upper()
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v not in allowed:
            raise ValueError(f"log_level must be one of {sorted(allowed)}, got {v!r}")
        return v

    @property
    def resolved_db_url(self) -> str:
        """Make a relative SQLite path absolute so it works regardless of CWD."""
        prefix = "sqlite:///"
        if self.db_url.startswith(prefix):
            raw = self.db_url[len(prefix) :]
            p = Path(raw)
            if not p.is_absolute():
                p = (PROJECT_ROOT / p).resolve()
            return f"{prefix}{p.as_posix()}"
        return self.db_url

    @property
    def is_sqlite(self) -> bool:
        return self.resolved_db_url.startswith("sqlite")

    def ensure_dirs(self) -> None:
        """Create the data/report directories if missing (idempotent)."""
        for d in (RAW_DIR, PROCESSED_DIR, REPORTS_DIR):
            d.mkdir(parents=True, exist_ok=True)
        if self.is_sqlite:
            db_path = Path(self.resolved_db_url[len("sqlite:///") :])
            db_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor (read env once)."""
    return Settings()


# Module-level singleton for convenient imports.
settings: Settings = get_settings()
