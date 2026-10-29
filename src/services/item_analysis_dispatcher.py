"""
商品分析分发器
将卖家资料采集、图片下载、AI 分析和结果保存移出主抓取链路。
"""
import asyncio
import copy
import os
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

from src.keyword_rule_engine import build_search_text, evaluate_keyword_rules
from src.services import model_check_service


SellerLoader = Callable[[str], Awaitable[dict]]
ImageDownloader = Callable[[str, list[str], str], Awaitable[list[str]]]
AIAnalyzer = Callable[[dict, list[str], str], Awaitable[Optional[dict]]]
Notifier = Callable[[dict, str], Awaitable[None]]
Saver = Callable[[dict, str], Awaitable[bool]]


@dataclass(frozen=True)
class ItemAnalysisJob:
    keyword: str
    task_name: str
    decision_mode: str
    analyze_images: bool
    prompt_text: str
    keyword_rules: tuple[str, ...]
    final_record: dict
    seller_id: Optional[str]
    zhima_credit_text: Optional[str]
    registration_duration_text: str
    # 复查触发的重新分析：保留原卖家信息，落库走上更新而不是插入
    update_existing: bool = False
    # 入库前先做一次型号核对，不是任务要的型号就不落结果表
    model_check: bool = False


class ItemAnalysisDispatcher:
    """用受控并发处理商品分析和落盘。"""

    def __init__(
        self,
        *,
        concurrency: int,
        skip_ai_analysis: bool,
        seller_loader: SellerLoader,
        image_downloader: ImageDownloader,
        ai_analyzer: AIAnalyzer,
        notifier: Notifier,
        saver: Saver,
        updater: Optional[Saver] = None,
    ) -> None:
        self._semaphore = asyncio.Semaphore(max(1, concurrency))
        self._skip_ai_analysis = skip_ai_analysis
        self._seller_loader = seller_loader
        self._image_downloader = image_downloader
        self._ai_analyzer = ai_analyzer
        self._notifier = notifier
        self._saver = saver
        self._updater = updater or saver
        self._tasks: set[asyncio.Task] = set()
        self.completed_count = 0

    def submit(self, job: ItemAnalysisJob) -> None:
        task = asyncio.create_task(self._process_with_limit(job))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def join(self) -> None:
        while self._tasks:
            await asyncio.gather(*tuple(self._tasks))

    async def _process_with_limit(self, job: ItemAnalysisJob) -> None:
        async with self._semaphore:
            await self._process_job(job)

    async def _process_job(self, job: ItemAnalysisJob) -> None:
        record = copy.deepcopy(job.final_record)
        item_data = record.get("item_info", {}) or {}

        # 型号核对放在最前面：不是任务要的型号，卖家信息、AI 分析、图片都不做
        if job.model_check and not job.update_existing:
            verdict = await self._check_model(job, item_data)
            if verdict is not None and verdict.get("matched") is False:
                print(
                    f"   [型号] 商品 {item_data.get('item_id')} 不是「{job.keyword}」，跳过入库："
                    f"{verdict.get('reason')}"
                )
                return

        if job.update_existing:
            record.setdefault("seller_info", {})
        else:
            record["seller_info"] = await self._load_seller_info(job)

        # 只有需要喂给模型时才先拉图，分析完不推荐就删掉
        needs_analysis_images = job.analyze_images and job.decision_mode != "keyword"
        analysis_images = (
            await self._download_images(job, record) if needs_analysis_images else []
        )
        record["ai_analysis"] = await self._build_analysis_result(
            job, record, analysis_images
        )

        # 图片只为留下来的商品保留：推荐了才下载，没推荐就把分析用的临时图删掉
        recommended = bool((record["ai_analysis"] or {}).get("is_recommended"))
        if recommended and not analysis_images:
            await self._download_images(job, record)
        elif not recommended and analysis_images:
            self._cleanup_images(analysis_images)

        writer = self._updater if job.update_existing else self._saver
        if await writer(record, job.keyword):
            self.completed_count += 1
        await self._notify_if_recommended(item_data, record["ai_analysis"])

    async def _check_model(self, job: ItemAnalysisJob, item_data: dict) -> Optional[dict]:
        """返回 None 表示判断不了，调用方放行。"""
        item_id = str(item_data.get("item_id") or "").strip()
        if not item_id:
            return None
        try:
            return await model_check_service.check_item(
                item_id=item_id,
                task_name=job.task_name,
                target=job.keyword,
                title=str(item_data.get("title") or ""),
                description=str(item_data.get("description") or ""),
            )
        except Exception as exc:  # noqa: BLE001
            print(f"   [型号] 判断出错，放行: {exc}")
            return None

    async def _load_seller_info(self, job: ItemAnalysisJob) -> dict:
        seller_info = {}
        if job.seller_id:
            try:
                seller_info = await self._seller_loader(job.seller_id)
            except Exception as exc:
                print(f"   [卖家] 采集卖家 {job.seller_id} 信息失败: {exc}")
        merged = copy.deepcopy(seller_info or {})
        merged["seller_zhima_credit"] = job.zhima_credit_text
        merged["seller_registered_years"] = job.registration_duration_text
        return merged

    async def _build_analysis_result(
        self,
        job: ItemAnalysisJob,
        record: dict,
        image_paths: list[str],
    ) -> dict:
        if job.decision_mode == "keyword":
            return self._build_keyword_result(job, record)
        if self._skip_ai_analysis:
            return self._build_skip_ai_result()
        return await self._run_ai_analysis(job, record, image_paths)

    def _build_keyword_result(self, job: ItemAnalysisJob, record: dict) -> dict:
        search_text = build_search_text(record)
        return evaluate_keyword_rules(list(job.keyword_rules), search_text)

    def _build_skip_ai_result(self) -> dict:
        return {
            "analysis_source": "ai",
            "is_recommended": True,
            "reason": "商品已跳过AI分析，直接通知",
            "keyword_hit_count": 0,
        }

    def _build_ai_error_result(self, reason: str, *, error: str = "") -> dict:
        payload = {
            "analysis_source": "ai",
            "is_recommended": False,
            "reason": reason,
            "keyword_hit_count": 0,
        }
        if error:
            payload["error"] = error
        return payload

    async def _run_ai_analysis(
        self,
        job: ItemAnalysisJob,
        record: dict,
        image_paths: list[str],
    ) -> dict:
        try:
            if not job.prompt_text:
                return self._build_ai_error_result("任务未配置AI prompt，跳过分析。")
            ai_result = await self._ai_analyzer(record, image_paths, job.prompt_text)
            if not ai_result:
                return self._build_ai_error_result(
                    "AI analysis returned None after retries.",
                    error="AI analysis returned None after retries.",
                )
            ai_result.setdefault("analysis_source", "ai")
            ai_result.setdefault("keyword_hit_count", 0)
            return ai_result
        except Exception as exc:
            return self._build_ai_error_result(
                f"AI分析异常: {exc}",
                error=str(exc),
            )

    async def _download_images(self, job: ItemAnalysisJob, record: dict) -> list[str]:
        item_data = record.get("item_info", {}) or {}
        image_urls = item_data.get("images", [])
        if not image_urls:
            return []
        try:
            return await self._image_downloader(
                item_data["item_id"],
                image_urls,
                job.task_name,
            )
        except Exception as exc:
            print(f"   [图片] 下载商品图片失败: {exc}")
            return []

    def _cleanup_images(self, image_paths: list[str]) -> None:
        for img_path in image_paths:
            try:
                if os.path.exists(img_path):
                    os.remove(img_path)
            except Exception as exc:
                print(f"   [图片] 删除图片文件时出错: {exc}")

    async def _notify_if_recommended(self, item_data: dict, analysis_result: dict) -> None:
        if not analysis_result.get("is_recommended"):
            return
        try:
            await self._notifier(item_data, analysis_result.get("reason", "无"))
        except Exception as exc:
            print(f"   [通知] 发送推荐通知失败: {exc}")
