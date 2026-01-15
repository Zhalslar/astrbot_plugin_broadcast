
from enum import Enum


class BroadcastScope(Enum):
    GROUP = "群聊"
    FRIEND = "私聊"
    ALL = "全部"

    @classmethod
    def from_text(cls, text: str) -> "BroadcastScope":
        for item in cls:
            if item.value == text:
                return item
        raise ValueError(f"未知广播范围: {text}")
