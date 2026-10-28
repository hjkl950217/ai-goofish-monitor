"""登录态文件的合并写回与有效期读取。

浏览器跑完任务后，服务端下发的续期 cookie 只在 Playwright 上下文里。
这里把它合并回原始 JSON：只换 cookies，扩展导出的 env/headers/page/storage
等指纹字段原样保留，否则下次启动会退回通用参数。
"""
from __future__ import annotations

import contextlib
import json
import os
import time
from typing import Any, Dict, Iterator, List, Optional

# 决定账号本身还能用多久的登录票据；_m_h5_tk 这类短期票会自动刷新，不计入
LOGIN_COOKIE_NAMES = ("cookie2", "unb", "sgcookie")


def _cookie_key(cookie: Dict[str, Any]) -> tuple:
    return (
        str(cookie.get("name") or ""),
        str(cookie.get("domain") or ""),
        str(cookie.get("path") or "/"),
    )


def merge_cookies(old: Optional[List[dict]], new: Optional[List[dict]]) -> List[dict]:
    """按 (name, domain, path) 合并：新值覆盖旧值，旧独有的保留。"""
    merged: Dict[tuple, dict] = {}
    for cookie in old or []:
        if isinstance(cookie, dict) and cookie.get("name"):
            merged[_cookie_key(cookie)] = cookie
    for cookie in new or []:
        if isinstance(cookie, dict) and cookie.get("name"):
            merged[_cookie_key(cookie)] = cookie
    return list(merged.values())


@contextlib.contextmanager
def _file_lock(path: str) -> Iterator[None]:
    """跨进程独占锁。

    用独立的 .lock 文件：原子写是 os.replace 换 inode，锁住数据文件本身会失效。
    shortcut: Windows 没有 fcntl，开发环境退化为不加锁，生产环境是 Linux 容器。
    """
    lock_path = f"{path}.lock"
    parent = os.path.dirname(lock_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    try:
        import fcntl
    except ImportError:
        fcntl = None

    with open(lock_path, "a+") as handle:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _read_json(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception:
        # 解析不了就留现场，避免把坏文件当成空文件覆盖掉
        try:
            if os.path.isfile(path):
                os.replace(path, f"{path}.corrupt.{int(time.time())}")
        except OSError:
            pass
        return {}


def _atomic_write(path: str, data: dict) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def merge_and_save(path: str, state: Optional[dict]) -> bool:
    """把浏览器里的最新登录态合并回文件。

    返回是否写入。state 里没有 cookies 时不动文件，避免把有效登录态清空。
    """
    if not path or not isinstance(state, dict):
        return False
    new_cookies = state.get("cookies")
    if not new_cookies:
        return False

    with _file_lock(path):
        original = _read_json(path)
        merged = dict(original)
        merged["cookies"] = merge_cookies(original.get("cookies"), new_cookies)
        # 标准 Playwright 快照才带 origins；增强快照的 localStorage 存在 storage.local，不在这里
        if "origins" in merged and state.get("origins") is not None:
            merged["origins"] = state["origins"]
        _atomic_write(path, merged)
    return True


def read_expiry(path: str) -> Optional[int]:
    """返回登录票据的过期时间（秒级时间戳）；没有可用票据时返回 None。"""
    data = _read_json(path)
    cookies = {
        str(cookie.get("name")): cookie
        for cookie in data.get("cookies") or []
        if isinstance(cookie, dict)
    }
    for name in LOGIN_COOKIE_NAMES:
        cookie = cookies.get(name)
        if not cookie:
            continue
        expires = cookie.get("expires")
        if isinstance(expires, (int, float)) and expires > 0:
            return int(expires)
    return None
