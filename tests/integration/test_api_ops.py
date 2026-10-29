from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes import ops
from src.infrastructure.config.env_manager import env_manager


def _build_ops_client(tmp_path, monkeypatch) -> TestClient:
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")
    monkeypatch.setattr(env_manager, "env_file", env_file)
    app = FastAPI()
    app.include_router(ops.router)
    return TestClient(app)


def test_runtime_switches_default_and_round_trip(tmp_path, monkeypatch):
    from src.api.routes.ops import RUNTIME_BOOL_KEYS, RUNTIME_INT_KEYS

    client = _build_ops_client(tmp_path, monkeypatch)

    defaults = client.get("/api/ops/config").json()
    assert defaults["KEEP_TASK_IMAGES"] is True
    assert defaults["ENABLE_RESPONSE_FORMAT"] is True
    assert defaults["AI_DEBUG_MODE"] is False
    assert defaults["TASK_FAILURE_THRESHOLD"] == RUNTIME_INT_KEYS["TASK_FAILURE_THRESHOLD"]

    response = client.put(
        "/api/ops/config",
        json={
            "KEEP_TASK_IMAGES": False,
            "AI_DEBUG_MODE": True,
            "TASK_FAILURE_THRESHOLD": 5,
            "TASK_LOG_RETENTION_DAYS": 14,
        },
    )
    assert response.status_code == 200

    updated = client.get("/api/ops/config").json()
    assert updated["KEEP_TASK_IMAGES"] is False
    assert updated["AI_DEBUG_MODE"] is True
    assert updated["TASK_FAILURE_THRESHOLD"] == 5
    assert updated["TASK_LOG_RETENTION_DAYS"] == 14
    # 未提交的开关保持原值
    for key, default in RUNTIME_BOOL_KEYS.items():
        if key in {"KEEP_TASK_IMAGES", "AI_DEBUG_MODE"}:
            continue
        assert updated[key] is default


def test_runtime_switches_reject_negative_numbers(tmp_path, monkeypatch):
    client = _build_ops_client(tmp_path, monkeypatch)

    response = client.put("/api/ops/config", json={"TASK_FAILURE_THRESHOLD": -1})

    assert response.status_code == 400
