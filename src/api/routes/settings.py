"""
设置管理路由
"""
import glob
import os
import shutil
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.dependencies import get_process_service
from src.infrastructure.config.env_manager import env_manager
from src.infrastructure.config.settings import (
    AISettings,
    reload_settings,
    scraper_settings,
)
from src.services.ai_request_compat import (
    CHAT_COMPLETIONS_API_MODE,
    RESPONSES_API_MODE,
    build_ai_request_params,
    create_ai_response_sync,
    is_chat_completions_api_unsupported_error,
    is_responses_api_unsupported_error,
)
from src.services.ai_response_parser import extract_ai_response_content
from src.services.notification_config_service import (
    DISABLED_CHANNELS_KEY,
    NotificationSettingsValidationError,
    build_configured_channels,
    build_notification_settings_response,
    build_notification_status_flags,
    load_notification_settings,
    model_dump,
    prepare_notification_test_settings,
    prepare_notification_settings_update,
)
from src.services.notification_service import build_notification_service
from src.services.process_service import ProcessService


router = APIRouter(prefix="/api/settings", tags=["settings"])
AI_TEST_PROMPT = "Reply with OK only."
AI_TEST_MAX_OUTPUT_TOKENS = 32
_MODEL_CHECK_PROMPT_FILE = Path("prompts/model_check_prompt.txt")


def _reload_env() -> None:
    load_dotenv(dotenv_path=env_manager.env_file, override=True)
    reload_settings()


def _env_bool(key: str, default: bool = False) -> bool:
    value = env_manager.get_value(key)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(key: str, default: int) -> int:
    value = env_manager.get_value(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _normalize_bool_value(value: bool) -> str:
    return "true" if value else "false"


class NotificationSettingsModel(BaseModel):
    """通知设置模型"""

    NTFY_TOPIC_URL: Optional[str] = None
    PUSHPLUS_TOKEN: Optional[str] = None
    PUSHPLUS_TOPIC: Optional[str] = None
    GOTIFY_URL: Optional[str] = None
    GOTIFY_TOKEN: Optional[str] = None
    BARK_URL: Optional[str] = None
    WX_BOT_URL: Optional[str] = None
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None
    TELEGRAM_API_BASE_URL: Optional[str] = None
    WEBHOOK_URL: Optional[str] = None
    WEBHOOK_METHOD: Optional[str] = None
    WEBHOOK_HEADERS: Optional[str] = None
    WEBHOOK_CONTENT_TYPE: Optional[str] = None
    WEBHOOK_QUERY_PARAMETERS: Optional[str] = None
    WEBHOOK_BODY: Optional[str] = None
    PCURL_TO_MOBILE: Optional[bool] = None
    # 显式停用的渠道：配置保留但不发送
    DISABLED_CHANNELS: Optional[list[str]] = None


class NotificationTestRequest(BaseModel):
    """通知测试请求"""

    channel: Optional[str] = None
    settings: NotificationSettingsModel = Field(default_factory=NotificationSettingsModel)


class AISettingsModel(BaseModel):
    """AI设置模型"""

    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: Optional[str] = None
    OPENAI_MODEL_NAME: Optional[str] = None
    SKIP_AI_ANALYSIS: Optional[bool] = None
    PROXY_URL: Optional[str] = None
    # 型号判断用独立模型；留空则回退到上面的主配置
    MODEL_CHECK_ENABLED: Optional[bool] = None
    MODEL_CHECK_BASE_URL: Optional[str] = None
    MODEL_CHECK_API_KEY: Optional[str] = None
    MODEL_CHECK_MODEL_NAME: Optional[str] = None
    MODEL_CHECK_PROXY_URL: Optional[str] = None
    MODEL_CHECK_PREFILTER_REGEX: Optional[str] = None


class RotationSettingsModel(BaseModel):
    ACCOUNT_ROTATION_ENABLED: Optional[bool] = None
    ACCOUNT_ROTATION_MODE: Optional[str] = None
    ACCOUNT_ROTATION_RETRY_LIMIT: Optional[int] = None
    ACCOUNT_BLACKLIST_TTL: Optional[int] = None
    ACCOUNT_STATE_DIR: Optional[str] = None
    PROXY_ROTATION_ENABLED: Optional[bool] = None
    PROXY_ROTATION_MODE: Optional[str] = None
    PROXY_POOL: Optional[str] = None
    PROXY_ROTATION_RETRY_LIMIT: Optional[int] = None
    PROXY_BLACKLIST_TTL: Optional[int] = None


@router.get("/notifications")
async def get_notification_settings():
    return build_notification_settings_response(load_notification_settings())


@router.put("/notifications")
async def update_notification_settings(settings: NotificationSettingsModel):
    try:
        updates, deletions, merged_settings = prepare_notification_settings_update(
            model_dump(settings, exclude_unset=True),
            load_notification_settings(),
        )
    except NotificationSettingsValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if settings.DISABLED_CHANNELS is not None:
        updates[DISABLED_CHANNELS_KEY] = ",".join(
            sorted({channel.strip() for channel in settings.DISABLED_CHANNELS if channel.strip()})
        )

    success = env_manager.apply_changes(updates=updates, deletions=deletions)
    if not success:
        raise HTTPException(status_code=500, detail="更新通知设置失败")

    _reload_env()
    return {
        "message": "通知设置已成功更新",
        "configured_channels": build_configured_channels(merged_settings),
    }


@router.post("/notifications/test")
async def test_notification_settings(payload: NotificationTestRequest):
    try:
        merged_settings = prepare_notification_test_settings(
            model_dump(payload.settings, exclude_unset=True),
            load_notification_settings(),
            channel=payload.channel,
        )
    except NotificationSettingsValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    service = build_notification_service(merged_settings, respect_disabled=False)
    if not service.clients:
        if payload.channel:
            raise HTTPException(
                status_code=422,
                detail=f"渠道 {payload.channel} 未配置或不受支持",
            )
        raise HTTPException(status_code=422, detail="请至少配置一个可用的通知渠道")

    results = await service.send_test_notification()
    if payload.channel:
        if payload.channel not in results:
            raise HTTPException(
                status_code=422,
                detail=f"渠道 {payload.channel} 未配置或不受支持",
            )
        results = {payload.channel: results[payload.channel]}

    return {
        "message": "测试通知已执行",
        "results": results,
    }


@router.get("/notifications/history")
async def get_notification_history(limit: int = 50):
    """最近的发送记录（含失败），排查「为什么没收到通知」用"""
    from src.services.notification_history import read_recent

    return {"records": read_recent(max(1, min(limit, 200)))}


@router.get("/rotation")
async def get_rotation_settings():
    return {
        "ACCOUNT_ROTATION_ENABLED": _env_bool("ACCOUNT_ROTATION_ENABLED", False),
        "ACCOUNT_ROTATION_MODE": env_manager.get_value("ACCOUNT_ROTATION_MODE", "per_task"),
        "ACCOUNT_ROTATION_RETRY_LIMIT": _env_int("ACCOUNT_ROTATION_RETRY_LIMIT", 2),
        "ACCOUNT_BLACKLIST_TTL": _env_int("ACCOUNT_BLACKLIST_TTL", 300),
        "ACCOUNT_STATE_DIR": env_manager.get_value("ACCOUNT_STATE_DIR", "state"),
        "PROXY_ROTATION_ENABLED": _env_bool("PROXY_ROTATION_ENABLED", False),
        "PROXY_ROTATION_MODE": env_manager.get_value("PROXY_ROTATION_MODE", "per_task"),
        "PROXY_POOL": env_manager.get_value("PROXY_POOL", ""),
        "PROXY_ROTATION_RETRY_LIMIT": _env_int("PROXY_ROTATION_RETRY_LIMIT", 2),
        "PROXY_BLACKLIST_TTL": _env_int("PROXY_BLACKLIST_TTL", 300),
    }


@router.put("/rotation")
async def update_rotation_settings(settings: RotationSettingsModel):
    updates = {}
    payload = model_dump(settings, exclude_unset=True)
    for key, value in payload.items():
        if isinstance(value, bool):
            updates[key] = _normalize_bool_value(value)
        else:
            updates[key] = str(value)
    success = env_manager.update_values(updates)
    if not success:
        raise HTTPException(status_code=500, detail="更新轮换设置失败")
    _reload_env()
    return {"message": "轮换设置已成功更新"}


_PROCESS_START = time.time()


def _disk_summary() -> Optional[dict]:
    try:
        usage = shutil.disk_usage(".")
    except OSError:
        return None
    used_percent = round(usage.used / usage.total * 100, 1) if usage.total else 0
    return {
        "total_bytes": usage.total,
        "free_bytes": usage.free,
        "used_percent": used_percent,
    }


def _database_summary() -> dict:
    from src.infrastructure.persistence.sqlite_connection import get_database_path

    path = get_database_path()
    size = os.path.getsize(path) if os.path.exists(path) else 0
    return {"path": path, "size_bytes": size}


def _backup_summary() -> dict:
    files = sorted(glob.glob(os.path.join("data", "backups", "app-*.sqlite3")))
    return {
        "count": len(files),
        "latest": os.path.basename(files[-1]) if files else None,
    }


def _accounts_summary() -> dict:
    from src.services.account_state_store import read_expiry

    raw_dir = (env_manager.get_value("ACCOUNT_STATE_DIR", "state") or "state").strip()
    state_dir = raw_dir.strip("\"'")
    if not os.path.isdir(state_dir):
        return {"count": 0, "nearest_expires_at": None}
    count = 0
    expiries = []
    for name in sorted(os.listdir(state_dir)):
        if not name.endswith(".json"):
            continue
        count += 1
        try:
            expires_at = read_expiry(os.path.join(state_dir, name))
        except Exception:
            expires_at = None
        if expires_at:
            expiries.append(expires_at)
    return {
        "count": count,
        "nearest_expires_at": min(expiries) if expiries else None,
    }


def _frontend_built_at() -> Optional[str]:
    path = os.path.join("dist", "index.html")
    if not os.path.exists(path):
        return None
    from datetime import datetime

    return datetime.fromtimestamp(os.path.getmtime(path)).isoformat(timespec="seconds")


@router.get("/status")
async def get_system_status(
    process_service: ProcessService = Depends(get_process_service),
):
    state_file = "xianyu_state.json"
    login_state_exists = os.path.exists(state_file)
    env_file_exists = os.path.exists(env_manager.env_file)
    openai_api_key = env_manager.get_value("OPENAI_API_KEY", "")
    openai_base_url = env_manager.get_value("OPENAI_BASE_URL", "")
    openai_model_name = env_manager.get_value("OPENAI_MODEL_NAME", "")
    ai_settings = AISettings()
    notification_settings = load_notification_settings()
    configured_channels = build_configured_channels(notification_settings)
    running_task_ids = [
        task_id
        for task_id, process in process_service.processes.items()
        if process and process.returncode is None
    ]

    return {
        "ai_configured": ai_settings.is_configured(),
        "notification_configured": bool(configured_channels),
        "headless_mode": scraper_settings.run_headless,
        "running_in_docker": scraper_settings.running_in_docker,
        "scraper_running": len(running_task_ids) > 0,
        "running_task_ids": running_task_ids,
        "login_state_file": {
            "exists": login_state_exists,
            "path": state_file,
        },
        "env_file": {
            "exists": env_file_exists,
            "openai_api_key_set": bool(openai_api_key),
            "openai_base_url_set": bool(openai_base_url),
            "openai_model_name_set": bool(openai_model_name),
            **build_notification_status_flags(notification_settings),
        },
        "configured_notification_channels": configured_channels,
        "app": {
            "version": os.getenv("APP_VERSION", "").strip() or None,
            "uptime_seconds": int(time.time() - _PROCESS_START),
            "frontend_built_at": _frontend_built_at(),
        },
        "disk": _disk_summary(),
        "database": _database_summary(),
        "backups": _backup_summary(),
        "accounts": _accounts_summary(),
    }


@router.get("/ai")
async def get_ai_settings():
    return {
        "OPENAI_BASE_URL": env_manager.get_value("OPENAI_BASE_URL", ""),
        "OPENAI_MODEL_NAME": env_manager.get_value("OPENAI_MODEL_NAME", ""),
        "SKIP_AI_ANALYSIS": env_manager.get_value("SKIP_AI_ANALYSIS", "false").lower() == "true",
        "PROXY_URL": env_manager.get_value("PROXY_URL", ""),
        "MODEL_CHECK_ENABLED": env_manager.get_value("MODEL_CHECK_ENABLED", "true").lower() != "false",
        "MODEL_CHECK_BASE_URL": env_manager.get_value("MODEL_CHECK_BASE_URL", ""),
        "MODEL_CHECK_MODEL_NAME": env_manager.get_value("MODEL_CHECK_MODEL_NAME", ""),
        "MODEL_CHECK_PROXY_URL": env_manager.get_value("MODEL_CHECK_PROXY_URL", ""),
        "MODEL_CHECK_PREFILTER_REGEX": env_manager.get_value("MODEL_CHECK_PREFILTER_REGEX", ""),
        "MODEL_CHECK_API_KEY_SET": bool(env_manager.get_value("MODEL_CHECK_API_KEY", "")),
        "MODEL_CHECK_PROMPT_EXISTS": (_MODEL_CHECK_PROMPT_FILE).exists(),
    }


@router.put("/ai")
async def update_ai_settings(settings: AISettingsModel):
    updates = {}
    if settings.OPENAI_API_KEY is not None:
        updates["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
    if settings.OPENAI_BASE_URL is not None:
        updates["OPENAI_BASE_URL"] = settings.OPENAI_BASE_URL
    if settings.OPENAI_MODEL_NAME is not None:
        updates["OPENAI_MODEL_NAME"] = settings.OPENAI_MODEL_NAME
    if settings.SKIP_AI_ANALYSIS is not None:
        updates["SKIP_AI_ANALYSIS"] = str(settings.SKIP_AI_ANALYSIS).lower()
    if settings.PROXY_URL is not None:
        updates["PROXY_URL"] = settings.PROXY_URL
    if settings.MODEL_CHECK_ENABLED is not None:
        updates["MODEL_CHECK_ENABLED"] = str(settings.MODEL_CHECK_ENABLED).lower()
    if settings.MODEL_CHECK_API_KEY is not None:
        updates["MODEL_CHECK_API_KEY"] = settings.MODEL_CHECK_API_KEY
    if settings.MODEL_CHECK_BASE_URL is not None:
        updates["MODEL_CHECK_BASE_URL"] = settings.MODEL_CHECK_BASE_URL
    if settings.MODEL_CHECK_MODEL_NAME is not None:
        updates["MODEL_CHECK_MODEL_NAME"] = settings.MODEL_CHECK_MODEL_NAME
    if settings.MODEL_CHECK_PROXY_URL is not None:
        updates["MODEL_CHECK_PROXY_URL"] = settings.MODEL_CHECK_PROXY_URL
    if settings.MODEL_CHECK_PREFILTER_REGEX is not None:
        updates["MODEL_CHECK_PREFILTER_REGEX"] = settings.MODEL_CHECK_PREFILTER_REGEX

    success = env_manager.update_values(updates)
    if not success:
        raise HTTPException(status_code=500, detail="更新AI设置失败")
    _reload_env()
    return {"message": "AI设置已成功更新"}


def _test_config_value(payload: dict, field: str, env_key: str, fallback_env: Optional[str] = None) -> str:
    """请求里填了就用请求的，否则用已存的，再否则用主配置的。"""
    value = (payload.get(field) or "").strip()
    if value:
        return value
    value = env_manager.get_value(env_key, "")
    if value:
        return value
    return env_manager.get_value(fallback_env, "") if fallback_env else ""


@router.post("/ai/test")
async def test_ai_settings(settings: dict):
    """测试AI模型设置是否有效。

    mode=model_check 时测型号判断那套配置，留空的项回退到主配置。
    """
    try:
        from openai import OpenAI
        import httpx

        if settings.get("mode") == "model_check":
            api_key = _test_config_value(settings, "MODEL_CHECK_API_KEY", "MODEL_CHECK_API_KEY", "OPENAI_API_KEY")
            base_url = _test_config_value(settings, "MODEL_CHECK_BASE_URL", "MODEL_CHECK_BASE_URL", "OPENAI_BASE_URL")
            model_name = _test_config_value(settings, "MODEL_CHECK_MODEL_NAME", "MODEL_CHECK_MODEL_NAME", "OPENAI_MODEL_NAME")
            proxy_url = _test_config_value(settings, "MODEL_CHECK_PROXY_URL", "MODEL_CHECK_PROXY_URL", "PROXY_URL")
        else:
            api_key = _test_config_value(settings, "OPENAI_API_KEY", "OPENAI_API_KEY")
            base_url = (settings.get("OPENAI_BASE_URL") or "").strip()
            model_name = (settings.get("OPENAI_MODEL_NAME") or "").strip()
            proxy_url = (settings.get("PROXY_URL") or "").strip()

        client_params = {
            "api_key": api_key,
            "base_url": base_url,
            "timeout": httpx.Timeout(30.0),
        }

        if proxy_url:
            client_params["http_client"] = httpx.Client(proxy=proxy_url)

        client = OpenAI(**client_params)
        messages = [{"role": "user", "content": AI_TEST_PROMPT}]
        api_mode = CHAT_COMPLETIONS_API_MODE

        try:
            response = create_ai_response_sync(
                client,
                api_mode,
                build_ai_request_params(
                    api_mode,
                    model=model_name,
                    messages=messages,
                    max_output_tokens=AI_TEST_MAX_OUTPUT_TOKENS,
                ),
            )
        except Exception as exc:
            if not is_chat_completions_api_unsupported_error(exc):
                raise
            api_mode = RESPONSES_API_MODE
            response = create_ai_response_sync(
                client,
                api_mode,
                build_ai_request_params(
                    api_mode,
                    model=model_name,
                    messages=messages,
                    max_output_tokens=AI_TEST_MAX_OUTPUT_TOKENS,
                ),
            )

        return {
            "success": True,
            "message": "AI模型连接测试成功！",
            "response": extract_ai_response_content(response),
        }
    except Exception as exc:
        return {
            "success": False,
            "message": f"AI模型连接测试失败: {exc}",
        }
