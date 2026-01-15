import asyncio

from astrbot.api.event import filter
from astrbot.api.star import Context, Star
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.message.components import Plain, Reply
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)

from .core.service import BroadcastResult, BroadcastService
from .core.state import BroadcastGroupState
from .core.utils import get_group_by_index, get_reply_id


class BroadcastPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.cfg = config
        self.state = BroadcastGroupState(config)
        self._broadcast_task = None

    # ========================
    # 广播开关与列表
    # ========================

    @filter.command("开启广播")
    async def enable_broadcast(
        self, event: AiocqhttpMessageEvent, index: int | None = None
    ):
        gid, name = await get_group_by_index(event, index)
        if not gid:
            return

        if self.state.enable(gid):
            yield event.plain_result(f"【{name}】已开启广播")
        else:
            yield event.plain_result(f"【{name}】广播已开启")

    @filter.command("关闭广播")
    async def disable_broadcast(
        self, event: AiocqhttpMessageEvent, index: int | None = None
    ):
        gid, name = await get_group_by_index(event, index)
        if not gid:
            return

        if self.state.disable(gid):
            yield event.plain_result(f"【{name}】已关闭广播")
        else:
            yield event.plain_result(f"【{name}】广播已关闭")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("广播列表")
    async def broadcast_list(self, event: AiocqhttpMessageEvent):
        groups = await event.bot.get_group_list()
        groups.sort(key=lambda x: x["group_id"])

        enabled = []
        disabled = []

        for idx, g in enumerate(groups, 1):
            info = f"{idx}. {g['group_name']}"
            if self.state.is_disabled(str(g["group_id"])):
                disabled.append(info)
            else:
                enabled.append(info)

        msg = (
            "【开启广播】\n" + "\n".join(enabled) + "\n\n"
            "【关闭广播】\n" + "\n".join(disabled)
        ).strip()

        yield event.plain_result(msg)

    # ========================
    # 广播流程
    # ========================

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("广播")
    async def broadcast(self, event: AiocqhttpMessageEvent):
        """(引用消息)广播， 广播引用的消息"""
        reply_id = get_reply_id(event)
        if not reply_id:
            yield event.plain_result("需要引用要广播的消息")
            return

        # 防止重复广播
        if self._broadcast_task and not self._broadcast_task.done():
            yield event.plain_result("已有广播正在进行中")
            return

        try:
            service = BroadcastService(self.cfg, self.state, bot=event.bot)
            task = service.create_broadcast_task(reply_id)
        except RuntimeError as e:
            yield event.plain_result(str(e))
            return

        self._broadcast_task = task

        gids = await service.get_broadcastable_gids()
        chain = [
            Reply(id=reply_id),
            Plain(f"正在向{len(gids)}个群广播此消息..."),
        ]
        yield event.chain_result(chain)

        # 后台等待结果并汇报
        async def _wait_result():
            try:
                result: BroadcastResult = await task
            except asyncio.CancelledError:
                return
            finally:
                self._broadcast_task = None

            msg = (
                f"广播完成\n"
                f"成功：{result.success_count}个群\n"
                f"失败：{result.failed_count}个群\n"
                f"{'（中途取消）' if result.cancelled else ''}"
            ).strip()

            await event.send(event.plain_result(msg))

        asyncio.create_task(_wait_result())

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("取消广播")
    async def cancel_broadcast(self, event: AiocqhttpMessageEvent):
        """取消当前正在进行的广播任务"""
        task = self._broadcast_task

        if not task or task.done():
            yield event.plain_result("当前没有进行中的广播")
            return

        task.cancel()
        yield event.plain_result("已请求取消广播")
