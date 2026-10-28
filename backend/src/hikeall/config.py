"""Configuration from environment / .env."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ROOT_ENV, extra="ignore")

    supabase_db_url: str
    overpass_url: str = "https://overpass-api.de/api/interpreter"
    dem_cache_dir: Path = Path("data/dem")
