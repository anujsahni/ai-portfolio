import pytest

from weekendwise.config import load_settings
from weekendwise.errors import ConfigError

BASE = {
    "GCP_PROJECT_ID": "demo-project",
    "GCP_REGION": "us-central1",
    "VERTEX_GENERATION_MODEL_ID": "gen-model",
    "VERTEX_EMBEDDING_MODEL_ID": "embed-model",
    "VERTEX_EMBEDDING_DIMENSION": "768",
}


def load(env, tmp_path):
    return load_settings(env=env, dotenv_path=tmp_path / "missing.env")


def test_defaults(tmp_path):
    s = load(BASE, tmp_path)
    assert s.generation_location == "global"
    assert s.embedding_location == "us-central1"  # follows GCP_REGION
    assert s.embedding_dimension == 768
    assert s.thinking_level == "LOW"
    assert s.model_retry_attempts == 1


def test_reports_every_missing_value(tmp_path):
    with pytest.raises(ConfigError) as err:
        load({}, tmp_path)
    msg = str(err.value)
    for name in ["GCP_PROJECT_ID", "VERTEX_GENERATION_MODEL_ID", "VERTEX_EMBEDDING_MODEL_ID", "VERTEX_EMBEDDING_DIMENSION"]:
        assert name in msg
    assert ".env" in msg  # tells the operator where to fix it


@pytest.mark.parametrize("value", ["0", "4096", "abc"])
def test_rejects_bad_dimension(tmp_path, value):
    with pytest.raises(ConfigError, match="VERTEX_EMBEDDING_DIMENSION"):
        load({**BASE, "VERTEX_EMBEDDING_DIMENSION": value}, tmp_path)


def test_rejects_bad_limits(tmp_path):
    with pytest.raises(ConfigError) as err:
        load({**BASE, "MAX_OUTPUT_TOKENS": "1", "MODEL_RETRY_ATTEMPTS": "9", "VERTEX_THINKING_LEVEL": "LOUD"}, tmp_path)
    msg = str(err.value)
    assert "MAX_OUTPUT_TOKENS" in msg and "MODEL_RETRY_ATTEMPTS" in msg and "VERTEX_THINKING_LEVEL" in msg


def test_reads_dotenv_and_env_wins(tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text("# comment\nGCP_PROJECT_ID=from-file\nVERTEX_EMBEDDING_DIMENSION=768 # inline\n")
    env = {k: v for k, v in BASE.items() if k not in ("GCP_PROJECT_ID", "VERTEX_EMBEDDING_DIMENSION")}
    s = load_settings(env=env, dotenv_path=dotenv)
    assert s.project_id == "from-file"
    assert s.embedding_dimension == 768
    s2 = load_settings(env={**env, "GCP_PROJECT_ID": "from-env"}, dotenv_path=dotenv)
    assert s2.project_id == "from-env"
