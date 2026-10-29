from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes import config_file
from src.infrastructure.config.store import config_store


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(config_file.router)
    return TestClient(app)


def test_get_raw_returns_current_file():
    config_store.save_raw('{"ai": {"OPENAI_MODEL_NAME": "mimo"}}')

    response = _client().get("/api/config/raw")

    assert response.status_code == 200
    payload = response.json()
    assert payload["content"] == '{"ai": {"OPENAI_MODEL_NAME": "mimo"}}'
    assert payload["path"].endswith("config.jsonc")


def test_put_raw_accepts_jsonc_with_comments():
    client = _client()
    content = """
    {
      // 模型
      "ai": { "OPENAI_MODEL_NAME": "from-raw" },
    }
    """

    response = client.put("/api/config/raw", json={"content": content})

    assert response.status_code == 200
    assert config_store.get("OPENAI_MODEL_NAME") == "from-raw"


def test_put_raw_rejects_broken_json_and_keeps_old_file():
    config_store.save_raw('{"ai": {"OPENAI_MODEL_NAME": "keep-me"}}')
    before = config_store.raw()

    response = _client().put("/api/config/raw", json={"content": "{ broken"})

    assert response.status_code == 400
    assert config_store.raw() == before


def test_masked_hides_secret_values():
    config_store.apply({"OPENAI_API_KEY": "sk-1234567890abcdef"})

    values = _client().get("/api/config/masked").json()["values"]

    assert values["OPENAI_API_KEY"] == "sk-1****cdef"
    assert "sk-1234567890abcdef" not in str(values)
