import asyncio

from aiocqhttp import CQHttp

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

async def get_ids(client: CQHttp, is_group: bool) -> list[str]:
    if is_group:
        groups = await client.get_group_list()
        return [str(g["group_id"]) for g in groups]
    else:
        friends = await client.get_friend_list()
        return [str(f["user_id"]) for f in friends]

async def broadcast(
    client: CQHttp,
    *,
    is_group: bool,
    message_id: str | int,
    ids: list[str] | list[int],
    delay: float = 0.5,
):
    success_ids = []
    try:
        for tid in ids:
            await asyncio.sleep(delay)
            try:
                if is_group:
                    await client.forward_group_single_msg(
                        group_id=int(tid),
                        message_id=message_id,
                    )
                    success_ids.append(tid)
                else:
                    await client.forward_friend_single_msg(
                        user_id=int(tid),
                        message_id=message_id,
                    )
                    success_ids.append(tid)
            except asyncio.CancelledError:
                return success_ids
            except Exception as e:
                logger.warning(f"{tid} 广播失败: {e}")
        return success_ids
    except asyncio.CancelledError:
        logger.info("广播任务被取消")
        return success_ids

