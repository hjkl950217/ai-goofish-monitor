"""浏览器行为采样：把一次任务里浏览器收发的东西写到 /tmp，供事后分析。

登录态到底依赖什么（cookies、localStorage、IndexedDB、Cache Storage、
服务端下发的 Set-Cookie）只能从真实执行里看。这里把一次任务的相关数据
落成文件，用完即弃，不做长期存储。
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
from datetime import datetime
from typing import Optional

TRACE_ENV = "AGM_BROWSER_TRACE"
TRACE_DIR_ENV = "AGM_TRACE_DIR"
MAX_MB_ENV = "AGM_TRACE_MAX_MB"
DEFAULT_TRACE_DIR = "/tmp/agm-trace"
DEFAULT_MAX_MB = 200

TARGET_HOSTS = ("goofish.com", "taobao.com")
CAPTURE_RESOURCE_TYPES = {"xhr", "fetch", "document"}
BODY_LIMIT = 20000
MAX_LISTED = 50

_SAFE_NAME = re.compile(r"[^0-9A-Za-z一-龥_-]+")

SNAPSHOT_JS = """async () => {
  const dump = (store) => {
    const out = {};
    for (let i = 0; i < store.length; i += 1) {
      const key = store.key(i);
      if (key !== null) out[key] = store.getItem(key);
    }
    return out;
  };
  const cachesList = [];
  try {
    for (const name of await caches.keys()) {
      const cache = await caches.open(name);
      const keys = await cache.keys();
      cachesList.push({ name, count: keys.length, urls: keys.slice(0, 200).map((r) => r.url) });
    }
  } catch (e) { /* 部分页面没有 caches */ }
  const idb = [];
  try {
    if (indexedDB.databases) {
      for (const db of await indexedDB.databases()) idb.push({ name: db.name, version: db.version });
    }
  } catch (e) { /* 同上 */ }
  return {
    cookieString: document.cookie,
    localStorage: dump(localStorage),
    sessionStorage: dump(sessionStorage),
    caches: cachesList,
    indexedDB: idb,
  };
}"""


def is_enabled() -> bool:
    value = (os.getenv(TRACE_ENV) or "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def base_dir() -> str:
    return (os.getenv(TRACE_DIR_ENV) or "").strip() or DEFAULT_TRACE_DIR


def _enforce_size_limit(root: str) -> None:
    """总量超过上限就从最旧的会话目录开始删；删失败只打日志。"""
    try:
        max_bytes = int(os.getenv(MAX_MB_ENV, str(DEFAULT_MAX_MB))) * 1024 * 1024
    except ValueError:
        max_bytes = DEFAULT_MAX_MB * 1024 * 1024
    sessions = []
    total = 0
    for entry in os.scandir(root):
        if not entry.is_dir():
            continue
        size = sum(f.stat().st_size for f in os.scandir(entry.path) if f.is_file())
        sessions.append((entry.stat().st_mtime, entry.path, size))
        total += size
    for _, path, size in sorted(sessions):  # 最旧在前
        if total <= max_bytes:
            break
        try:
            shutil.rmtree(path)
            total -= size
        except Exception as exc:  # noqa: BLE001
            print(f"[TRACE] 清理超限目录失败: {path}: {exc}")


class TraceSession:
    def __init__(self, path: str):
        self.path = path
        self._seq = 0
        self._file = open(os.path.join(path, "network.jsonl"), "a", encoding="utf-8")

    def attach(self, context) -> None:
        context.on("response", self._on_response)

    def _on_response(self, response) -> None:
        try:
            if self._wanted(response):
                asyncio.create_task(self._dump(response))
        except Exception:  # noqa: BLE001
            pass

    @staticmethod
    def _wanted(response) -> bool:
        url = response.url or ""
        if not any(host in url for host in TARGET_HOSTS):
            return False
        if response.request.resource_type in CAPTURE_RESOURCE_TYPES:
            return True
        # 静态资源也可能下发 Set-Cookie，碰到就记
        return any(key.lower() == "set-cookie" for key in response.headers)

    async def _dump(self, response) -> None:
        try:
            request = response.request
            headers = response.headers
            body = None
            content_type = headers.get("content-type") or ""
            if request.resource_type in {"xhr", "fetch"} and "json" in content_type:
                try:
                    body = (await response.body()).decode("utf-8", "replace")[:BODY_LIMIT]
                except Exception as exc:  # noqa: BLE001
                    body = f"<body unavailable: {exc}>"
            self._seq += 1
            record = {
                "seq": self._seq,
                "ts": datetime.now().isoformat(timespec="milliseconds"),
                "url": response.url,
                "method": request.method,
                "status": response.status,
                "resource_type": request.resource_type,
                "request_headers": request.headers,
                "request_body": (request.post_data or "")[:BODY_LIMIT],
                "response_headers": headers,
                "set_cookie": headers.get("set-cookie"),
                "body": body,
            }
            self._file.write(json.dumps(record, ensure_ascii=False) + "\n")
            self._file.flush()
        except Exception as exc:  # noqa: BLE001
            print(f"[TRACE] 记录响应失败: {exc}")

    async def snapshot(self, context, page) -> None:
        """任务收尾时补一份快照：httpOnly cookie 只能从 context 拿，storage 从页面拿。"""
        try:
            self._write_json("cookies.json", await context.cookies())
        except Exception as exc:  # noqa: BLE001
            print(f"[TRACE] 采集 cookies 失败: {exc}")
        try:
            self._write_json("storage.json", await page.evaluate(SNAPSHOT_JS))
        except Exception as exc:  # noqa: BLE001
            print(f"[TRACE] 采集 storage 失败: {exc}")

    def _write_json(self, name: str, data) -> None:
        with open(os.path.join(self.path, name), "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)

    def close(self) -> None:
        try:
            self._file.close()
        except Exception:  # noqa: BLE001
            pass


def start(task_name: str, state_file: str = "") -> Optional[TraceSession]:
    """开关关着返回 None；开了就在 trace 目录下建一个新目录。"""
    if not is_enabled():
        return None
    safe_name = _SAFE_NAME.sub("_", str(task_name or "task"))[:40]
    root = base_dir()
    os.makedirs(root, exist_ok=True)
    _enforce_size_limit(root)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(root, f"{safe_name}_{stamp}")
    suffix = 1
    while os.path.exists(path):
        suffix += 1
        path = os.path.join(root, f"{safe_name}_{stamp}_{suffix}")
    os.makedirs(path)
    with open(os.path.join(path, "meta.json"), "w", encoding="utf-8") as handle:
        json.dump(
            {
                "task_name": task_name,
                "state_file": state_file,
                "started_at": datetime.now().isoformat(timespec="seconds"),
            },
            handle,
            ensure_ascii=False,
            indent=2,
        )
    return TraceSession(path)


def list_traces(root: str, limit: int = MAX_LISTED) -> list:
    if not root or not os.path.isdir(root):
        return []
    items = []
    for name in sorted(os.listdir(root), reverse=True):
        path = os.path.join(root, name)
        if not os.path.isdir(path):
            continue
        files = []
        total = 0
        for entry in os.scandir(path):
            if entry.is_file():
                size = entry.stat().st_size
                total += size
                files.append({"name": entry.name, "size": size})
        items.append({
            "name": name,
            "path": path,
            "size": total,
            "mtime": datetime.fromtimestamp(os.stat(path).st_mtime).isoformat(timespec="seconds"),
            "files": files,
        })
        if len(items) >= limit:
            break
    return items
