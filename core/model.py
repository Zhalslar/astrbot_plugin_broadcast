from enum import Enum


class BroadcastScope(Enum):
    GROUP = "群聊"
    FRIEND = "私聊"
    ALL = "全部"

    @classmethod
    def from_text(cls, text: str) -> "BroadcastScope":
        if not text:
            raise ValueError("广播范围不能为空")

        key = text.strip().lower()

        # 别名映射（显式、可控）
        if key in ("群", "群聊", "g", "group"):
            return cls.GROUP
        if key in ("好友", "私聊", "f", "friend"):
            return cls.FRIEND
        if key in ("全部", "a", "all"):
            return cls.ALL

        raise ValueError(f"未知广播范围: {text}")
