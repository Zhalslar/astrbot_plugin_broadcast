import asyncio

from astrbot.api.event import filter
from astrbot.api.star import Context, Star
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.message.components import Plain, Reply
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)

from .config import PluginConfig
from .utils import (
    broadcast,
    get_friend_by_index,
    get_group_by_index,
    get_ids,
    get_reply_id,
    parse_scope_and_index,
    parse_scope_name,
)


class BroadcastPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.cfg = PluginConfig(config)
        self._broadcast_task = None

    @filter.command("开启广播")
    async def enable_broadcast(
        self,
        event: AiocqhttpMessageEvent,
        arg1: str = "",
        arg2: str = "",
    ):
        """开启广播 <留空|群聊|私聊> <序号>"""
        is_group, index, err = parse_scope_and_index(arg1, arg2)
        if err:
            yield event.plain_result(err)
            return

        if is_group:
            target_id, name = await get_group_by_index(event, index)
        else:
            target_id, name = await get_friend_by_index(event, index)
        if not target_id:
            return

        self.cfg.enable_target(target_id, is_group=is_group)
        scope_name = "群聊" if is_group else "私聊"
        yield event.plain_result(f"【{name}】已开启{scope_name}广播")

    @filter.command("关闭广播")
    async def disable_broadcast(
        self,
        event: AiocqhttpMessageEvent,
        arg1: str = "",
        arg2: str = "",
    ):
        """关闭广播 <留空|群聊|私聊> <序号>"""
        is_group, index, err = parse_scope_and_index(arg1, arg2)
        scope_text = "群聊" if is_group else "好友"

        if err:
            yield event.plain_result(err)
            return

        if is_group:
            target_id, name = await get_group_by_index(event, index)
        else:
            target_id, name = await get_friend_by_index(event, index)
        if not target_id:
            return

        self.cfg.disable_target(target_id, is_group=is_group)
        yield event.plain_result(f"已关闭【{name}】的{scope_text}广播")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("广播列表")
    async def broadcast_list(self, event: AiocqhttpMessageEvent, scope_name: str = ""):
        """广播列表 <留空|群聊|私聊>"""
        is_group = bool(parse_scope_name(scope_name))
        scope_text = "群聊" if is_group else "好友"

        enabled = []
        disabled = []

        if is_group:
            groups = await event.bot.get_group_list()
            groups.sort(key=lambda x: x["group_id"])
            for idx, g in enumerate(groups, 1):
                target_id = str(g["group_id"])
                info = f"{idx}. {g['group_name']} ({target_id})"
                if self.cfg.is_disabled(target_id, is_group=True):
                    disabled.append(info)
                else:
                    enabled.append(info)
        else:
            friends = await event.bot.get_friend_list()
            friends.sort(key=lambda x: x["user_id"])
            for idx, f in enumerate(friends, 1):
                target_id = str(f["user_id"])
                name = f.get("remark") or f.get("nickname") or target_id
                info = f"{idx}. {name} ({target_id})"
                if self.cfg.is_disabled(target_id, is_group=False):
                    disabled.append(info)
                else:
                    enabled.append(info)

        msg = f"【{scope_text}开启广播】\n" + "\n".join(enabled)
        if len(disabled) > 0:
            msg += f"\n\n【{scope_text}关闭广播】\n" + "\n".join(disabled)

        yield event.plain_result(msg)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("广播")
    async def cmd_broadcast(self, event: AiocqhttpMessageEvent, scope_name: str = ""):
        """(引用消息)广播 <群聊|私聊|全部>"""
        reply_id = get_reply_id(event)
        if not reply_id:
            yield event.plain_result("需要引用要广播的消息")
            return

        if self._broadcast_task and not self._broadcast_task.done():
            yield event.plain_result("已有广播正在进行中")
            return

        is_group = bool(parse_scope_name(scope_name))
        scope_text = "群聊" if is_group else "好友"

        ids = await get_ids(client=event.bot, is_group=is_group)

        if self.cfg.skip_source:
            source_id = str(event.get_group_id() if is_group else event.get_sender_id())
            if source_id in ids:
                ids.remove(source_id)

        filter_ids = self.cfg.filter_broadcastable(ids, is_group=is_group)

        task = asyncio.create_task(
            broadcast(
                client=event.bot,
                is_group=is_group,
                message_id=reply_id,
                ids=filter_ids,
                delay=self.cfg.get_broadcast_delay(),
            ),
            name="broadcast_task",
        )
        self._broadcast_task = task

        chain = [
            Reply(id=reply_id),
            Plain(f"正在向{len(filter_ids)}个{scope_text}广播此消息..."),
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

            msg = f"已向{len(success_ids)}个{scope_text}广播此消息"
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
