"""Configuration from environment / .env."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ROOT_ENV = _REPO_ROOT / ".env"


def data_root() -> Path:
    """Where relative data paths live: HIKEALL_DATA_DIR if set, else <repo root>/data when that
    directory exists, else ./data (Docker: WORKDIR /app, volume ./data -> /app/data)."""
    env = os.environ.get("HIKEALL_DATA_DIR")
    if env:
        return Path(env)
    repo_data = _REPO_ROOT / "data"
    return repo_data if repo_data.is_dir() else Path("data")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ROOT_ENV, extra="ignore")

    supabase_db_url: str
    overpass_url: str = "https://overpass-api.de/api/interpreter"
    dem_cache_dir: Path = Path("data/dem")
    openrouter_api_key: str | None = None
    hikeall_model: str = "openai/gpt-4o-mini"
    max_tool_calls: int = 8
    max_cost_usd: float = 0.05
    chat_log_path: Path = Path("logs/chat.jsonl")
    chroma_dir: Path = Path("chroma")

    @model_validator(mode="after")
    def _resolve_data_paths(self) -> Settings:
        """Relative chat_log_path / chroma_dir are relative to the data root, not the cwd."""
        root = data_root()
        if not self.chat_log_path.is_absolute():
            self.chat_log_path = root / self.chat_log_path
        if not self.chroma_dir.is_absolute():
            self.chroma_dir = root / self.chroma_dir
        return self
