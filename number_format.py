"""棋盘和界面共用的有界整数显示，不依赖窗口或数值加速库。"""

from __future__ import annotations


def format_integer(value: int, *, compact: bool = False, grouped: bool = False) -> str:
    """Bound display length without converting arbitrary-sized integers to float."""

    if value.bit_length() > 64:
        exponent = value.bit_length() - 1
        magnitude = abs(value)
        prefix = "" if magnitude & (magnitude - 1) == 0 else "≈"
        sign = "-" if value < 0 else ""
        return f"{prefix}{sign}2^{exponent}"
    if compact and value >= 1_048_576:
        return f"{value / 1_048_576:g}M"
    if compact and value >= 1024:
        return f"{value / 1024:g}K"
    return f"{value:,}" if grouped else str(value)
