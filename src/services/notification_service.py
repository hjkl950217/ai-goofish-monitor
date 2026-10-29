"""
通知服务
统一管理所有通知渠道
"""
import asyncio
from typing import Dict, List

from src.infrastructure.external.notification_clients.base import NotificationClient
from src.infrastructure.external.notification_clients.factory import build_notification_clients
from src.services.notification_config_service import (
    disabled_notification_channels,
    load_notification_settings,
)
from src.services.notification_history import record
from src.infrastructure.config.settings import NotificationSettings


class NotificationService:
    """通知服务"""

    def __init__(self, clients: List[NotificationClient]):
        self.clients = [client for client in clients if client.is_enabled()]

    async def send_notification(
        self,
        product_data: Dict,
        reason: str,
        *,
        is_test: bool = False,
    ) -> Dict[str, Dict[str, str | bool]]:
        """
        发送通知到所有启用的渠道

        Returns:
            各渠道发送结果，包含成功状态和消息
        """
        if not self.clients:
            return {}

        tasks = [
            self._send_with_result(client, product_data, reason, is_test=is_test)
            for client in self.clients
        ]
        results = await asyncio.gather(*tasks)
        return {result["channel"]: result for result in results}

    async def send_test_notification(self) -> Dict[str, Dict[str, str | bool]]:
        test_product = {
            "title": "[测试通知] 闲鱼智能监控",
            "price": "0",
            "link": "https://www.goofish.com/",
        }
        return await self.send_notification(
            test_product,
            "这是一条测试通知，用于验证推送渠道是否可用。",
            is_test=True,
        )

    async def _send_with_result(
        self,
        client: NotificationClient,
        product_data: Dict,
        reason: str,
        *,
        is_test: bool = False,
    ) -> Dict[str, str | bool]:
        try:
            await client.send(product_data, reason)
            result: Dict[str, str | bool] = {
                "channel": client.channel_key,
                "label": client.display_name,
                "success": True,
                "message": "发送成功",
            }
        except Exception as exc:
            result = {
                "channel": client.channel_key,
                "label": client.display_name,
                "success": False,
                "message": str(exc),
            }
        record(
            channel=client.channel_key,
            label=client.display_name,
            success=bool(result["success"]),
            message=str(result["message"]),
            title=str(product_data.get("title", "")),
            is_test=is_test,
        )
        return result


def build_notification_service(
    settings: NotificationSettings | None = None,
    *,
    respect_disabled: bool = True,
) -> NotificationService:
    """respect_disabled=False 用于「测试此渠道」：停用的渠道也要能测通。"""
    notification_settings = settings or load_notification_settings()
    clients = build_notification_clients(notification_settings)
    if respect_disabled:
        disabled = disabled_notification_channels()
        clients = [client for client in clients if client.channel_key not in disabled]
    return NotificationService(clients)
