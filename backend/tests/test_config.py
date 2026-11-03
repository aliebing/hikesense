from pathlib import Path

import pytest

from hikeall import config
from hikeall.config import Settings


def make(**kw) -> Settings:
    return Settings(supabase_db_url="x", _env_file=None, **kw)


@pytest.fixture(autouse=True)
def _no_data_dir_env(monkeypatch):
    monkeypatch.delenv("HIKEALL_DATA_DIR", raising=False)


def test_env_data_dir_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("HIKEALL_DATA_DIR", str(tmp_path))
    s = make()
    assert s.chroma_dir == tmp_path / "chroma"
    assert s.chat_log_path == tmp_path / "logs" / "chat.jsonl"


def test_repo_data_dir_used_when_it_exists(monkeypatch, tmp_path):
    (tmp_path / "data").mkdir()
    monkeypatch.setattr(config, "_REPO_ROOT", tmp_path)
    monkeypatch.chdir(tmp_path / "data")  # cwd must not matter
    s = make()
    assert s.chroma_dir == tmp_path / "data" / "chroma"
    assert s.chat_log_path == tmp_path / "data" / "logs" / "chat.jsonl"


def test_falls_back_to_cwd_data_without_repo_data(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "_REPO_ROOT", tmp_path / "nowhere")
    monkeypatch.chdir(tmp_path)
    s = make()
    assert s.chroma_dir == Path("data/chroma")
    assert s.chat_log_path == Path("data/logs/chat.jsonl")


def test_absolute_paths_are_kept(monkeypatch, tmp_path):
    monkeypatch.setenv("HIKEALL_DATA_DIR", str(tmp_path / "d"))
    s = make(chroma_dir=tmp_path / "c", chat_log_path=tmp_path / "l.jsonl")
    assert s.chroma_dir == tmp_path / "c" and s.chat_log_path == tmp_path / "l.jsonl"


def test_real_repo_data_dir_is_found_from_any_cwd(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    s = make()
    assert s.chroma_dir.is_absolute() and s.chroma_dir.parent.name == "data"
    assert (s.chroma_dir.parent.parent / "backend").is_dir()


# --- optional LangSmith tracing ---------------------------------------------------------------

_LS_VARS = ("LANGSMITH_TRACING", "LANGSMITH_TRACING_V2", "LANGSMITH_API_KEY", "LANGSMITH_ENDPOINT",
            "LANGSMITH_PROJECT")


@pytest.fixture
def ls_env(monkeypatch):
    import os

    for v in _LS_VARS:  # restored after the test
        monkeypatch.setenv(v, "unset-marker")
        monkeypatch.delenv(v)
    yield os.environ
    config.export_langsmith_env(make(langsmith_tracing="false"))  # off for the next tests


def test_langsmith_off_by_default(ls_env):
    assert config.export_langsmith_env(make()) is False
    assert ls_env["LANGSMITH_TRACING"] == "false" and ls_env["LANGSMITH_TRACING_V2"] == "false"
    assert "LANGSMITH_API_KEY" not in ls_env


def test_langsmith_needs_both_flag_and_key(ls_env):
    assert config.export_langsmith_env(make(langsmith_tracing="true")) is False
    assert config.export_langsmith_env(make(langsmith_api_key="k")) is False
    assert config.export_langsmith_env(make(langsmith_tracing="", langsmith_api_key="k")) is False
    assert ls_env["LANGSMITH_TRACING"] == "false" and "LANGSMITH_API_KEY" not in ls_env


def test_langsmith_on_exports_env_with_eu_defaults(ls_env):
    from langsmith.utils import tracing_is_enabled

    assert config.export_langsmith_env(make(langsmith_tracing="true", langsmith_api_key="k")) is True
    assert ls_env["LANGSMITH_TRACING"] == "true" and ls_env["LANGSMITH_API_KEY"] == "k"
    assert ls_env["LANGSMITH_ENDPOINT"] == "https://eu.api.smith.langchain.com"
    assert ls_env["LANGSMITH_PROJECT"] == "hikesense"
    assert tracing_is_enabled() is True
    config.export_langsmith_env(make(langsmith_tracing="false"))  # and off again
    assert tracing_is_enabled() is False
