"""响应式布局：宽屏与紧凑模式共用控件，只有设计尺寸不同。"""

from __future__ import annotations

import pygame

from ui_models import Button


class LayoutMixin:
    """Lay out a host providing screen/config and display/control callbacks."""

    def _layout(self) -> None:
        width, height = self.screen.get_size()
        logical_width, logical_height = self._logical_window_size()
        aspect = logical_width / max(1, logical_height)
        if (
            logical_width >= self.config.wide_min_width
            and logical_height >= self.config.wide_min_height
            and aspect >= self.config.wide_min_aspect
        ):
            self.layout_mode = "wide"
            base_width, base_height = 1100, 760
        elif (
            aspect >= self.config.wide_min_aspect
            or logical_height < self.config.wide_min_height
        ):
            self.layout_mode = "compact_landscape"
            base_width, base_height = 800, 420
        else:
            self.layout_mode = "portrait"
            base_width, base_height = 420, 800

        self.ui_scale = max(
            0.72,
            min(4.0, width / max(1, base_width), height / max(1, base_height)),
        )
        unit = self.ui_scale
        margin = max(8, round((28 if self.layout_mode == "wide" else 16) * unit))
        gap = max(7, round((24 if self.layout_mode == "wide" else 14) * unit))

        if self.layout_mode == "wide":
            panel_width = max(
                round(286 * unit),
                min(round(320 * unit), round(width * 0.31)),
            )
            board_size = min(
                height - margin * 2,
                width - margin * 2 - gap - panel_width,
                round(700 * unit),
            )
            board_size = max(1, board_size)
            content_width = board_size + gap + panel_width
            content_left = (width - content_width) // 2
            content_top = (height - board_size) // 2
            self.board_rect = pygame.Rect(
                content_left, content_top, board_size, board_size
            )
            self.panel_rect = pygame.Rect(
                self.board_rect.right + gap,
                content_top,
                panel_width,
                board_size,
            )
        elif self.layout_mode == "portrait":
            desired_panel_height = round(390 * unit)
            available_height = max(2, height - margin * 2 - gap)
            board_size = min(
                width - margin * 2,
                round(540 * unit),
                available_height - desired_panel_height,
            )
            if board_size < round(170 * unit):
                board_size = min(
                    width - margin * 2,
                    round(available_height * 0.46),
                )
            board_size = max(1, board_size)
            self.board_rect = pygame.Rect(
                (width - board_size) // 2, margin, board_size, board_size
            )
            panel_top = self.board_rect.bottom + gap
            self.panel_rect = pygame.Rect(
                margin,
                panel_top,
                width - margin * 2,
                height - margin - panel_top,
            )
        else:
            board_size = min(
                height - margin * 2,
                round(width * 0.43),
                round(360 * unit),
            )
            board_size = max(1, board_size)
            self.board_rect = pygame.Rect(
                margin, (height - board_size) // 2, board_size, board_size
            )
            panel_left = self.board_rect.right + gap
            self.panel_rect = pygame.Rect(
                panel_left,
                margin,
                width - margin - panel_left,
                height - margin * 2,
            )

        self._layout_panel(compact=self.layout_mode != "wide")
        self._layout_modal()
        self.shadow_cache.clear()
        self._refresh_buttons()

    def _layout_panel(self, compact: bool) -> None:
        panel = self.panel_rect
        unit = self.ui_scale
        pad = max(8 if compact else 10, round((14 if compact else 20) * unit))
        left, inner = panel.x + pad, max(1, panel.width - pad * 2)

        def y(value: float) -> int:
            return panel.y + round(value * unit)

        def h(value: float) -> int:
            return max(1, round(value * unit))

        self.title_position = (left, y(5 if compact else 12))
        self.subtitle_position = (left, y(64))
        self.section_label_positions = {
            "size": (left, y(110 if compact else 161)),
            "strength": (left, y(256 if compact else 411)),
            "speed": (left, y(310 if compact else 481)),
        }
        stat_gap = h(6 if compact else 7)
        stat_width = max(1, (inner - stat_gap * 2) // 3)
        self.stats_rects = {
            name: pygame.Rect(
                left + index * (stat_width + stat_gap),
                y(53 if compact else 82),
                stat_width,
                h(47 if compact else 68),
            )
            for index, name in enumerate(("score", "best", "moves"))
        }
        control_h = h(34 if compact else 43)
        control_gap = h(8 if compact else 10)
        half = max(1, (inner - control_gap) // 2)
        third_gap = h(6)
        third = max(1, (inner - third_gap * 2) // 3)
        side_button = h(34 if compact else 42)
        size_inset = h(42 if compact else 50)
        size_y = y(127 if compact else 183)
        self.size_value_rect = pygame.Rect(
            left + size_inset,
            size_y,
            max(1, inner - size_inset * 2),
            control_h,
        )
        self.buttons = {
            "help": Button(
                "?",
                pygame.Rect(
                    left + inner - h(30), y(8 if compact else 16), h(30), h(30)
                ),
            ),
            "size_down": Button(
                "−", pygame.Rect(left, size_y, side_button, control_h)
            ),
            "size_up": Button(
                "+",
                pygame.Rect(
                    left + inner - side_button,
                    size_y,
                    side_button,
                    control_h,
                ),
            ),
            "new_game": Button(
                "新游戏",
                pygame.Rect(left, y(170 if compact else 244), half, control_h),
                "primary",
            ),
            "undo": Button(
                "撤销",
                pygame.Rect(left + half + control_gap, y(170 if compact else 244), half, control_h),
            ),
        }
        # 紧凑模式把 AI 控件放在同一行；宽屏采用两行，其他控件共用布局。
        for index, (action, label, style) in enumerate((
            ("auto", "自动", "ai"),
            ("hint", "提示", "secondary"),
            ("single", "AI 单步", "secondary"),
        )):
            if compact:
                rect = pygame.Rect(left + index * (third + third_gap), y(213), third, control_h)
            elif action == "single":
                rect = pygame.Rect(left, y(354), inner, control_h)
            else:
                rect = pygame.Rect(left + index * (half + control_gap), y(299), half, control_h)
            self.buttons[action] = Button(label, rect, style)

        level_count = len(self.config.ai_levels)
        level_width = max(1, (inner - third_gap * (level_count - 1)) // level_count)
        for index, level in enumerate(self.config.ai_levels):
            self.buttons[f"strength_{index}"] = Button(
                level.label,
                pygame.Rect(
                    left + index * (level_width + third_gap),
                    y(273 if compact else 435),
                    level_width,
                    h(29 if compact else 35),
                ),
            )
        speed_button = h(29 if compact else 34)
        speed_y = y(326 if compact else 505)
        self.buttons["speed_down"] = Button(
            "−", pygame.Rect(left, speed_y, speed_button, speed_button)
        )
        self.buttons["speed_up"] = Button(
            "+",
            pygame.Rect(
                left + inner - speed_button,
                speed_y,
                speed_button,
                speed_button,
            ),
        )
        speed_inset = h(42 if compact else 48)
        self.speed_track = pygame.Rect(
            left + speed_inset,
            y(338 if compact else 518),
            max(1, inner - speed_inset * 2),
            h(5),
        )
        if compact:
            hint_left = left + h(88)
            self.hint_card = pygame.Rect(
                hint_left, y(8), max(1, left + inner - h(38) - hint_left), h(36)
            )
        else:
            self.hint_card = pygame.Rect(left, y(558), inner, h(70))

    def _layout_modal(self) -> None:
        """Keep dialog hit areas current before input, rather than during drawing."""
        key = (self.modal, self.screen.get_size(), self.ui_scale)
        if self._modal_layout_key == key:
            return
        self._modal_layout_key = key
        if self.modal is None:
            self.modal_buttons = {}
            return

        screen = self.screen.get_rect()
        margin = self._px(14)
        help_dialog = self.modal == "help"
        width = min(self._px(480 if help_dialog else 430), max(1, screen.width - margin * 2))
        gap = self._px(12)
        inset = self._px(20) if help_dialog else min(
            self._px(36), max(self._px(18), round(width * 0.085))
        )
        button_width = max(1, (width - inset * 2 - gap) // 2)
        stacked = not help_dialog and button_width < self._px(112)
        height = min(
            self._px(430 if help_dialog else 340 if stacked else 292),
            max(1, screen.height - margin * 2),
        )
        card = pygame.Rect(0, 0, width, height)
        card.center = screen.center
        self.modal_card_rect = card
        self.modal_text_width = max(1, width - inset * 2)
        if help_dialog:
            rect = pygame.Rect(
                card.x + inset, card.bottom - self._px(56),
                self.modal_text_width, self._px(38),
            )
            self.modal_buttons = {
                "modal_dismiss": Button("知道了 · Enter / Esc", rect, "primary")
            }
        else:
            button_height = self._px(44)
            if stacked:
                second = pygame.Rect(
                    card.x + inset, card.bottom - self._px(24) - button_height,
                    self.modal_text_width, button_height,
                )
                first = second.move(0, -gap - button_height)
            else:
                first = pygame.Rect(
                    card.x + inset, card.bottom - self._px(76), button_width, button_height
                )
                second = first.move(button_width + gap, 0)
            actions = (
                (("modal_continue", "继续挑战"), ("modal_restart", "新游戏"))
                if self.modal == "win" else
                (("modal_restart", "再来一局"), ("modal_dismiss", "查看棋盘"))
            )
            self.modal_buttons = {
                action: Button(label, rect, "primary" if number == 0 else "secondary")
                for number, ((action, label), rect) in enumerate(zip(actions, (first, second)))
            }
        if self.focus_action not in self.modal_buttons:
            self.focus_action = None

    def _px(self, logical_pixels: float) -> int:
        """Convert a design-space measurement to native surface pixels."""

        return max(1, round(logical_pixels * self.ui_scale))
