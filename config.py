"""运行配置与主题；无窗口或输入副作用，可安全用于无界面计算。"""

from __future__ import annotations

import colorsys
import math
import operator
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from types import MappingProxyType
from typing import ClassVar

from search_profiles import AI_PROFILES


Color = tuple[int, int, int]


def _is_positive_finite(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return value > 0 and math.isfinite(value)
    except OverflowError:
        return False


@lru_cache(maxsize=512)
def _luminance(color: Color) -> float:
    """缓存 sRGB 相对亮度，深色/浅色前景可在不同棋块间复用。"""
    channels = (channel / 255.0 for channel in color)
    red, green, blue = (
        value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
        for value in channels
    )
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


@dataclass(frozen=True, slots=True)
class AILevel:
    """A user-facing, time-bounded AI strength preset."""

    key: str
    label: str
    time_budget_ms: int

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or self.key not in AI_PROFILES:
            raise ValueError(f"unknown AI profile: {self.key!r}")
        if not isinstance(self.label, str) or not self.label.strip():
            raise ValueError("AI level label must not be empty")
        if type(self.time_budget_ms) is not int or self.time_budget_ms < 0:
            raise ValueError("AI time budget must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Runtime defaults shared by the app and command-line entry point."""

    window_width: int = 1100
    window_height: int = 760
    # 小窗口自动切换竖屏或紧凑横屏布局，不锁定桌面宽高比。
    min_window_width: int = 360
    min_window_height: int = 360
    wide_min_width: int = 840
    wide_min_height: int = 560
    wide_min_aspect: float = 1.15
    fps: int = 60

    default_size: int = 4
    min_size: int = 3
    max_size: int = 40
    target: int = 2048

    animation_ms: int = 150
    score_animation_ms: int = 520
    # 从慢到快排列，滑块和 +/- 按钮共用下标。
    auto_delays: tuple[float, ...] = (0.95, 0.58, 0.32, 0.16, 0.08)
    default_auto_speed: int = 2
    default_ai_level: int = 1

    ai_levels: ClassVar[tuple[AILevel, ...]] = (
        AILevel("fast", "快速", AI_PROFILES["fast"].time_budget_ms),
        AILevel("balanced", "均衡", AI_PROFILES["balanced"].time_budget_ms),
        AILevel("deep", "深入", AI_PROFILES["deep"].time_budget_ms),
    )

    def __post_init__(self) -> None:
        positive_dimensions = (
            self.window_width,
            self.window_height,
            self.min_window_width,
            self.min_window_height,
            self.wide_min_width,
            self.wide_min_height,
            self.fps,
            self.animation_ms,
            self.score_animation_ms,
        )
        integer_values = (
            *positive_dimensions,
            self.default_size,
            self.min_size,
            self.max_size,
            self.target,
            self.default_auto_speed,
            self.default_ai_level,
        )
        if any(type(value) is not int for value in integer_values):
            raise ValueError("integer configuration fields must contain integers")
        if any(value <= 0 for value in positive_dimensions):
            raise ValueError("window, frame-rate and animation values must be positive")
        if not _is_positive_finite(self.wide_min_aspect):
            raise ValueError("wide_min_aspect must be a positive finite number")
        if self.min_size < 2 or self.max_size < self.min_size:
            raise ValueError("board size bounds are invalid")
        if not self.min_size <= self.default_size <= self.max_size:
            raise ValueError("default_size must be within the configured size bounds")
        if self.target < 2 or self.target & (self.target - 1):
            raise ValueError("target must be a power of two starting at 2")
        try:
            delays = tuple(self.auto_delays)
        except TypeError as exc:
            raise ValueError("auto_delays must be a sequence of delays") from exc
        if len(delays) < 2 or any(not _is_positive_finite(delay) for delay in delays):
            raise ValueError("auto_delays must contain at least two positive finite values")
        if any(first <= second for first, second in zip(delays, delays[1:])):
            raise ValueError("auto_delays must be ordered from slow to fast")
        object.__setattr__(self, "auto_delays", delays)
        if not 0 <= self.default_auto_speed < len(self.auto_delays):
            raise ValueError("default_auto_speed is outside auto_delays")
        if not self.ai_levels or not 0 <= self.default_ai_level < len(self.ai_levels):
            raise ValueError("default_ai_level is outside ai_levels")
        if any(not isinstance(level, AILevel) for level in self.ai_levels):
            raise ValueError("ai_levels must contain AILevel instances")
        keys = [level.key for level in self.ai_levels]
        if len(keys) != len(set(keys)):
            raise ValueError("AI level keys must be unique")

    def clamp_size(self, value: int) -> int:
        if isinstance(value, bool):
            raise ValueError("board size must be an integer")
        try:
            size = operator.index(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("board size must be an integer") from exc
        return max(self.min_size, min(self.max_size, size))


@dataclass(frozen=True, slots=True)
class Theme:
    """Warm, accessible colour system used by every renderer component."""

    background: Color = (247, 244, 239)
    surface: Color = (255, 253, 250)
    surface_alt: Color = (244, 240, 234)
    board: Color = (169, 159, 148)
    empty_tile: Color = (202, 193, 183)

    text: Color = (42, 38, 34)
    muted_text: Color = (119, 111, 102)
    inverse_text: Color = (255, 253, 248)
    hairline: Color = (226, 219, 210)

    accent: Color = (196, 72, 50)
    accent_hover: Color = (176, 60, 42)
    ai: Color = (80, 107, 211)
    ai_hover: Color = (67, 94, 194)
    success: Color = (63, 145, 112)

    shadow: Color = (66, 55, 43)
    overlay: tuple[int, int, int, int] = (35, 30, 25, 154)

    tile_palette: ClassVar[Mapping[int, Color]] = MappingProxyType({
        0: (202, 193, 183),
        2: (238, 228, 218),
        4: (237, 224, 200),
        8: (242, 177, 121),
        16: (245, 149, 99),
        32: (246, 124, 95),
        64: (246, 94, 59),
        128: (237, 207, 114),
        256: (237, 204, 97),
        512: (237, 200, 80),
        1024: (225, 180, 65),
        2048: (217, 149, 49),
        4096: (105, 91, 159),
        8192: (87, 76, 145),
        16384: (69, 62, 128),
    })

    @lru_cache(maxsize=512)
    def tile_color(self, value: int) -> Color:
        """Return a continuous colour for every power of two."""

        value = int(value)
        if value <= 0:
            return self.empty_tile
        if value in self.tile_palette:
            return self.tile_palette[value]

        exponent = max(1, value.bit_length() - 1)
        shift = max(0, exponent - 14)
        hue = ((262 + shift * 13) % 360) / 360.0
        saturation = min(0.62, 0.42 + shift * 0.025)
        lightness = max(0.29, 0.43 - shift * 0.012)
        red, green, blue = colorsys.hls_to_rgb(hue, lightness, saturation)
        return round(red * 255), round(green * 255), round(blue * 255)

    @lru_cache(maxsize=512)
    def tile_text_color(self, value: int) -> Color:
        """Choose tile text using relative luminance instead of tile number."""

        background_luminance = _luminance(self.tile_color(value))

        def contrast(color: Color) -> float:
            foreground_luminance = _luminance(color)
            lighter = max(background_luminance, foreground_luminance)
            darker = min(background_luminance, foreground_luminance)
            return (lighter + 0.05) / (darker + 0.05)

        # 直接比较对比度，橙色棋块未必适合白字，不能只按数字大小选前景。
        return max((self.text, self.inverse_text), key=contrast)
