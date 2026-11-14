from acts.config import ACTS_MANIFEST, DATA_DIR, GOLDEN_SET, PROJECT_ROOT, load_settings


def test_paths_point_into_repository():
    assert (PROJECT_ROOT / "pyproject.toml").exists()
    assert DATA_DIR == PROJECT_ROOT / "data" / "raw"
    assert ACTS_MANIFEST.parent == DATA_DIR


def test_golden_set_is_in_eval_dir():
    assert GOLDEN_SET == PROJECT_ROOT / "eval" / "golden.jsonl"


def test_settings_defaults():
    s = load_settings(env_file=None)

    assert s.llm_model == "qwen3.5:4b"
    assert s.embed_model == "qwen3-embedding:0.6b"
    assert s.llm_temperature == 0.0
    assert s.ollama_url == "http://localhost:11434"
    assert s.is_local


def test_settings_from_environment(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "qwen3.5:4b")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.example.org/v1")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.5")

    s = load_settings(env_file=None)

    assert s.llm_model == "qwen3.5:4b"
    assert s.llm_temperature == 0.5
    assert not s.is_local


def test_empty_variable_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "")

    assert load_settings(env_file=None).llm_model == "qwen3.5:4b"


def test_env_file_is_loaded(tmp_path):
    env = tmp_path / ".env"
    env.write_text("LLM_MODEL=from-file\n", encoding="utf-8")

    assert load_settings(env_file=env).llm_model == "from-file"
