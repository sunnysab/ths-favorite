from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Set

from loguru import logger


@dataclass(frozen=True)
class StockItem:
    """同花顺自选股的单个项目数据类。"""

    code: str = field(compare=True)
    market: Optional[str] = field(default=None, compare=True)
    price: Optional[float] = field(default=None, compare=False)
    added_at: Optional[str] = field(default=None, compare=False)

    def __post_init__(self) -> None:
        if self.market:
            object.__setattr__(self, "market", self.market.upper())

    def __repr__(self) -> str:
        extras = []
        if self.market:
            extras.append(f"market='{self.market}'")
        if self.price is not None:
            extras.append(f"price={self.price}")
        if self.added_at:
            extras.append(f"added_at='{self.added_at}'")
        extras_str = ", ".join(extras)
        if extras_str:
            return f"StockItem(code='{self.code}', {extras_str})"
        return f"StockItem(code='{self.code}')"


@dataclass
class StockGroup:
    """同花顺自选股的分组数据类。"""

    name: str
    group_id: str
    items: List[StockItem] = field(default_factory=list)

    def __repr__(self) -> str:
        return (
            f"StockGroup(name='{self.name}', "
            f"group_id='{self.group_id}', items_count={len(self.items)})"
        )

    def diff(self, other: "StockGroup") -> Tuple[List[StockItem], List[StockItem]]:
        if not isinstance(other, StockGroup):
            logger.error(
                "类型错误: 比较对象 'other' 必须是 StockGroup 类型，而非 %s。",
                type(other),
            )
            raise TypeError("比较对象 'other' 必须是 StockGroup 类型。")

        self_items_set: Set[StockItem] = set(self.items)
        other_items_set: Set[StockItem] = set(other.items)

        added_items: List[StockItem] = list(other_items_set - self_items_set)
        removed_items: List[StockItem] = list(self_items_set - other_items_set)

        logger.debug(
            "分组 '%s' 与 '%s' 比较: 新增 %d 项, 删除 %d 项。",
            self.name,
            other.name,
            len(added_items),
            len(removed_items),
        )
        return added_items, removed_items
