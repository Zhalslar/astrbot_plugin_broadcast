import asyncio
import random

from aiocqhttp import CQHttp

from astrbot.api import logger
from astrbot.api.event import filter
from astrbot.api.star import Context, Star
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.message.message_event_result import MessageChain
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)
from astrbot.core.utils.session_waiter import (
    SessionController,
    session_waiter,
)


class BroadcastPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.disable_gids: list[str] = config.get("disable_gids", [])
        self.broadcast_message = None

    async def get_able_gids(self, client: CQHttp) -> list[str] | None:
        all_groups = await client.get_group_list()
        all_gids = [str(group["group_id"]) for group in all_groups]
        able_gids = [gid for gid in all_gids if gid not in self.disable_gids]
        return able_gids

    async def get_target_group(
        self, event: AiocqhttpMessageEvent, group_index: int | None = None
    ):
        """
        获取目标群组的 ID 和名称
        """
        try:
            all_groups = await event.bot.get_group_list()
            all_groups.sort(key=lambda x: x["group_id"])
            group_map = {
                str(group["group_id"]): group["group_name"] for group in all_groups
            }

            if group_index and event.is_admin():  # 仅管理员可以指定索引
                try:
                    target_group_id = str(all_groups[group_index - 1]["group_id"])
                    group_name = group_map[target_group_id]
                except IndexError:
                    logger.error("索引越界")
                    return None, None

            else:
                target_group_id = event.get_group_id()
                group_name = group_map.get(target_group_id, "未知群组")

            return target_group_id, group_name
        except Exception as e:
            logger.error(f"获取群组信息时发生错误：{e}")
            return None, None

    @filter.command("开启广播")
    async def enable_broadcast(
        self, event: AiocqhttpMessageEvent, group_index: int | None = None
    ):
        """
        开启广播，开启后当前群聊可接收来自机器人管理员的广播消息。
        """
        # 如果提供了 group_index，则关闭指定索引的群组广播；否则关闭当前群组的广播
        target_group_id, group_name = await self.get_target_group(event, group_index)
        if target_group_id is None:
            return

        if str(target_group_id) in self.disable_gids:
            self.disable_gids.remove(str(target_group_id))
            self.config.save_config()
            yield event.plain_result(f"【{group_name}】可以接收广播消息了")
        else:
            yield event.plain_result(f"【{group_name}】已开启广播，无需重复开启")

    @filter.command("关闭广播")
    async def disable_broadcast(
        self, event: AiocqhttpMessageEvent, group_index: int | None = None
    ):
        """
        关闭广播，关闭后当前群聊将不再接收来自机器人管理员的广播消息。
        """
        # 如果提供了 group_index，则关闭指定索引的群组广播；否则关闭当前群组的广播
        target_group_id, group_name = await self.get_target_group(event, group_index)
        if target_group_id is None:
            return

        if target_group_id not in self.disable_gids:
            self.disable_gids.append(str(target_group_id))
            self.config.save_config()
            yield event.plain_result(f"【{group_name}】不再接收广播消息")
        else:
            yield event.plain_result(f"【{group_name}】已关闭广播，无需重复关闭")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("广播列表")
    async def broadcast_list(self, event: AiocqhttpMessageEvent):
        """查看将要向哪些群广播"""
        all_groups = await event.bot.get_group_list()
        all_groups.sort(key=lambda x: x["group_id"])
        able_gids_str = []
        disable_gids_str = []
        for idx, group in enumerate(all_groups, start=1):
            group_info = f"{idx}: {group['group_name']}"
            if str(group["group_id"]) in self.disable_gids:
                disable_gids_str.append(group_info)
            else:
                able_gids_str.append(group_info)

        reply = (
            "【开启广播的群聊】\n" + "\n".join(able_gids_str) + "\n\n"
            "【关闭广播的群聊】\n" + "\n".join(disable_gids_str)
        ).strip()
        yield event.plain_result(reply)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("广播")
    async def broadcast(self, event: AiocqhttpMessageEvent):
        """向所有启用广播的群聊广播消息"""
        group_id = event.get_group_id()
        sender_id = event.get_sender_id()
        yield event.plain_result("请30秒内发送要广播的消息")

        @session_waiter(timeout=30, record_history_chains=True)  # type: ignore
        async def empty_mention_waiter(
            controller: SessionController, event: AiocqhttpMessageEvent
        ):
            if group_id != event.get_group_id() or sender_id != event.get_sender_id():
                return

            client = event.bot
            able_gids = await self.get_able_gids(client)
            if not able_gids:
                await event.send(event.make_result().message("没有可广播的群聊"))
                controller.stop()
                return

            if event.message_str == "取消广播":
                await event.send(event.make_result().message("广播已取消"))
                controller.stop()
                return

            # 存储最后一条消息，当用户输入确认广播时发送
            if event.message_str != "确认广播":
                self.broadcast_message = await event._parse_onebot_json(
                    MessageChain(chain=event.message_obj.message)
                )
                await event.send(
                    event.make_result().message(
                        f"准备向{len(able_gids)}个群广播这条消息\n请发送“确认广播/取消广播”"
                    )
                )
                controller.keep(timeout=30, reset_timeout=True)

            elif self.broadcast_message:
                await event.send(event.make_result().message("正在广播中..."))
                success_count = 0  # 发送成功的群组数量
                failure_count = 0  # 发送失败的群组数量
                for gid in able_gids:
                    await asyncio.sleep(random.randint(1, 3))  # 控制发送间隔
                    try:
                        await client.send_group_msg(
                            group_id=int(gid), message=self.broadcast_message
                        )
                        success_count += 1
                        controller.keep(timeout=30, reset_timeout=True)
                    except Exception as e:
                        failure_count += 1
                        logger.error(f"向群组 {gid} 发送消息失败: {e}")
                        pass

                await event.send(
                    event.make_result().message(
                        f"广播完成\n成功：{success_count}个群\n失败：{failure_count}个群"
                    )
                )
                self.broadcast_message = None
                controller.stop()

        try:
            await empty_mention_waiter(event)
        except TimeoutError as _:
            yield event.plain_result("等待超时！")
        except Exception as e:
            logger.error("广播插件出错: " + str(e))
        finally:
            event.stop_event()
