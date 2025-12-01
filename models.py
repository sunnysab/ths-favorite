from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Set

from loguru import logger


@dataclass(frozen=True)
class THSFavorite:
    """同花顺自选股的单个项目数据类。"""

    code: str
    market: Optional[str] = None

    def __post_init__(self) -> None:
        if self.market:
            object.__setattr__(self, "market", self.market.upper())

    def __repr__(self) -> str:
        if self.market:
            return f"THSFavorite(code='{self.code}', market='{self.market}')"
        return f"THSFavorite(code='{self.code}')"


@dataclass
class THSFavoriteGroup:
    """同花顺自选股的分组数据类。"""

    name: str
    group_id: str
    items: List[THSFavorite] = field(default_factory=list)

    def __repr__(self) -> str:
        return (
            f"THSFavoriteGroup(name='{self.name}', "
            f"group_id='{self.group_id}', items_count={len(self.items)})"
        )

    def diff(self, other: "THSFavoriteGroup") -> Tuple[List[THSFavorite], List[THSFavorite]]:
        if not isinstance(other, THSFavoriteGroup):
            logger.error(
                "类型错误: 比较对象 'other' 必须是 THSFavoriteGroup 类型，而非 %s。",
                type(other),
            )
            raise TypeError("比较对象 'other' 必须是 THSFavoriteGroup 类型。")

        self_items_set: Set[THSFavorite] = set(self.items)
        other_items_set: Set[THSFavorite] = set(other.items)

        added_items: List[THSFavorite] = list(other_items_set - self_items_set)
        removed_items: List[THSFavorite] = list(self_items_set - other_items_set)

        logger.debug(
            "分组 '%s' 与 '%s' 比较: 新增 %d 项, 删除 %d 项。",
            self.name,
            other.name,
            len(added_items),
            len(removed_items),
        )
        return added_items, removed_items
