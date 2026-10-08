"""AI 档位的唯一配置来源；尺寸上限为深度与出生位置目标数。"""

from __future__ import annotations

import operator
from dataclasses import dataclass


def non_negative_integer(value: object, name: str) -> int:
    """Reject fractional and boolean budgets rather than silently truncating them."""
    try:
        if isinstance(value, bool):
            raise TypeError
        parsed = operator.index(value)
    except TypeError as exc:
        raise ValueError(f"{name} must be a non-negative integer") from exc
    if parsed < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return parsed


@dataclass(frozen=True, slots=True)
class SearchSettings:
    """One search profile; custom profiles keep the original size limits by default."""

    name: str
    time_budget_ms: int
    max_depth: int
    chance_branch_limit: int = 16
    deadline_check_interval: int = 32
    size_limits: tuple[tuple[int, int, int], ...] = ((10, 1, 4), (6, 2, 8), (5, 3, 12))

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("profile name must be a non-empty string")
        for field in (
            "time_budget_ms", "max_depth", "chance_branch_limit", "deadline_check_interval"
        ):
            value = non_negative_integer(getattr(self, field), field)
            if field != "time_budget_ms" and not value:
                raise ValueError(f"{field} must be positive")
            object.__setattr__(self, field, value)
        previous = float("inf")
        limits: list[tuple[int, int, int]] = []
        try:
            raw_limits = tuple(tuple(limit) for limit in self.size_limits)
        except TypeError as exc:
            raise ValueError("size limits must contain triples of integers") from exc
        for limit in raw_limits:
            if len(limit) != 3:
                raise ValueError("size limits must contain triples of integers")
            minimum_size, depth_cap, chance_cap = (
                non_negative_integer(value, "size limit") for value in limit
            )
            if min(minimum_size, depth_cap, chance_cap) < 1 or minimum_size >= previous:
                raise ValueError("size limits must be positive and ordered by decreasing size")
            previous = minimum_size
            limits.append((minimum_size, depth_cap, chance_cap))
        object.__setattr__(self, "size_limits", tuple(limits))

    def limits(self, size: int) -> tuple[int, int]:
        size = non_negative_integer(size, "board size")
        if not size:
            raise ValueError("board size must be positive")
        for minimum_size, depth_cap, chance_cap in self.size_limits:
            if size >= minimum_size:
                return min(self.max_depth, depth_cap), min(
                    self.chance_branch_limit, chance_cap, size * size
                )
        return self.max_depth, min(self.chance_branch_limit, size * size)


AI_PROFILES: dict[str, SearchSettings] = {
    "fast": SearchSettings("fast", 28, 3, 16, 24, ((10, 1, 8), (6, 1, 8), (5, 2, 12))),
    "balanced": SearchSettings("balanced", 85, 5, 32, 32, ((10, 1, 16), (6, 2, 16), (5, 3, 16))),
    "deep": SearchSettings("deep", 220, 6, 32, 40, ((10, 2, 32), (6, 3, 24), (5, 4, 24))),
}
