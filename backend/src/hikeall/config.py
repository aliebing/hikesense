"""Configuration from environment / .env."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supabase_db_url: str
    overpass_url: str = "https://overpass-api.de/api/interpreter"
    dem_cache_dir: Path = Path("data/dem")
