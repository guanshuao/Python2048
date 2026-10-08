"""界面绘制：静态棋盘底层缓存，滑动、合并和得分效果按时间叠加。"""

from __future__ import annotations

import math
import time

import pygame

from number_format import format_integer
from ui_models import BUTTON_HELP, BoardLayer, Button, DIRECTION_LABELS, TileLayer


class RendererMixin:
    """Draw a host's screen, theme, game and layout state without mutating gameplay."""

    def render(self) -> None:
        self.screen.fill(self.theme.background)
        self._draw_shadow(self.board_rect, self._px(22))
        self._draw_board()
        self._draw_shadow(self.panel_rect, self._px(24))
        pygame.draw.rect(
            self.screen,
            self.theme.surface,
            self.panel_rect,
            border_radius=self._px(24),
        )
        self._draw_panel()
        if self.modal:
            self._draw_modal()
        else:
            self._draw_hover_detail()

    def _draw_shadow(self, rect: pygame.Rect, radius: int) -> None:
        key = (rect.width, rect.height, radius, self.ui_scale, self.theme.shadow)
        layer = self.shadow_cache.get(key)
        if layer is None:
            if len(self.shadow_cache) >= 8:
                del self.shadow_cache[next(iter(self.shadow_cache))]
            pad = self._px(14)
            layer = pygame.Surface(
                (rect.width + pad * 2, rect.height + pad * 2),
                pygame.SRCALPHA,
            )
            # 小尺寸半透明层叠出柔和阴影，避免逐帧创建全窗口透明表面。
            for logical_spread, alpha in ((6, 5), (4, 7), (2, 10), (0, 13)):
                spread = self._px(logical_spread) if logical_spread else 0
                shadow = pygame.Rect(
                    pad - spread,
                    pad + self._px(6) - spread,
                    rect.width + spread * 2,
                    rect.height + spread * 2,
                )
                pygame.draw.rect(
                    layer,
                    (*self.theme.shadow, alpha),
                    shadow,
                    border_radius=radius + spread,
                )
            self.shadow_cache[key] = layer
        self.screen.blit(layer, (rect.x - self._px(14), rect.y - self._px(14)))

    def _draw_board(self) -> None:
        board = self._snapshot()
        count = len(board)
        now = time.monotonic()
        cell, rects = self._draw_board_background(count)
        maximum = max((max(row) for row in board), default=0)

        animation = self.move_animation
        if animation is not None:
            progress = (now - animation.started_at) / max(0.001, animation.duration)
            if progress < 1.0:
                progress = max(0.0, progress)
                eased = 1.0 - (1.0 - progress) ** 3
                for motion in animation.motions:
                    source_rect = rects[motion.source[0]][motion.source[1]]
                    destination_rect = rects[motion.destination[0]][motion.destination[1]]
                    center_x = source_rect.centerx + (
                        destination_rect.centerx - source_rect.centerx
                    ) * eased
                    center_y = source_rect.centery + (
                        destination_rect.centery - source_rect.centery
                    ) * eased
                    rect = pygame.Rect(
                        0,
                        0,
                        max(1, round(cell)),
                        max(1, round(cell)),
                    )
                    rect.center = round(center_x), round(center_y)
                    self._draw_tile(rect, motion.value, cell, maximum)
                return
            # 动画结束由控制器处理；绘制不能丢弃排队输入或待显示弹窗。

        if not any(now < pulse.started_at + pulse.duration for pulse in self.tile_pulses.values()):
            # One transparent foreground per board revision, rebuilt only when
            # board/geometry/theme changes. Animations keep their own draw path.
            key = (self.board_layer.key, self.board_revision)
            if self.tile_layer is None or self.tile_layer.key != key:
                layer = pygame.Surface(self.board_rect.size, pygame.SRCALPHA)
                for row_index, row in enumerate(board):
                    for column_index, value in enumerate(row):
                        if value:
                            rect = rects[row_index][column_index].move(
                                -self.board_rect.x, -self.board_rect.y
                            )
                            self._draw_tile(rect, value, cell, maximum, surface=layer)
                self.tile_layer = TileLayer(key, layer)
            self.screen.blit(self.tile_layer.surface, self.board_rect)
            return

        for row_index, row in enumerate(board):
            for column_index, value in enumerate(row):
                if not value:
                    continue
                rect = rects[row_index][column_index]
                pulse = self.tile_pulses.get((row_index, column_index))
                if pulse and now >= pulse.started_at:
                    progress = max(
                        0.0,
                        min(1.0, (now - pulse.started_at) / pulse.duration),
                    )
                    if pulse.kind == "spawn":
                        scale = 0.55 + 0.45 * (1.0 - (1.0 - progress) ** 3)
                    else:
                        scale = 1.0 + 0.14 * math.sin(progress * math.pi)
                    width = max(1, round(rect.width * scale))
                    height = max(1, round(rect.height * scale))
                    center = rect.center
                    rect = pygame.Rect(0, 0, width, height)
                    rect.center = center
                self._draw_tile(rect, value, cell, maximum)

    def _draw_board_background(self, count: int):
        # 只缓存当前几何；窗口、棋盘阶数或主题改变时自动重建，不累积历史尺寸。
        key = (tuple(self.board_rect), count, self.ui_scale, self.theme)
        cached = self.board_layer
        if cached is None or cached.key != key:
            gap = max(self.ui_scale, min(11 * self.ui_scale, self.board_rect.width / (count * 11.5)))
            cell = (self.board_rect.width - gap * (count + 1)) / count
            rects = tuple(
                tuple(self._tile_rect(row, column, gap, cell) for column in range(count))
                for row in range(count)
            )
            layer = pygame.Surface(self.board_rect.size, pygame.SRCALPHA)
            pygame.draw.rect(
                layer, self.theme.board, layer.get_rect(),
                border_radius=max(self._px(5), min(self._px(18), round(cell * 0.16))),
            )
            radius = max(0, min(self._px(10), round(cell * 0.11)))
            for row in rects:
                for rect in row:
                    pygame.draw.rect(
                        layer, self.theme.empty_tile,
                        rect.move(-self.board_rect.x, -self.board_rect.y),
                        border_radius=radius,
                    )
            self.board_layer = BoardLayer(key, layer, cell, rects)
        cached = self.board_layer
        self.screen.blit(cached.surface, self.board_rect)
        return cached.cell_size, cached.rects

    def _tile_rect(
        self,
        row: int,
        column: int,
        gap: float,
        cell: float,
    ) -> pygame.Rect:
        x = self.board_rect.x + gap + column * (cell + gap)
        y = self.board_rect.y + gap + row * (cell + gap)
        return pygame.Rect(
            round(x),
            round(y),
            max(1, round(cell)),
            max(1, round(cell)),
        )

    def _draw_tile(
        self,
        rect: pygame.Rect,
        value: int,
        cell: float,
        maximum: int,
        *,
        surface: pygame.Surface | None = None,
    ) -> None:
        target = self.screen if surface is None else surface
        pygame.draw.rect(
            target,
            self.theme.tile_color(value),
            rect,
            border_radius=max(0, min(self._px(10), round(cell * 0.11))),
        )
        logical_cell = cell / max(0.01, self.ui_scale)
        show = logical_cell >= 25
        if 17 <= logical_cell < 25:
            show = value >= max(64, maximum // 8)
        elif logical_cell < 17:
            show = value >= max(128, maximum // 2)
        if not show:
            return

        text = format_integer(value, compact=logical_cell < 34)
        size = max(
            self._px(7),
            min(
                self._px(58),
                round(cell * (0.47 if len(text) < 4 else 0.36)),
            ),
        )
        color = self.theme.tile_text_color(value)
        image = self.fonts.render(text, size, color, role="number")
        while image.get_width() > rect.width * 0.84 and size > self._px(7):
            size -= 1
            image = self.fonts.render(text, size, color, role="number")
        # Tiny cells remain identifiable by colour and hover detail. A minimum
        # font size must never allow a label to spill into neighbouring cells.
        if image.get_width() > rect.width * 0.9 or image.get_height() > rect.height * 0.9:
            return
        target.blit(image, image.get_rect(center=rect.center))

    def _draw_panel(self) -> None:
        compact = self.layout_mode != "wide"
        self._text(
            "2048",
            self.title_position,
            30 if compact else 36,
            self.theme.text,
            role="number",
        )
        if not compact:
            self._text(
                f"{self.size} × {self.size} · AI 实验室",
                self.subtitle_position,
                12,
                self.theme.muted_text,
                max_width=self.panel_rect.width - self._px(40),
            )
        for name, label, value in (
            ("score", "得分", self.game.score),
            ("best", "最大", max(max(row) for row in self._snapshot())),
            ("moves", "步数", self.game.moves),
        ):
            rect = self.stats_rects[name]
            pygame.draw.rect(
                self.screen,
                self.theme.surface_alt,
                rect,
                border_radius=self._px(12),
            )
            self._text(
                label,
                (
                    rect.centerx,
                    rect.y + self._px(5 if compact else 10),
                ),
                9 if compact else 10,
                self.theme.muted_text,
                center=True,
                max_width=rect.width - self._px(8),
                min_size=8,
            )
            self._text(
                format_integer(value, grouped=True),
                (
                    rect.centerx,
                    rect.y + rect.height - self._px(5 if compact else 13),
                ),
                16 if compact else 20,
                self.theme.text,
                center=True,
                bottom=True,
                role="number",
                max_width=rect.width - self._px(8),
                min_size=10,
            )
        self._draw_score_bursts()

        self._text(
            ("棋盘 · 下局生效" if self.selected_size != self.size else "棋盘")
            if compact else "棋盘尺寸 · 新游戏后生效",
            self.section_label_positions["size"],
            10 if compact else 12,
            self.theme.muted_text,
            max_width=self.panel_rect.width - self._px(28),
            min_size=8,
        )
        pygame.draw.rect(
            self.screen,
            self.theme.surface_alt,
            self.size_value_rect,
            border_radius=self._px(11),
        )
        size_color = (
            self.theme.accent
            if self.selected_size != self.size
            else self.theme.text
        )
        self._text(
            f"{self.selected_size} × {self.selected_size}",
            self.size_value_rect.center,
            18,
            size_color,
            center=True,
            middle=True,
            role="number",
            max_width=self.size_value_rect.width - self._px(8),
            min_size=10,
        )

        for name, label in (("strength", "AI 强度"), ("speed", "自动速度")):
            self._text(
                label, self.section_label_positions[name],
                10 if compact else 12, self.theme.muted_text,
            )
        speed_label = f"间隔 {self.config.auto_delays[self.speed_level]:g}s"
        self._text(
            speed_label,
            (self.buttons["speed_up"].rect.right, self.section_label_positions["speed"][1]),
            9 if compact else 10,
            self.theme.muted_text,
            right=True,
        )
        pygame.draw.rect(
            self.screen,
            self.theme.hairline,
            self.speed_track,
            border_radius=self._px(4),
        )
        fraction = self.speed_level / (len(self.config.auto_delays) - 1)
        knob_x = round(self.speed_track.left + fraction * self.speed_track.width)
        pygame.draw.circle(
            self.screen,
            self.theme.ai,
            (knob_x, self.speed_track.centery),
            self._px(8),
        )

        self._refresh_buttons()
        for button in self.buttons.values():
            self._draw_button(button)

        self._draw_hint_card(compact)

    def _draw_hint_card(self, compact: bool) -> None:
        pygame.draw.rect(
            self.screen,
            self.theme.surface_alt,
            self.hint_card,
            border_radius=self._px(13),
        )
        if self.hint_direction:
            arrow, label = DIRECTION_LABELS[self.hint_direction]
            arrow_x = self.hint_card.x + self._px(18 if compact else 28)
            arrow_rect = self._text(
                arrow,
                (arrow_x, self.hint_card.centery),
                20 if compact else 28,
                self.theme.ai,
                center=True,
                middle=True,
                bold=True,
            )
            message = f"建议{label}"
            # 两行文字共用箭头右侧区域；实际字形宽度会随字体和缩放变化。
            message_x = max(
                self.hint_card.x + self._px(36 if compact else 52),
                arrow_rect.right + self._px(8),
            )
        else:
            message = self.search_status
            message_x = self.hint_card.x + self._px(12 if compact else 18)
        message_width = max(0, self.hint_card.right - message_x - self._px(10))
        text_region = pygame.Rect(
            message_x, self.hint_card.y, message_width, self.hint_card.height
        )
        old_clip = self.screen.get_clip()
        # 缩到最小字号仍放不下的长文本，只显示在文字区域内。
        self.screen.set_clip(old_clip.clip(text_region))
        try:
            self._text(
                message,
                (
                    message_x,
                    self.hint_card.centery
                    if compact
                    else self.hint_card.y + self._px(13),
                ),
                12 if compact else 14,
                self.theme.text,
                middle=compact,
                max_width=message_width,
                min_size=8,
            )
            if not compact:
                self._text(
                    self.search_detail or "方向键移动 · Z 撤销 · Space 自动 · F1 帮助",
                    (message_x, self.hint_card.y + self._px(39)),
                    10,
                    self.theme.muted_text,
                    max_width=message_width,
                    min_size=8,
                )
        finally:
            self.screen.set_clip(old_clip)

    def _draw_score_bursts(self) -> None:
        now = time.monotonic()
        score_rect = self.stats_rects["score"]
        for burst in self.score_bursts:
            progress = (now - burst.started_at) / burst.duration
            if progress < 0.0:
                continue
            if progress >= 1.0:
                continue
            # 透明度属于本帧效果，复制缓存文字，不能修改共享的文字表面。
            image = self.fonts.render(
                f"+{format_integer(burst.amount)}", self._px(13), self.theme.success, role="number"
            ).copy()
            image.set_alpha(round(255 * (1.0 - progress)))
            rect = image.get_rect(
                midbottom=(
                    score_rect.centerx,
                    score_rect.bottom
                    - self._px(5)
                    - round(progress * self._px(20)),
                )
            )
            self.screen.blit(image, rect)

    def _draw_button(self, button: Button) -> None:
        hover = button.enabled and button.rect.collidepoint(self.mouse_pos)
        if not button.enabled:
            fill, text = self.theme.surface_alt, (174, 167, 159)
        elif button.style == "primary":
            fill = self.theme.accent_hover if hover else self.theme.accent
            text = self.theme.inverse_text
        elif button.style == "ai" or button.selected:
            fill = self.theme.ai_hover if hover else self.theme.ai
            text = self.theme.inverse_text
        else:
            fill = (235, 230, 223) if hover else self.theme.surface_alt
            text = self.theme.text
        pygame.draw.rect(
            self.screen,
            fill,
            button.rect,
            border_radius=self._px(10),
        )
        if button.enabled and self.focus_action is not None and (
            self.buttons.get(self.focus_action) is button
            or self.modal_buttons.get(self.focus_action) is button
        ):
            pygame.draw.rect(
                self.screen, self.theme.ai, button.rect.inflate(self._px(4), self._px(4)),
                width=self._px(2), border_radius=self._px(12),
            )
        old_clip = self.screen.get_clip()
        self.screen.set_clip(button.rect)
        self._text(
            button.label,
            button.rect.center,
            13,
            text,
            center=True,
            middle=True,
            max_width=max(1, button.rect.width - self._px(12)),
            min_size=9,
        )
        self.screen.set_clip(old_clip)

    def _draw_modal(self) -> None:
        self._layout_modal()
        size = self.screen.get_size()
        overlay_color = self.theme.overlay
        cached = self.modal_overlay
        if cached is None or cached[0] != size or cached[1] != overlay_color:
            overlay = pygame.Surface(size, pygame.SRCALPHA)
            overlay.fill(overlay_color)
            self.modal_overlay = (size, overlay_color, overlay)
        else:
            overlay = cached[2]
        self.screen.blit(overlay, (0, 0))
        card = self.modal_card_rect
        self._draw_shadow(card, self._px(22))
        pygame.draw.rect(
            self.screen,
            self.theme.surface,
            card,
            border_radius=self._px(22),
        )
        if self.modal == "help":
            self._draw_help_content()
            return
        won = self.modal == "win"
        title = "游戏成功！" if won else "游戏结束"
        subtitle = (
            f"已合成 {format_integer(self.config.target, grouped=True)}，可继续挑战更大的数字"
            if won
            else "棋盘已没有可行移动"
        )
        text_width = self.modal_text_width
        self._text(
            title,
            (card.centerx, card.y + self._px(46)),
            29,
            self.theme.accent if won else self.theme.text,
            center=True,
            bold=True,
            max_width=text_width,
            min_size=20,
        )
        self._text(
            subtitle,
            (card.centerx, card.y + self._px(90)),
            13,
            self.theme.muted_text,
            center=True,
            max_width=text_width,
            min_size=10,
        )
        summary = (
            f"得分 {format_integer(self.game.score, grouped=True)}  ·  "
            f"最大数字 {format_integer(self.game.best_tile, grouped=True)}"
        )
        self._text(
            summary,
            (card.centerx, card.y + self._px(130)),
            15,
            self.theme.text,
            center=True,
            max_width=text_width,
            min_size=10,
        )
        for button in self.modal_buttons.values():
            self._draw_button(button)

    def _draw_help_content(self) -> None:
        """Keep the essential controls discoverable in every layout."""
        card = self.modal_card_rect
        self._text("操作说明", (card.centerx, card.y + self._px(18)), 24,
                   self.theme.text, center=True, bold=True)
        lines = (
            ("移动", "方向键 / WASD / 棋盘滑动"),
            ("新局 / 撤销", "R / Z；撤销会暂停自动"),
            ("自动 / 单步", "Space 或 P / N"),
            ("提示 / 速度", "H / + −；速度条可拖动"),
            ("键盘操作", "Tab 切换控件，Enter 确认"),
            ("棋盘尺寸", "所选尺寸在新游戏后生效"),
            ("查看数值", "悬停格子显示数值和坐标"),
            ("退出", "Esc；弹层内先关闭弹层"),
        )
        top = card.y + self._px(67)
        button = self.modal_buttons["modal_dismiss"]
        button_top = button.rect.top
        row_height = max(1, (button_top - self._px(12) - top) // len(lines))
        inset = self._px(20)
        label_width = min(self._px(105), round(card.width * 0.29))
        for index, (label, message) in enumerate(lines):
            line_y = top + index * row_height
            self._text(label, (card.x + inset, line_y), 12, self.theme.muted_text,
                       max_width=label_width - self._px(8), min_size=9)
            self._text(message, (card.x + inset + label_width, line_y), 12, self.theme.text,
                       max_width=card.width - inset * 2 - label_width, min_size=8)
        self._draw_button(button)

    def _draw_hover_detail(self) -> None:
        message = None
        if self.board_rect.collidepoint(self.mouse_pos) and self.move_animation is None and self.board_layer:
            count = len(self._snapshot())
            gap = (self.board_rect.width - self.board_layer.cell_size * count) / (count + 1)
            stride = self.board_layer.cell_size + gap
            column = int((self.mouse_pos[0] - self.board_rect.x - gap) // stride)
            row = int((self.mouse_pos[1] - self.board_rect.y - gap) // stride)
            if 0 <= row < count and 0 <= column < count:
                if self.board_layer.rects[row][column].collidepoint(self.mouse_pos):
                    value = self._snapshot()[row][column]
                    label = format_integer(value, grouped=True) if value else "空格"
                    message = f"{label} · 第 {row + 1} 行，第 {column + 1} 列"
        if message is None:
            action = self._action_at(self.mouse_pos)
            message = BUTTON_HELP.get(action)
        if not message:
            return
        image = self.fonts.render(message, self._px(11), self.theme.inverse_text)
        pad = self._px(9)
        bounds = self.screen.get_rect().inflate(-self._px(8), -self._px(8))
        rect = pygame.Rect(self.mouse_pos[0] + self._px(12), self.mouse_pos[1] + self._px(18),
                           min(image.get_width() + pad * 2, bounds.width), image.get_height() + pad * 2)
        rect.clamp_ip(bounds)
        pygame.draw.rect(self.screen, self.theme.text, rect, border_radius=self._px(8))
        clip = self.screen.get_clip()
        self.screen.set_clip(rect)
        self.screen.blit(image, (rect.x + pad, rect.y + pad))
        self.screen.set_clip(clip)

    def _text(
        self,
        text: str,
        position: tuple[int, int],
        size: int,
        color: tuple[int, int, int],
        *,
        center: bool = False,
        middle: bool = False,
        bottom: bool = False,
        bold: bool = False,
        role: str = "ui",
        max_width: int | None = None,
        min_size: int = 7,
        right: bool = False,
    ) -> pygame.Rect:
        pixel_size = self._px(size)
        minimum = min(pixel_size, self._px(min_size))
        image = self.fonts.render(str(text), pixel_size, color, bold, role=role)
        while (
            max_width is not None
            and image.get_width() > max_width
            and pixel_size > minimum
        ):
            pixel_size -= 1
            image = self.fonts.render(str(text), pixel_size, color, bold, role=role)
        if max_width is not None and image.get_width() > max_width:
            # Preserve an explicit indication of truncation after reaching the
            # readable minimum size, instead of drawing over adjacent controls.
            source = str(text)
            low, high = 0, len(source)
            while low < high:
                middle_index = (low + high + 1) // 2
                candidate = self.fonts.render(source[:middle_index] + "…", pixel_size, color, bold, role=role)
                if candidate.get_width() <= max_width:
                    low = middle_index
                else:
                    high = middle_index - 1
            image = self.fonts.render(source[:low] + "…", pixel_size, color, bold, role=role)
            if image.get_width() > max_width:
                image = image.subsurface((0, 0, max(0, max_width), image.get_height()))
        rect = image.get_rect()
        if right:
            rect.topright = position
        elif center and middle:
            rect.center = position
        elif center and bottom:
            rect.midbottom = position
        elif center:
            rect.midtop = position
        elif middle:
            rect.midleft = position
        else:
            rect.topleft = position
        self.screen.blit(image, rect)
        return rect
