from collections.abc import Iterable

from astrbot.core.config.astrbot_config import AstrBotConfig


class BroadcastGroupState:
    """
    广播群状态管理
    - disable_gids：人工禁用（配置，落盘）
    - unreachable_gids：已确认不可达的群（事实黑名单，落盘，可清空）
    """

    def __init__(self, config: AstrBotConfig):
        self.cfg = config
        self._disable_gids: list[str] = self.cfg["disable_gids"]
        self._unreachable_gids: list[str] = self.cfg["unreachable_gids"]

    # ---------- 查询 ----------

    def is_disabled(self, gid: str) -> bool:
        return gid in self._disable_gids

    def is_unreachable(self, gid: str) -> bool:
        return gid in self._unreachable_gids

    def is_broadcastable(self, gid: str) -> bool:
        return gid not in self._disable_gids and gid not in self._unreachable_gids

    def filter_broadcastable(self, gids: Iterable[str]) -> list[str]:
        return [gid for gid in gids if self.is_broadcastable(gid)]

    # ---------- 人工策略 ----------

    def enable(self, gid: str) -> bool:
        """
        启用广播（从 disable_gids 移除）
        """
        if gid in self._disable_gids:
            self._disable_gids.remove(gid)
            self.cfg.save_config()
            return True
        return False

    def disable(self, gid: str) -> bool:
        """
        禁用广播（加入 disable_gids）
        """
        if gid not in self._disable_gids:
            self._disable_gids.append(gid)
            self.cfg.save_config()
            return True
        return False

    # ---------- 运行期事实反馈 ----------

    def mark_unreachable(self, gid: str) -> bool:
        """
        标记为不可达（被踢 / 群不存在 / 无权限）
        """
        if gid not in self._unreachable_gids:
            self._unreachable_gids.append(gid)
            self.cfg.save_config()
            return True
        return False

    def clear_unreachable(self, gid: str) -> bool:
        """
        清除单个不可达标记
        """
        if gid in self._unreachable_gids:
            self._unreachable_gids.remove(gid)
            self.cfg.save_config()
            return True
        return False

    def clear_all_unreachable(self) -> bool:
        """
        清空所有不可达群（人工恢复）
        """
        if self._unreachable_gids:
            self._unreachable_gids.clear()
            self.cfg.save_config()
            return True
        return False

    # ---------- 只读视图（防误改）----------

    @property
    def disabled_gids(self) -> tuple[str, ...]:
        return tuple(self._disable_gids)

    @property
    def unreachable_gids(self) -> tuple[str, ...]:
        return tuple(self._unreachable_gids)
