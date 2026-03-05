# config.py
from __future__ import annotations

import random
from collections.abc import MutableMapping
from typing import Any, Literal, get_type_hints

from astrbot.api import logger
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.star.context import Context

TargetType = Literal["group", "friend"]


class ConfigNode:
    """
    配置节点, 把 dict 变成强类型对象。
    """

    _SCHEMA_CACHE: dict[type, dict[str, type]] = {}
    _FIELDS_CACHE: dict[type, set[str]] = {}

    @classmethod
    def _schema(cls) -> dict[str, type]:
        return cls._SCHEMA_CACHE.setdefault(cls, get_type_hints(cls))

    @classmethod
    def _fields(cls) -> set[str]:
        return cls._FIELDS_CACHE.setdefault(
            cls,
            {k for k in cls._schema() if not k.startswith("_")},
        )

    def __init__(self, data: MutableMapping[str, Any]):
        object.__setattr__(self, "_data", data)
        object.__setattr__(self, "_children", {})
        for key, tp in self._schema().items():
            if key.startswith("_"):
                continue
            if key in data:
                continue
            if hasattr(self.__class__, key):
                continue
            logger.warning(f"[config:{self.__class__.__name__}] 缺少字段: {key}")

    def __getattr__(self, key: str) -> Any:
        if key in self._fields():
            value = self._data.get(key)
            tp = self._schema().get(key)

            if isinstance(tp, type) and issubclass(tp, ConfigNode):
                children: dict[str, ConfigNode] = self.__dict__["_children"]
                if key not in children:
                    if not isinstance(value, MutableMapping):
                        raise TypeError(
                            f"[config:{self.__class__.__name__}] "
                            f"字段 {key} 期望 dict，实际是 {type(value).__name__}"
                        )
                    children[key] = tp(value)
                return children[key]

            return value

        if key in self.__dict__:
            return self.__dict__[key]

        raise AttributeError(key)

    def __setattr__(self, key: str, value: Any) -> None:
        if key in self._fields():
            self._data[key] = value
            return
        object.__setattr__(self, key, value)

    def save_config(self) -> None:
        """
        保存配置到磁盘（仅允许在根节点调用）
        """
        if not isinstance(self._data, AstrBotConfig):
            raise RuntimeError(
                f"{self.__class__.__name__}.save_config() 只能在根配置节点上调用"
            )
        self._data.save_config()


# ============ 插件自定义配置 ==================


class PluginConfig(ConfigNode):
    broadcast_max_delay: float
    skip_source: bool
    disable_gids: list[str]
    disable_uids: list[str]

    def __init__(self, cfg: AstrBotConfig, context: Context | None = None):
        super().__init__(cfg)
        self.context = context

    def get_broadcast_delay(self):
        return random.uniform(0, self.broadcast_max_delay)

    def disabled_list(self, is_group: bool = True) -> list[str]:
        if is_group:
            return self.disable_gids
        return self.disable_uids

    def is_disabled(self, target_id: str, is_group: bool = True) -> bool:
        return target_id in self.disabled_list(is_group)

    def filter_broadcastable(self, ids: list[str], is_group: bool = True) -> list[str]:
        disabled = self.disabled_list(is_group)
        return [target_id for target_id in ids if target_id not in disabled]

    def enable_target(self, target_id: str, is_group: bool = True) -> bool:
        disabled = self.disabled_list(is_group)
        if target_id in disabled:
            disabled.remove(target_id)
            self.save_config()
            return True
        return False

    def disable_target(self, target_id: str, is_group: bool = True) -> bool:
        disabled = self.disabled_list(is_group)
        if target_id not in disabled:
            disabled.append(target_id)
            self.save_config()
            return True
        return False
