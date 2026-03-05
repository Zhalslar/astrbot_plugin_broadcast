import asyncio

from aiocqhttp import CQHttp

from astrbot.core import logger
from astrbot.core.message.components import Reply
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)


def parse_scope_name(
    scope_name: str = "",
    *,
    strict: bool = False,
    default_is_group: bool = True,
) -> bool | None:
    scope = scope_name.strip()
    scope_lower = scope.lower()

    if scope in ("好友", "私聊") or scope_lower in ("friend", "f"):
        return False
    if scope in ("群聊", "群") or scope_lower in ("group", "g"):
        return True
    if strict:
        return None
    return default_is_group


def parse_scope_and_index(
    arg1: str = "",
    arg2: str = "",
) -> tuple[bool, int | None, str | None]:
    first = arg1.strip()
    second = arg2.strip()

    if first.isdigit() and not second:
        index = int(first)
        if index <= 0:
            return True, None, "序号必须大于 0"
        return True, index, None

    if not first:
        return True, None, None

    is_group = parse_scope_name(first, strict=True)
    if is_group is None:
        return True, None, "参数错误，格式：开启广播 [群聊|私聊] [序号]"

    if not second:
        return is_group, None, None

    if not second.isdigit():
        return is_group, None, "序号必须是正整数"

    index = int(second)
    if index <= 0:
        return is_group, None, "序号必须大于 0"
    return is_group, index, None


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


async def get_friend_by_index(
    event: AiocqhttpMessageEvent, index: int | None
) -> tuple[str | None, str | None]:
    try:
        friends = await event.bot.get_friend_list()
        friends.sort(key=lambda x: x["user_id"])

        if index and event.is_admin():
            friend = friends[index - 1]
        else:
            uid = event.get_sender_id()
            friend = next(
                (f for f in friends if str(f["user_id"]) == str(uid)),
                None,
            )
            if not friend:
                return str(uid), str(uid)

        name = friend.get("remark") or friend.get("nickname") or str(friend["user_id"])
        return str(friend["user_id"]), name
    except Exception as e:
        logger.error(f"获取好友信息失败: {e}")
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
