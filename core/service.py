import asyncio
import random
from dataclasses import dataclass, field

from aiocqhttp import CQHttp

from astrbot.api import logger
from astrbot.core.config.astrbot_config import AstrBotConfig

from .model import BroadcastScope
from .state import BroadcastState, TargetType

# =========================
# 结果对象
# =========================


@dataclass(slots=True)
class BroadcastResult:
    success_ids: list[str] = field(default_factory=list)
    failed_ids: list[str] = field(default_factory=list)
    cancelled: bool = False

    @property
    def success_count(self) -> int:
        return len(self.success_ids)

    @property
    def failed_count(self) -> int:
        return len(self.failed_ids)

    @property
    def total(self) -> int:
        return self.success_count + self.failed_count


# =========================
# 广播服务
# =========================


class BroadcastService:
    """
    广播服务（单实例单任务）
    """

    def __init__(
        self,
        config: AstrBotConfig,
        state: BroadcastState,
        bot: CQHttp,
    ):
        self.cfg = config
        self.state = state
        self.bot = bot

    # ========================
    # 目标解析
    # ========================

    async def _get_targets(self, t: TargetType) -> list[str]:
        if t == "group":
            groups = await self.bot.get_group_list()
            ids = [str(g["group_id"]) for g in groups]
        else:
            friends = await self.bot.get_friend_list()
            ids = [str(f["user_id"]) for f in friends]

        return self.state.filter_broadcastable(t, ids)

    def _scope_to_targets(self, scope: BroadcastScope) -> list[TargetType]:
        if scope == BroadcastScope.GROUP:
            return ["group"]
        if scope == BroadcastScope.FRIEND:
            return ["friend"]
        return ["group", "friend"]


    async def broadcast(
        self,
        message_id: str | int,
        scope: BroadcastScope,
    ) -> BroadcastResult:
        result = BroadcastResult()

        try:
            for t in self._scope_to_targets(scope):
                ids = await self._get_targets(t)

                for id_ in ids:
                    await asyncio.sleep(random.uniform(0, self.cfg["broadcast_max_delay"]))

                    try:
                        await self._send_single(t, id_, message_id)
                        result.success_ids.append(f"{t}:{id_}")

                    except asyncio.CancelledError:
                        # ★ 关键：立即放行取消
                        raise

                    except Exception as e:
                        result.failed_ids.append(f"{t}:{id_}")
                        logger.warning(f"{t} {id_} 广播失败: {e}")

        except asyncio.CancelledError:
            logger.info("广播任务被取消")
            result.cancelled = True

        return result

    # ========================
    # 发送封装
    # ========================

    async def _send_single(
        self,
        t: TargetType,
        id_: str,
        message_id: str | int,
    ) -> None:
        if t == "group":
            await self.bot.forward_group_single_msg(
                group_id=int(id_),
                message_id=message_id,
            )
        else:
            await self.bot.forward_friend_single_msg(
                user_id=int(id_),
                message_id=message_id,
            )
