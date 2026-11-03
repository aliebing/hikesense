"""Configuration from environment / .env."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import SecretStr, model_validator
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
    supabase_jwt_secret: str | None = None
    supabase_url: str | None = None  # JWKS: {supabase_url}/auth/v1/.well-known/jwks.json
    supabase_anon_key: str | None = None  # smoke run: sign-in at the local Supabase auth
    hikeall_smoke_password: SecretStr | None = None  # smoke user smoke@hikeall.local
    hikeall_admin_password_hash: SecretStr | None = None  # bcrypt hash, admin@hikeall.local
    overpass_url: str = "https://overpass-api.de/api/interpreter"
    dem_cache_dir: Path = Path("data/dem")
    openrouter_api_key: str | None = None
    hikeall_model: str = "openai/gpt-4o-mini"
    # None: the gateway keeps its fixed values (0.0 structured/tools, 0.3 answers); set (eval
    # comparison): used for every call
    hikeall_temperature: float | None = None
    max_tool_calls: int = 8
    max_cost_usd: float = 0.05
    chat_log_path: Path = Path("logs/chat.jsonl")
    chroma_dir: Path = Path("chroma")
    hikeall_user_agent: str | None = None  # own User-Agent for event pages (None: neutral default)
    # optional LangSmith tracing: on only with LANGSMITH_TRACING=true and an API key
    langsmith_tracing: str | None = None  # "true" turns it on (empty: off)
    langsmith_api_key: SecretStr | None = None
    langsmith_endpoint: str | None = None  # empty: the EU endpoint
    langsmith_project: str | None = None  # empty: "hikesense"

    @model_validator(mode="after")
    def _resolve_data_paths(self) -> Settings:
        """Relative chat_log_path / chroma_dir are relative to the data root, not the cwd."""
        root = data_root()
        if not self.chat_log_path.is_absolute():
            self.chat_log_path = root / self.chat_log_path
        if not self.chroma_dir.is_absolute():
            self.chroma_dir = root / self.chroma_dir
        return self


LANGSMITH_EU_ENDPOINT = "https://eu.api.smith.langchain.com"
LANGSMITH_DEFAULT_PROJECT = "hikesense"


def export_langsmith_env(settings: Settings) -> bool:
    """LangChain/LangSmith read only os.environ, while Settings also reads .env: export the
    LANGSMITH_* values at startup. On only when tracing is true and a key is set; otherwise
    tracing is forced off (also a stray LANGCHAIN_TRACING_V2). Returns whether it is on."""
    key = settings.langsmith_api_key.get_secret_value() if settings.langsmith_api_key else ""
    on = (settings.langsmith_tracing or "").strip().lower() == "true" and bool(key)
    flag = "true" if on else "false"
    os.environ["LANGSMITH_TRACING"] = flag
    os.environ["LANGSMITH_TRACING_V2"] = flag  # read before LANGSMITH_TRACING / LANGCHAIN_*
    if on:
        os.environ["LANGSMITH_API_KEY"] = key
        os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint or LANGSMITH_EU_ENDPOINT
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project or LANGSMITH_DEFAULT_PROJECT
    from langsmith import utils as ls_utils

    ls_utils.get_env_var.cache_clear()  # langsmith caches env lookups
    return on
