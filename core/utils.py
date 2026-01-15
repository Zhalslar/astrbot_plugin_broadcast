from astrbot.core import logger
from astrbot.core.message.components import Reply
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)


def get_reply_id(event: AiocqhttpMessageEvent) -> str | int | None:
    """获取被引用消息者的id"""
    for seg in event.get_messages():
        if isinstance(seg, Reply):
            return seg.id


async def get_group_by_index(
    event: AiocqhttpMessageEvent, index: int | None
) -> tuple[str | None, str | None]:
    try:
        groups = await event.bot.get_group_list()
        groups.sort(key=lambda x: x["group_id"])

        if index and event.is_admin():
            group = groups[index - 1]
        else:
            gid = event.get_group_id()
            group = next(g for g in groups if str(g["group_id"]) == str(gid))

        return str(group["group_id"]), group["group_name"]
    except Exception as e:
        logger.error(f"获取群信息失败: {e}")
        return None, None
