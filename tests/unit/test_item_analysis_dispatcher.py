import asyncio

from src.services.item_analysis_dispatcher import (
    ItemAnalysisDispatcher,
    ItemAnalysisJob,
)


def test_item_analysis_dispatcher_uses_bounded_concurrency():
    active_ai_calls = 0
    max_active_ai_calls = 0
    saved_records = []
    notifications = []

    async def seller_loader(user_id: str):
        await asyncio.sleep(0.005)
        return {"卖家ID": user_id}

    async def image_downloader(product_id: str, image_urls: list[str], task_name: str):
        return []

    async def ai_analyzer(record: dict, image_paths: list[str], prompt_text: str):
        nonlocal active_ai_calls, max_active_ai_calls
        active_ai_calls += 1
        max_active_ai_calls = max(max_active_ai_calls, active_ai_calls)
        await asyncio.sleep(0.03)
        active_ai_calls -= 1
        return {
            "analysis_source": "ai",
            "is_recommended": True,
            "reason": f"推荐 {record['item_info']['item_id']}",
            "keyword_hit_count": 0,
        }

    async def notifier(item_data: dict, reason: str):
        notifications.append((item_data["item_id"], reason))

    async def saver(record: dict, keyword: str):
        saved_records.append((keyword, record))
        return True

    async def run():
        dispatcher = ItemAnalysisDispatcher(
            concurrency=2,
            skip_ai_analysis=False,
            seller_loader=seller_loader,
            image_downloader=image_downloader,
            ai_analyzer=ai_analyzer,
            notifier=notifier,
            saver=saver,
        )
        for index in range(3):
            dispatcher.submit(
                ItemAnalysisJob(
                    keyword="demo",
                    task_name="Demo",
                    decision_mode="ai",
                    analyze_images=False,
                    prompt_text="prompt",
                    keyword_rules=(),
                    final_record={
                        "item_info": {"item_id": str(index), "images": []},
                        "seller_info": {},
                    },
                    seller_id=f"seller-{index}",
                    zhima_credit_text="优秀",
                    registration_duration_text="来闲鱼1年",
                )
            )
        await dispatcher.join()
        return dispatcher

    dispatcher = asyncio.run(run())
    assert dispatcher.completed_count == 3
    assert len(saved_records) == 3
    assert len(notifications) == 3
    assert max_active_ai_calls == 2
    assert saved_records[0][1]["seller_info"]["卖家ID"].startswith("seller-")


def test_images_downloaded_only_for_recommended_items():
    """图片只为留下来的商品下载：不推荐的连图片请求都不发。"""
    downloaded = []

    async def seller_loader(user_id: str):
        return {}

    async def image_downloader(product_id: str, image_urls: list[str], task_name: str):
        downloaded.append(product_id)
        return []

    async def ai_analyzer(record: dict, image_paths: list[str], prompt_text: str):
        product_id = record["item_info"]["item_id"]
        return {
            "analysis_source": "ai",
            "is_recommended": product_id == "keep",
            "reason": "test",
            "keyword_hit_count": 0,
        }

    async def notifier(item_data: dict, reason: str):
        return None

    async def saver(record: dict, keyword: str):
        return True

    async def run():
        dispatcher = ItemAnalysisDispatcher(
            concurrency=1,
            skip_ai_analysis=False,
            seller_loader=seller_loader,
            image_downloader=image_downloader,
            ai_analyzer=ai_analyzer,
            notifier=notifier,
            saver=saver,
        )
        for product_id in ("keep", "drop"):
            dispatcher.submit(
                ItemAnalysisJob(
                    keyword="demo",
                    task_name="Demo",
                    decision_mode="ai",
                    analyze_images=False,
                    prompt_text="prompt",
                    keyword_rules=(),
                    final_record={
                        "item_info": {
                            "item_id": product_id,
                            "images": ["http://img/1.jpg"],
                        },
                        "seller_info": {},
                    },
                    seller_id=None,
                    zhima_credit_text=None,
                    registration_duration_text="",
                )
            )
        await dispatcher.join()

    asyncio.run(run())
    assert downloaded == ["keep"]


def test_item_analysis_dispatcher_supports_keyword_mode_without_ai():
    saved_records = []

    async def seller_loader(user_id: str):
        return {"卖家标签": "个人闲置"}

    async def image_downloader(product_id: str, image_urls: list[str], task_name: str):
        raise AssertionError("关键词模式不应下载图片")

    async def ai_analyzer(record: dict, image_paths: list[str], prompt_text: str):
        raise AssertionError("关键词模式不应调用 AI")

    async def notifier(item_data: dict, reason: str):
        return None

    async def saver(record: dict, keyword: str):
        saved_records.append(record)
        return True

    async def run():
        dispatcher = ItemAnalysisDispatcher(
            concurrency=1,
            skip_ai_analysis=False,
            seller_loader=seller_loader,
            image_downloader=image_downloader,
            ai_analyzer=ai_analyzer,
            notifier=notifier,
            saver=saver,
        )
        dispatcher.submit(
            ItemAnalysisJob(
                keyword="demo",
                task_name="Demo",
                decision_mode="keyword",
                analyze_images=False,
                prompt_text="",
                keyword_rules=("个人闲置",),
                final_record={
                    "item_info": {"item_id": "1", "title": "演示商品"},
                    "seller_info": {},
                },
                seller_id="seller-1",
                zhima_credit_text="优秀",
                registration_duration_text="来闲鱼1年",
            )
        )
        await dispatcher.join()

    asyncio.run(run())
    assert saved_records[0]["ai_analysis"]["analysis_source"] == "keyword"
    assert saved_records[0]["ai_analysis"]["is_recommended"] is True


def test_dispatcher_skips_mismatched_model_before_any_other_work(monkeypatch):
    saved_records = []
    seller_calls = []

    async def fake_check(**kwargs):
        return {"matched": False, "reason": "实际是 M1 85", "source": "ai"}

    monkeypatch.setattr(
        "src.services.item_analysis_dispatcher.model_check_service.check_item",
        fake_check,
    )

    async def seller_loader(user_id: str):
        seller_calls.append(user_id)
        return {}

    async def image_downloader(product_id: str, image_urls: list[str], task_name: str):
        raise AssertionError("型号不符不应下载图片")

    async def ai_analyzer(record: dict, image_paths: list[str], prompt_text: str):
        raise AssertionError("型号不符不应调用 AI")

    async def notifier(item_data: dict, reason: str):
        raise AssertionError("型号不符不应发通知")

    async def saver(record: dict, keyword: str):
        saved_records.append(record)
        return True

    async def run():
        dispatcher = ItemAnalysisDispatcher(
            concurrency=1,
            skip_ai_analysis=False,
            seller_loader=seller_loader,
            image_downloader=image_downloader,
            ai_analyzer=ai_analyzer,
            notifier=notifier,
            saver=saver,
        )
        dispatcher.submit(
            ItemAnalysisJob(
                keyword="九号M1 100",
                task_name="九号捡漏-M1100",
                decision_mode="ai",
                analyze_images=False,
                prompt_text="prompt",
                keyword_rules=(),
                final_record={
                    "item_info": {"item_id": "1", "title": "九号M1 85 准新车"},
                    "seller_info": {},
                },
                seller_id="seller-1",
                zhima_credit_text=None,
                registration_duration_text="",
                model_check=True,
            )
        )
        await dispatcher.join()

    asyncio.run(run())
    assert saved_records == []
    assert seller_calls == []


def test_dispatcher_drops_items_whose_model_cannot_be_confirmed(monkeypatch):
    """判不出型号（matched=None）不再放行，直接不入库。"""
    saved_records = []

    async def fake_check(**kwargs):
        return {"matched": None, "reason": "标题未写型号", "source": "ai"}

    monkeypatch.setattr(
        "src.services.item_analysis_dispatcher.model_check_service.check_item",
        fake_check,
    )

    async def saver(record: dict, keyword: str):
        saved_records.append(record)
        return True

    async def run():
        dispatcher = ItemAnalysisDispatcher(
            concurrency=1,
            skip_ai_analysis=True,
            seller_loader=lambda user_id: {},
            image_downloader=lambda *args: [],
            ai_analyzer=lambda *args: {},
            notifier=lambda *args: None,
            saver=saver,
        )
        dispatcher.submit(
            ItemAnalysisJob(
                keyword="九号M1 100",
                task_name="九号捡漏-M1100",
                decision_mode="ai",
                analyze_images=False,
                prompt_text="prompt",
                keyword_rules=(),
                final_record={
                    "item_info": {"item_id": "1", "title": "标价就是总价带7230锂电池"},
                    "seller_info": {},
                },
                seller_id="seller-1",
                zhima_credit_text=None,
                registration_duration_text="",
                model_check=True,
            )
        )
        await dispatcher.join()

    asyncio.run(run())
    assert saved_records == []
