"""跨平台中文字体选择和有界文字缓存，避免每帧重复栅格化相同文字。"""

from __future__ import annotations

import os
import sys
from collections import OrderedDict
from collections.abc import Sequence
from pathlib import Path

import pygame


class FontBook:
    """Choose one CJK-capable family and cache its real font faces.

    Keeping Chinese, Latin text and numerals in one family avoids uneven cap
    heights and stroke weights. The ordered family list follows each desktop OS.
    """

    def __init__(self) -> None:
        regular: str | None = None
        medium: str | None = None
        if os.name == "nt":
            font_dir = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
            regular = self._first_file(font_dir, ("msyh.ttc", "NotoSansSC-VF.ttf"))
            medium = self._first_file(font_dir, ("msyhbd.ttc", "NotoSansSC-VF.ttf"))
            families = (
                "microsoftyaheiui", "microsoftyahei", "notosanscjksc",
                "notosanssc", "malgungothic",
            )
        elif sys.platform == "darwin":
            families = (
                "pingfangsc", "hiraginosansgb", "heitisc", "notosanscjksc",
                "notosanssc", "arialunicode",
            )
        else:
            families = (
                "notosanscjksc", "notosanssc", "sourcehansanssc",
                "wenquanyimicrohei", "droidsansfallback", "unifont",
            )

        regular = regular or pygame.font.match_font(families)
        medium = medium or pygame.font.match_font(families, bold=True) or regular
        # 找不到中文字体时，None 让 pygame 使用内置字体作为最终回退。
        self.paths = {"ui": regular, "ui_bold": medium, "number": medium}
        self.cache: OrderedDict[tuple[str, int], pygame.font.Font] = OrderedDict()
        self.render_cache: OrderedDict[
            tuple[str, int, str, tuple[int, int, int]], pygame.Surface
        ] = OrderedDict()

    @staticmethod
    def _first_file(font_dir: Path, filenames: Sequence[str]) -> str | None:
        for filename in filenames:
            path = font_dir / filename
            if path.is_file():
                return str(path)
        return None

    def get(self, size: int, bold: bool = False, *, role: str = "ui") -> pygame.font.Font:
        face = "number" if role == "number" else ("ui_bold" if bold else "ui")
        key = (face, max(7, int(size)))
        if key not in self.cache:
            # 只淘汰最久未使用的字号，缩放窗口时仍保留常用字体。
            if len(self.cache) >= 96:
                self.cache.popitem(last=False)
            self.cache[key] = pygame.font.Font(self.paths[face], key[1])
        self.cache.move_to_end(key)
        return self.cache[key]

    def render(
        self,
        text: object,
        size: int,
        color: tuple[int, int, int],
        bold: bool = False,
        *,
        role: str = "ui",
    ) -> pygame.Surface:
        """Render and cache reusable label and tile-number surfaces."""

        face = "number" if role == "number" else ("ui_bold" if bold else "ui")
        pixel_size = max(7, int(size))
        key = (face, pixel_size, str(text), tuple(color))
        image = self.render_cache.get(key)
        if image is None:
            # 缓存最近常用标签与棋块数字，不无限保留缩放历史。
            if len(self.render_cache) >= 256:
                self.render_cache.popitem(last=False)
            image = self.get(pixel_size, bold, role=role).render(
                str(text), True, color
            )
            self.render_cache[key] = image
        self.render_cache.move_to_end(key)
        return image
