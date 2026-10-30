"""
新架构的主应用入口
整合所有路由和服务
"""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.gzip import GZipMiddleware

from src.api.routes import (
    dashboard,
    tasks,
    logs,
    settings,
    prompts,
    results,
    login_state,
    websocket,
    accounts,
    favorites,
    reanalyze,
    items,
    image_proxy,
    model_check,
    ops,
    config_file,
)
from src.api.dependencies import (
    set_process_service,
    set_scheduler_service,
    set_task_generation_service,
)
from src.services.task_service import TaskService
from src.services.process_service import ProcessService
from src.services.scheduler_service import SchedulerService
from src.services.task_log_cleanup_service import cleanup_task_logs
from src.services.prompt_defaults import ensure_default_prompts
from src.services.task_generation_service import TaskGenerationService
from src.services.sqlite_backup_service import sqlite_backup_loop
from src.infrastructure.persistence.sqlite_bootstrap import bootstrap_sqlite_storage
from src.infrastructure.persistence.sqlite_task_repository import SqliteTaskRepository
from src.infrastructure.config.settings import settings as app_settings


# 全局服务实例
process_service = ProcessService()
scheduler_service = SchedulerService(process_service)
task_generation_service = TaskGenerationService()


async def _sync_task_runtime_status(task_id: int, is_running: bool) -> None:
    task_service = TaskService(SqliteTaskRepository())
    task = await task_service.get_task(task_id)
    if not task or task.is_running == is_running:
        return
    await task_service.update_task_status(task_id, is_running)
    await websocket.broadcast_message(
        "task_status_changed",
        {"id": task_id, "is_running": is_running},
    )


process_service.set_lifecycle_hooks(
    on_started=lambda task_id: _sync_task_runtime_status(task_id, True),
    on_stopped=lambda task_id: _sync_task_runtime_status(task_id, False),
)

# 设置全局 ProcessService 实例供依赖注入使用
set_process_service(process_service)
set_scheduler_service(scheduler_service)
set_task_generation_service(task_generation_service)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    print("正在启动应用...")
    if app_settings.web_password == "admin123":
        print("[安全提醒] WEB_PASSWORD 仍是默认值 admin123，请尽快在 .env 里修改并重启容器。")
    bootstrap_sqlite_storage()
    # SQLite 自动备份：启动时备份一次，之后每 24 小时一次；失败只打日志
    backup_task = asyncio.create_task(sqlite_backup_loop())
    created_prompts = ensure_default_prompts()
    if created_prompts:
        print(f"已从内置副本补齐提示词: {', '.join(created_prompts)}")
    cleanup_task_logs(keep_days=app_settings.task_log_retention_days)

    # 重置所有任务状态为停止
    task_repo = SqliteTaskRepository()
    task_service = TaskService(task_repo)
    tasks_list = await task_service.get_all_tasks()

    for task in tasks_list:
        if task.is_running:
            await task_service.update_task_status(task.id, False)

    # 加载定时任务
    await scheduler_service.reload_jobs(tasks_list)
    scheduler_service.start()

    print("应用启动完成")

    yield

    # 关闭时
    print("正在关闭应用...")
    backup_task.cancel()
    try:
        await backup_task
    except asyncio.CancelledError:
        pass
    scheduler_service.stop()
    await process_service.stop_all()
    print("应用已关闭")


# 创建 FastAPI 应用
app = FastAPI(
    title="闲鱼智能监控机器人",
    description="基于AI的闲鱼商品监控系统",
    version="2.0.0",
    lifespan=lifespan
)

# 注册路由
app.include_router(tasks.router)
app.include_router(dashboard.router)
app.include_router(logs.router)
app.include_router(settings.router)
app.include_router(prompts.router)
app.include_router(results.router)
app.include_router(login_state.router)
app.include_router(websocket.router)
app.include_router(accounts.router)
app.include_router(favorites.router)
app.include_router(reanalyze.router)
app.include_router(items.router)
app.include_router(image_proxy.router)
app.include_router(model_check.router)
app.include_router(ops.router)
app.include_router(config_file.router)

# 静态资源均为 Vite 哈希产物，可缓存 - 注册 GZip 压缩以加快页面加载
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 挂载静态文件
# 旧的静态文件目录（用于截图等）
app.mount("/static", StaticFiles(directory="static"), name="static")

# 挂载 Vue 3 前端构建产物
# 注意：需要在所有 API 路由之后挂载，以避免覆盖 API 路由
import os

class HashedStaticFiles(StaticFiles):
    """dist/assets 下均为带内容哈希的文件名，可安全长缓存（immutable）。"""

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

if os.path.exists("dist"):
    app.mount("/assets", HashedStaticFiles(directory="dist/assets"), name="assets")


# 健康检查端点
@app.get("/health")
async def health_check():
    """健康检查（无需认证）"""
    return {"status": "healthy", "message": "服务正常运行"}


# 认证状态检查端点
import secrets

from fastapi import Request, HTTPException, Response
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from src.api.auth_session import (
    COOKIE_NAME,
    SESSION_TTL_SECONDS,
    is_authenticated,
    issue_token,
)

class LoginRequest(BaseModel):
    username: str
    password: str


def _credentials_match(username: str, password: str) -> bool:
    return secrets.compare_digest(username, app_settings.web_username) and secrets.compare_digest(
        password, app_settings.web_password
    )


@app.post("/auth/status")
async def auth_status(payload: LoginRequest, response: Response):
    """检查认证状态，成功后下发会话 Cookie"""
    if not _credentials_match(payload.username, payload.password):
        raise HTTPException(status_code=401, detail="认证失败")
    response.set_cookie(
        COOKIE_NAME,
        issue_token(payload.username, app_settings.web_password),
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return {"authenticated": True, "username": payload.username}


@app.get("/auth/session")
async def auth_session(request: Request):
    """当前浏览器是否已有有效会话，前端启动时用它决定是否跳登录页"""
    authenticated = is_authenticated(request.cookies)
    return {
        "authenticated": authenticated,
        "username": app_settings.web_username if authenticated else None,
    }


@app.post("/auth/logout")
async def auth_logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"authenticated": False}


@app.middleware("http")
async def require_web_session(request: Request, call_next):
    """除 /health、登录端点和静态资源外，/api/* 一律要求有效会话"""
    if request.url.path.startswith("/api/") and not is_authenticated(request.cookies):
        return JSONResponse(status_code=401, content={"detail": "未登录或会话已过期"})
    return await call_next(request)


# 主页路由 - 服务 Vue 3 SPA

@app.get("/")
async def read_root(request: Request):
    """提供 Vue 3 SPA 的主页面"""
    if os.path.exists("dist/index.html"):
        return FileResponse("dist/index.html", headers={"Cache-Control": "no-cache"})
    else:
        return JSONResponse(
            status_code=500,
            content={"error": "前端构建产物不存在，请先运行 cd web-ui && npm run build"}
        )


# Catch-all 路由 - 处理所有前端路由（必须放在最后）
@app.get("/{full_path:path}")
async def serve_spa(request: Request, full_path: str):
    """
    Catch-all 路由，将所有非 API 请求重定向到 index.html
    这样可以支持 Vue Router 的 HTML5 History 模式
    """
    # 如果请求的是静态资源（如 favicon.ico），返回 404
    if full_path.endswith(('.ico', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.css', '.js', '.json')):
        return JSONResponse(status_code=404, content={"error": "资源未找到"})

    # 其他所有路径都返回 index.html，让前端路由处理
    if os.path.exists("dist/index.html"):
        return FileResponse("dist/index.html", headers={"Cache-Control": "no-cache"})
    else:
        return JSONResponse(
            status_code=500,
            content={"error": "前端构建产物不存在，请先运行 cd web-ui && npm run build"}
        )


if __name__ == "__main__":
    import uvicorn
    from src.infrastructure.config.settings import settings

    print(f"启动新架构应用，端口: {app_settings.server_port}")
    uvicorn.run(app, host="0.0.0.0", port=app_settings.server_port)
