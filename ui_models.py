"""UI 共用的小型状态结构；动画只携带描述信息，不修改游戏棋盘。"""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from game_rules import TileMotion


KEY_DIRECTIONS = {
    pygame.K_LEFT: "L", pygame.K_a: "L",
    pygame.K_RIGHT: "R", pygame.K_d: "R",
    pygame.K_UP: "U", pygame.K_w: "U",
    pygame.K_DOWN: "D", pygame.K_s: "D",
}
DIRECTION_LABELS = {
    "L": ("←", "向左"), "R": ("→", "向右"),
    "U": ("↑", "向上"), "D": ("↓", "向下"),
}


@dataclass(slots=True)
class Button:
    label: str
    rect: pygame.Rect
    style: str = "secondary"
    enabled: bool = True
    selected: bool = False

    def is_click(self, position: tuple[int, int]) -> bool:
        return self.enabled and self.rect.collidepoint(position)


@dataclass(frozen=True, slots=True)
class TilePulse:
    kind: str
    started_at: float
    duration: float


@dataclass(frozen=True, slots=True)
class ScoreBurst:
    amount: int
    started_at: float
    duration: float


@dataclass(frozen=True, slots=True)
class MoveAnimation:
    motions: tuple[TileMotion, ...]
    started_at: float
    duration: float


@dataclass(frozen=True, slots=True)
class PendingMove:
    """Keep a queued action's origin until the controller can execute it."""

    direction: str
    source: str
    revision: int
    generation: int


@dataclass(slots=True)
class BoardLayer:
    key: tuple
    surface: pygame.Surface
    cell_size: float
    rects: tuple[tuple[pygame.Rect, ...], ...]


@dataclass(slots=True)
class TileLayer:
    key: tuple
    surface: pygame.Surface


BUTTON_HELP = {
    "new_game": "R · 按所选尺寸开始新游戏",
    "undo": "Z · 撤销并暂停自动",
    "auto": "Space / P · 开启或暂停自动",
    "hint": "H · 显示当前棋盘建议",
    "single": "N · 让 AI 移动一步",
    "help": "F1 · 操作说明",
    "size_down": "下一局缩小棋盘",
    "size_up": "下一局增大棋盘",
    "speed_down": "降低自动速度",
    "speed_up": "提高自动速度",
    "strength_0": "较少计算，优先响应速度",
    "strength_1": "平衡计算时间与搜索范围",
    "strength_2": "更多计算，扩大搜索范围",
}
