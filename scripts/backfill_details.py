#!/usr/bin/env python
"""回填商品详情、重新计算 AI 推荐、清理失效商品。

分三个阶段（状态记录在 data/backfill_state.json，可断点续跑）：

    python scripts/backfill_details.py fetch    [--limit N] [--state state/222.json] [--force]
    python scripts/backfill_details.py analyze  [--limit N] [--workers 3] [--task iPhone]
    python scripts/backfill_details.py prune
    python scripts/backfill_details.py all

fetch:   逐条打开商品详情页，抓 mtop 详情接口，把 商品描述/浏览量/想要人数/
         商品状态/商品已售数/商品收藏数 写回 result_items.raw_json；
         itemStatusStr != 在线 的判定为失效，接口无响应的标记为 uncertain（不删）。
analyze: 重新下载图片并调用 AI，用 task 的 base+criteria prompt 重新生成 ai_analysis，
         同步更新 is_recommended / analysis_source。
prune:   删除失效记录。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from playwright.async_api import async_playwright  # noqa: E402

DB_PATH = os.getenv("APP_DATABASE_FILE", "data/app.sqlite3")
STATE_PATH = "data/backfill_state.json"
DETAIL_PATTERN = "mtop.taobao.idle.pc.detail"
ONLINE_STATUS = "在线"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


# ---------------------------------------------------------------- helpers

def load_state() -> dict:
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    return {"fetched": {}, "dead": {}, "uncertain": {}, "analyzed": {}, "failed_analyze": []}


def save_state(state: dict) -> None:
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_PATH)


def db_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def fetch_rows() -> list[sqlite3.Row]:
    with db_conn() as conn:
        return conn.execute(
            "SELECT id, item_id, link, title, raw_json FROM result_items ORDER BY id ASC"
        ).fetchall()


def state_file_for_browser(cli_state: str | None) -> str:
    """登录态优先级：命令行 --state > BACKFILL_STATE_FILE > 账号池第一个 > 根登录态。"""
    candidate = cli_state or os.getenv("BACKFILL_STATE_FILE")
    if not candidate:
        state_dir = os.getenv("ACCOUNT_STATE_DIR", "state")
        if os.path.isdir(state_dir):
            files = sorted(f for f in os.listdir(state_dir) if f.endswith(".json"))
            if files:
                candidate = os.path.join(state_dir, files[0])
    candidate = candidate or "xianyu_state.json"
    if not os.path.exists(candidate):
        raise SystemExit(f"登录态文件不存在: {candidate}")
    return candidate


async def capture_detail(page, url: str, timeout_ms: int = 25000) -> dict | None:
    captured: dict = {}

    async def on_response(response):
        if DETAIL_PATTERN in response.url and not captured:
            try:
                captured["json"] = await response.json()
            except Exception as exc:  # noqa: BLE001
                captured["err"] = str(exc)

    page.on("response", on_response)
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        for _ in range(int(timeout_ms / 500)):
            if captured:
                break
            await asyncio.sleep(0.5)
    except Exception as exc:  # noqa: BLE001
        captured.setdefault("err", str(exc))
    finally:
        page.remove_listener("response", on_response)
    return captured.get("json")


def parse_detail(detail: dict) -> dict:
    ret = detail.get("ret") or []
    ret_text = " ".join(str(x) for x in ret)
    data = detail.get("data") or {}
    item_do = data.get("itemDO") or {}
    seller_do = data.get("sellerDO") or {}

    not_found = any(k in ret_text for k in ("ITEM_NOT_FOUND", "ITEM_DELETED", "NOT_FOUND", "INVALID"))
    fields = {
        "商品状态": str(item_do.get("itemStatusStr") or "").strip(),
        "商品描述": str(item_do.get("desc") or "").strip(),
        "浏览量": item_do.get("browseCnt"),
        "“想要”人数": item_do.get("wantCnt"),
        "商品已售数": item_do.get("soldCnt"),
        "商品收藏数": item_do.get("collectCnt"),
        "卖家累计已售数": seller_do.get("hasSoldNumInteger"),
    }
    return {"ok": (not not_found) and bool(item_do), "not_found": not_found, "fields": fields}


# ---------------------------------------------------------------- fetch

async def run_fetch(args: argparse.Namespace) -> None:
    from playwright.async_api import async_playwright as pw

    state = load_state()
    state.setdefault("fetched", {})
    rows = fetch_rows()
    if getattr(args, "force", False):
        state["fetched"] = {}
        state["dead"] = {}
        state["uncertain"] = {}
    targets = [r for r in rows if str(r["item_id"]) not in state["fetched"]]
    if args.limit:
        targets = targets[: args.limit]
    print(f"[fetch] 待抓取 {len(targets)} 条（共 {len(rows)} 条记录）")
    if not targets:
        return

    state_file = state_file_for_browser(args.state)
    async with pw() as p:
        browser = await p.chromium.launch(
            headless=True,
            channel="chromium",
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        snap = json.load(open(state_file, encoding="utf-8"))
        storage = {"cookies": snap["cookies"]} if isinstance(snap, dict) and "cookies" in snap else state_file
        context = await browser.new_context(storage_state=storage, user_agent=DEFAULT_USER_AGENT)
        page = await context.new_page()

        for index, row in enumerate(targets, start=1):
            item_id = str(row["item_id"])
            canonical = f"https://www.goofish.com/item?id={item_id}"
            detail = await capture_detail(page, canonical)
            if not detail:
                await asyncio.sleep(random.uniform(2, 4))
                detail = await capture_detail(page, row["link"] or canonical)

            if not detail:
                state["uncertain"][item_id] = "详情接口两次均未响应"
                state["fetched"][item_id] = {"result": "uncertain"}
                print(f"[{index}/{len(targets)}] {item_id} 详情未响应 -> uncertain（保留）")
            else:
                parsed = parse_detail(detail)
                if not parsed["ok"]:
                    reason = "详情接口返回不存在/已删除" if parsed["not_found"] else "itemDO 为空"
                    state["dead"][item_id] = reason
                    state["fetched"][item_id] = {"result": "dead", "reason": reason}
                    print(f"[{index}/{len(targets)}] {item_id} 判定失效: {reason}")
                else:
                    fields = parsed["fields"]
                    update_row(row, fields)
                    state["dead"].pop(item_id, None)
                    state["uncertain"].pop(item_id, None)
                    state["fetched"][item_id] = {"result": "ok", "status": fields["商品状态"]}
                    if fields["商品状态"] != ONLINE_STATUS:
                        state["dead"][item_id] = f"商品状态={fields['商品状态']}"
                        print(f"[{index}/{len(targets)}] {item_id} 商品状态 {fields['商品状态']} -> 待删除")
                    else:
                        print(
                            f"[{index}/{len(targets)}] {item_id} 已回填 "
                            f"(描述 {len(fields['商品描述'])} 字, 浏览 {fields['浏览量']}, 想要 {fields['“想要”人数']})"
                        )
            save_state(state)
            await asyncio.sleep(random.uniform(2, 4))

        await browser.close()

    print(f"[fetch] 完成。失效 {len(state['dead'])} 条，不确定 {len(state['uncertain'])} 条")


def update_row(row: sqlite3.Row, fields: dict) -> None:
    record = json.loads(row["raw_json"])
    item = record.setdefault("商品信息", {})
    for key, value in fields.items():
        if value is None or value == "":
            continue
        if key == "商品描述":
            item[key] = value
        elif key in ("浏览量", "“想要”人数", "商品已售数", "商品收藏数", "卖家累计已售数"):
            item[key] = value
        else:
            item[key] = value
    raw = json.dumps(record, ensure_ascii=False)
    with db_conn() as conn:
        conn.execute(
            "UPDATE result_items SET raw_json = ?, publish_time = COALESCE(?, publish_time) WHERE id = ?",
            (raw, item.get("发布时间"), row["id"]),
        )
        conn.commit()


# ---------------------------------------------------------------- analyze

def build_prompt(task_name: str | None) -> tuple[str, str]:
    with db_conn() as conn:
        if task_name:
            row = conn.execute(
                "SELECT * FROM tasks WHERE task_name = ?", (task_name,)
            ).fetchone()
        else:
            row = conn.execute("SELECT * FROM tasks WHERE enabled = 1 ORDER BY id LIMIT 1").fetchone()
    if not row:
        raise SystemExit("未找到可用任务（检查 --task 或任务是否启用）")
    base_path = REPO_ROOT / row["ai_prompt_base_file"]
    criteria_path = REPO_ROOT / row["ai_prompt_criteria_file"]
    base = base_path.read_text(encoding="utf-8")
    criteria = criteria_path.read_text(encoding="utf-8")
    prompt = base.replace("{{CRITERIA_SECTION}}", criteria)
    if len(prompt) < 100 or "{{CRITERIA_SECTION}}" in prompt:
        raise SystemExit(f"prompt 组装异常（长度 {len(prompt)}）")
    return str(row["task_name"]), prompt


async def run_analyze(args: argparse.Namespace) -> None:
    """命令行入口：复用 reanalyze_service 的实现，避免两份逻辑。"""
    from src.services.reanalyze_service import (
        SCOPE_PENDING,
        ReanalyzeBusyError,
        run_analyze as _run_analyze,
    )

    scope = getattr(args, "scope", SCOPE_PENDING)
    try:
        status = await _run_analyze(
            scope=scope,
            limit=getattr(args, "limit", 0) or None,
            workers=getattr(args, "workers", 3),
            only_ids=getattr(args, "item_ids", None),
        )
    except ReanalyzeBusyError as exc:
        print(f"[analyze] {exc}")
        return
    print(f"[analyze] {status.get('message')}")


# ---------------------------------------------------------------- prune

def run_prune(_args: argparse.Namespace) -> None:
    state = load_state()
    dead = dict(state.get("dead", {}))
    if not dead:
        print("[prune] 没有判定为失效的记录")
        return
    with db_conn() as conn:
        for item_id, reason in dead.items():
            row = conn.execute(
                "SELECT id, title FROM result_items WHERE item_id = ?", (item_id,)
            ).fetchone()
            if not row:
                continue
            conn.execute("DELETE FROM result_items WHERE id = ?", (row["id"],))
            print(f"[prune] 已删除 {item_id} ({reason}): {str(row['title'])[:40]}")
        conn.commit()
    state["pruned"] = state.get("pruned", {})
    state["pruned"].update(dead)
    state["dead"] = {}
    save_state(state)
    with db_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM result_items").fetchone()[0]
    print(f"[prune] 完成，剩余记录 {total} 条")


# ---------------------------------------------------------------- main

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_fetch = sub.add_parser("fetch")
    p_fetch.add_argument("--state", default=None, help="登录态文件，默认 state/222.json")
    p_fetch.add_argument("--limit", type=int, default=0)
    p_fetch.add_argument("--force", action="store_true", help="忽略已有状态重新抓取")

    p_analyze = sub.add_parser("analyze")
    p_analyze.add_argument("--limit", type=int, default=0)
    p_analyze.add_argument("--workers", type=int, default=3)
    p_analyze.add_argument("--task", default=None)
    p_analyze.add_argument("--scope", default="pending", choices=["pending", "all", "selected"])
    p_analyze.add_argument("--item-ids", nargs="*", dest="item_ids", default=None)

    sub.add_parser("prune")

    p_clean = sub.add_parser("clean-images")
    p_clean.add_argument("--task", default=None, help="只清理指定任务的图片目录")

    p_all = sub.add_parser("all")
    p_all.add_argument("--state", default=None)
    p_all.add_argument("--limit", type=int, default=0)
    p_all.add_argument("--workers", type=int, default=3)
    p_all.add_argument("--task", default=None)
    p_all.add_argument("--scope", default="pending", choices=["pending", "all", "selected"])
    p_all.add_argument("--item-ids", nargs="*", dest="item_ids", default=None)

    args = parser.parse_args()

    if args.command == "fetch":
        asyncio.run(run_fetch(args))
    elif args.command == "analyze":
        asyncio.run(run_analyze(args))
    elif args.command == "prune":
        run_prune(args)
    elif args.command == "clean-images":
        from src.services.image_cache_service import clear, get_stats

        if args.task:
            print(json.dumps(clear(only_task=args.task), ensure_ascii=False, indent=2))
        else:
            stats = get_stats()
            print(f"图片缓存：{stats['total_size']} / {stats['file_count']} 张 / {stats['task_count']} 个任务目录")
            for d in stats["dirs"]:
                print(f"  - {d['name']}: {d['size']} ({d['files']} 张)")
            result = clear()
            print(f"已清理 {len(result['removed'])} 个目录，释放 {result['freed_size']}，剩余 {result['remaining_size']}")
            if result["errors"]:
                print("错误：", result["errors"])
    elif args.command == "all":
        asyncio.run(run_fetch(args))
        asyncio.run(run_analyze(args))
        run_prune(args)


if __name__ == "__main__":
    main()
