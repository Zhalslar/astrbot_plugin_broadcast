import asyncio

from astrbot.api.event import filter
from astrbot.api.star import Context, Star
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.message.components import Plain, Reply
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)

from .config import PluginConfig
from .utils import broadcast, get_group_by_index, get_ids, get_reply_id


class BroadcastPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.cfg = PluginConfig(config)
        self._broadcast_task = None

    @filter.command("开启广播")
    async def enable_broadcast(
        self, event: AiocqhttpMessageEvent, index: int | None = None
    ):
        gid, name = await get_group_by_index(event, index)
        if not gid:
            return

        if self.cfg.enable_target(gid):
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

        if self.cfg.disable_target(gid):
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
            gid = str(g["group_id"])
            info = f"{idx}. {g['group_name']}"
            if self.cfg.is_disabled(gid):
                disabled.append(info)
            else:
                enabled.append(info)

        msg = "【开启广播】\n" + "\n".join(enabled)
        if len(disabled) > 0:
            msg += "\n\n【关闭广播】\n" + "\n".join(disabled)

        yield event.plain_result(msg)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("广播")
    async def cmd_broadcast(self, event: AiocqhttpMessageEvent, scope_str: str = ""):
        """(引用消息)广播 <群聊|私聊|全部>"""
        reply_id = get_reply_id(event)
        if not reply_id:
            yield event.plain_result("需要引用要广播的消息")
            return

        if self._broadcast_task and not self._broadcast_task.done():
            yield event.plain_result("已有广播正在进行中")
            return

        is_group = True if scope_str in ("好友", "私聊", "f", "friend") else True
        scope_str = "群聊" if is_group else "私聊"

        ids = await get_ids(client=event.bot, is_group=is_group)

        if self.cfg.skip_source:
            source_id = event.get_group_id() if is_group else event.get_sender_id()
            if source_id in ids:
                ids.remove(source_id)

        task = asyncio.create_task(
            broadcast(
                client=event.bot,
                is_group=is_group,
                message_id=reply_id,
                ids=ids,
                delay=self.cfg.get_broadcast_delay(),
            ),
            name="broadcast_task",
        )
        self._broadcast_task = task

        chain = [
            Reply(id=reply_id),
            Plain(f"正在向{len(ids)}个{scope_str}广播此消息..."),
        ]
        yield event.chain_result(chain)

        # 后台等待结果并汇报
        async def _wait_result():
            try:
                success_ids = await task
            except asyncio.CancelledError:
                return
            finally:
                self._broadcast_task = None

            msg = f"已向{len(success_ids)}个{scope_str}广播此消息"
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
