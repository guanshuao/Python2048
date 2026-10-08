"""命令行入口参数；范围约束与图形界面共用 AppConfig。"""

from __future__ import annotations

import argparse
import math
from collections.abc import Sequence

from config import AppConfig


def _ui_scale(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("UI scale must be a positive finite number")
    return parsed


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    config = AppConfig()

    def _board_size(value: str) -> int:
        parsed = int(value)
        if not config.min_size <= parsed <= config.max_size:
            raise argparse.ArgumentTypeError(
                f"board size must be between {config.min_size} and {config.max_size}"
            )
        return parsed

    parser = argparse.ArgumentParser(
        description="Modern pygame 2048 with expectimax AI"
    )
    parser.add_argument(
        "--size",
        type=_board_size,
        default=config.default_size,
        help=(
            f"board order, from {config.min_size} to {config.max_size} "
            f"(default: {config.default_size})"
        ),
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="deterministic random seed",
    )
    parser.add_argument(
        "--screenshot",
        nargs="?",
        const="python2048-screenshot.png",
        metavar="PATH",
        help="render once headlessly and save a PNG",
    )
    parser.add_argument(
        "--ui-scale",
        type=_ui_scale,
        default=None,
        metavar="FACTOR",
        help="override automatic display scaling (for example 2 on a 4K screen)",
    )
    args = parser.parse_args(argv)
    if args.screenshot is not None and not args.screenshot.strip():
        parser.error("screenshot path must not be empty or whitespace")
    return args
