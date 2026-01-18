from collections.abc import Iterable
from typing import Literal

from astrbot.core.config.astrbot_config import AstrBotConfig

TargetType = Literal["group", "friend"]


class BroadcastState:
    """
    广播状态管理（群聊 / 私聊结构对齐）
    """

    def __init__(self, config: AstrBotConfig):
        self.cfg = config

        self._disable: dict[TargetType, list[str]] = {
            "group": self.cfg["disable_gids"],
            "friend": self.cfg["disable_uids"],
        }

    # =========================
    # 通用查询
    # =========================

    def is_disabled(self, t: TargetType, id_: str) -> bool:
        return id_ in self._disable[t]

    def filter_broadcastable(self, t: TargetType, ids: Iterable[str]) -> list[str]:
        return [i for i in ids if self.is_disabled(t, i)]

    # =========================
    # 人工策略
    # =========================

    def enable(self, t: TargetType, id_: str) -> bool:
        if id_ in self._disable[t]:
            self._disable[t].remove(id_)
            self.cfg.save_config()
            return True
        return False

    def disable(self, t: TargetType, id_: str) -> bool:
        if id_ not in self._disable[t]:
            self._disable[t].append(id_)
            self.cfg.save_config()
            return True
        return False

    # =========================
    # 只读视图（防误改）
    # =========================

    def disabled_ids(self, t: TargetType) -> tuple[str, ...]:
        return tuple(self._disable[t])
