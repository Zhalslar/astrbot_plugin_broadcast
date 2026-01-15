import asyncio
import random
from dataclasses import dataclass, field

from aiocqhttp import CQHttp

from astrbot.api import logger
from astrbot.core.config.astrbot_config import AstrBotConfig

from .state import BroadcastGroupState

# =========================
# 结果对象
# =========================


@dataclass(slots=True)
class BroadcastResult:
    success_gids: list[str] = field(default_factory=list)
    failed_gids: list[str] = field(default_factory=list)
    cancelled: bool = False

    @property
    def success_count(self) -> int:
        return len(self.success_gids)

    @property
    def failed_count(self) -> int:
        return len(self.failed_gids)

    @property
    def total(self) -> int:
        return self.success_count + self.failed_count


# =========================
# 广播服务
# =========================


class BroadcastService:
    """
    广播服务（单实例单任务）
    - 通过 asyncio.Task 管理生命周期
    - 使用 CancelledError 作为唯一取消语义
    """

    def __init__(
        self,
        config: AstrBotConfig,
        state: BroadcastGroupState,
        bot: CQHttp,
    ):
        self.cfg = config
        self.state = state
        self.bot = bot

        self._task: asyncio.Task | None = None

    # ========================
    # 群列表
    # ========================

    async def get_broadcastable_gids(self) -> list[str]:
        groups = await self.bot.get_group_list()
        gids = [str(g["group_id"]) for g in groups]
        return self.state.filter_broadcastable(gids)

    # ========================
    # 对外入口
    # ========================

    def create_broadcast_task(self, message_id: str | int) -> asyncio.Task:
        """
        启动广播任务
        - 同一时间只允许一个广播
        - 取消请直接对返回的 task 调用 cancel()
        """
        if self._task and not self._task.done():
            raise RuntimeError("已有广播任务正在执行")

        self._task = asyncio.create_task(
            self._broadcast_impl(message_id),
            name="broadcast_task",
        )
        return self._task

    # ========================
    # 内部实现
    # ========================

    async def _broadcast_impl(self, message_id: str | int) -> BroadcastResult:
        result = BroadcastResult()

        try:
            gids = await self.get_broadcastable_gids()

            for gid in gids:
                # 延迟（可被 CancelledError 中断）
                await asyncio.sleep(random.uniform(0, self.cfg["broadcast_max_delay"]))

                try:
                    await self.bot.forward_group_single_msg(
                        group_id=int(gid),
                        message_id=message_id,
                    )
                    result.success_gids.append(gid)

                except Exception as e:
                    result.failed_gids.append(gid)
                    self.state.mark_unreachable(gid)
                    logger.warning(f"群 {gid} 不可达，已标记: {e}")

        except asyncio.CancelledError:
            logger.info("广播任务被取消")
            result.cancelled = True
            raise

        finally:
            self._task = None

        return result
