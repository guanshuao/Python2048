"""应用控制器：处理输入、动画时序和 AI 请求，布局与绘制交给 UI 模块。"""

from __future__ import annotations

import math
import operator
import random
import time
from collections.abc import Sequence
from pathlib import Path

# 必须先设置 SDL/DPI，再导入 pygame，否则高分屏窗口可能被重复缩放。
from ui_display import DisplayMixin, create_display

import pygame

from ai_worker import AIRequest, AIResponse, AIWorker
from app_cli import parse_args
from config import AppConfig, Theme
from game import Board, Game, StepResult
from number_format import format_integer
from ui_fonts import FontBook
from ui_layout import LayoutMixin
from ui_models import (
    BoardLayer,
    Button,
    DIRECTION_LABELS,
    KEY_DIRECTIONS,
    MoveAnimation,
    PendingMove,
    ScoreBurst,
    TileLayer,
    TilePulse,
)
from ui_renderer import RendererMixin


__all__ = ["Main", "AIRequest", "AIResponse", "AIWorker", "parse_args", "main"]


class Main(DisplayMixin, LayoutMixin, RendererMixin):
    """Application controller. ``Main().start()`` remains the supported API."""

    def __init__(
        self,
        config: AppConfig | None = None,
        theme: Theme | None = None,
        *,
        size: int | None = None,
        seed: int | None = None,
        screenshot: str | None = None,
        ui_scale: float | None = None,
    ) -> None:
        self.config = config or AppConfig()
        self.theme = theme or Theme()
        requested_size = self.config.default_size if size is None else size
        self.size = self.config.clamp_size(requested_size)
        self.selected_size = self.size
        if seed is not None:
            if isinstance(seed, bool):
                raise ValueError("seed must be an integer or None")
            try:
                seed = operator.index(seed)
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError("seed must be an integer or None") from exc
        self.rng = random.Random(seed)
        if screenshot is not None and (
            not isinstance(screenshot, str) or not screenshot.strip()
        ):
            raise ValueError("screenshot path must be a non-empty string or None")
        self.screenshot_path = screenshot
        # 窗口使用逻辑像素；实际像素倍率由 SDL 提供，不能再手动乘系统 DPI。
        if isinstance(ui_scale, bool):
            raise ValueError("ui_scale must be a positive finite number")
        try:
            requested_scale = 1.0 if ui_scale is None else float(ui_scale)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("ui_scale must be a positive finite number") from exc
        if not math.isfinite(requested_scale) or requested_scale <= 0:
            raise ValueError("ui_scale must be a positive finite number")
        self.display_scale = max(0.75, min(4.0, requested_scale))
        self.ui_scale = 1.0

        self.window, self.screen = create_display(
            self.config, self.display_scale, screenshot, ui_scale
        )
        self.clock = pygame.time.Clock()
        self.fonts = FontBook()
        self.shadow_cache: dict[tuple, pygame.Surface] = {}
        self.board_layer: BoardLayer | None = None
        self.tile_layer: TileLayer | None = None
        self._snapshot_cache: tuple[int, Board] | None = None
        self.modal_overlay: tuple[
            tuple[int, int], tuple[int, int, int, int], pygame.Surface
        ] | None = None
        self.running = True

        self.game = self._make_game(self.size)
        self.board_revision = 0
        self.ai_generation = 0
        self.ai_request_id = 0
        self.ai_inflight: AIRequest | None = None
        self.ai_inflight_cancelled = False
        self.worker = AIWorker()

        self.auto_enabled = False
        self.hint_enabled = False
        self.hint_direction: str | None = None
        self.hint_revision = -1
        self.ai_level = self.config.default_ai_level
        self.speed_level = self.config.default_auto_speed
        self.next_auto_at = 0.0
        self.search_status = "AI 已就绪"
        self.search_detail = ""
        self.modal: str | None = None
        self.pending_modal: str | None = None
        self.move_animation: MoveAnimation | None = None
        self.pending_move: PendingMove | None = None
        self.tile_pulses: dict[tuple[int, int], TilePulse] = {}
        self.score_bursts: list[ScoreBurst] = []

        self.mouse_pos = (0, 0)
        self.pressed_action: str | None = None
        self.drag_start: tuple[int, int] | None = None
        self.speed_dragging = False
        self.focus_action: str | None = None
        self.modal_buttons: dict[str, Button] = {}
        self._modal_layout_key: tuple | None = None
        # 几何和普通按钮统一由布局模块创建，无需先填入会立即覆盖的占位值。
        self._layout()
        self._sync_modal()

    def _make_game(self, size: int) -> Game:
        return Game(size, target=self.config.target, rng=self.rng)

    def _snapshot(self) -> Board:
        # Main owns all board mutations. External Game/Grid callers still get
        # full validation; UI frames reuse a snapshot until its revision changes.
        if self._snapshot_cache is None or self._snapshot_cache[0] != self.board_revision:
            self._snapshot_cache = (self.board_revision, self.game.grid.snapshot())
        return self._snapshot_cache[1]

    def start(self) -> None:
        try:
            if self.screenshot_path:
                self.render()
                self._flip()
                path = Path(self.screenshot_path).expanduser().resolve()
                path.parent.mkdir(parents=True, exist_ok=True)
                pygame.image.save(self.screen, str(path))
                print(f"Screenshot saved to {path}")
                return
            self.run()
        finally:
            self.worker.close()
            if self.window is not None:
                self.window.destroy()
                self.window = None
            pygame.quit()

    def run(self) -> None:
        while self.running:
            self.update()
            self.render()
            self._flip()
            self.clock.tick(self.config.fps)

    def update(self) -> None:
        """Process input before queued actions, including at animation boundaries."""
        self.handle_events()
        self._advance_move_animation()
        self._advance_effects()
        self._poll_ai()
        self._schedule_ai()

    def _refresh_buttons(self) -> None:
        if not self.buttons:
            return
        for action, label, enabled in (
            ("auto", "自动", self.auto_enabled),
            ("hint", "提示", self.hint_enabled),
        ):
            self.buttons[action].label = f"{label}：{'开' if enabled else '关'}"
            self.buttons[action].selected = enabled
        self.buttons["undo"].enabled = self.game.can_undo
        ai_controls_enabled = (
            self.modal is None
            and self.pending_modal is None
            and self.game.state == "running"
        )
        self.buttons["auto"].enabled = ai_controls_enabled
        self.buttons["hint"].enabled = ai_controls_enabled
        self.buttons["single"].enabled = ai_controls_enabled and self.ai_inflight is None
        self.buttons["size_down"].enabled = self.selected_size > self.config.min_size
        self.buttons["size_up"].enabled = self.selected_size < self.config.max_size
        for index in range(len(self.config.ai_levels)):
            self.buttons[f"strength_{index}"].selected = index == self.ai_level

    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type in (pygame.QUIT, pygame.WINDOWCLOSE):
                self.running = False
            elif event.type == pygame.VIDEORESIZE:
                if self.window is None:
                    self._resize_display((
                        max(self.config.min_window_width, event.w),
                        max(self.config.min_window_height, event.h),
                    ))
                else:
                    self._sync_window_surface()
            elif event.type in (
                pygame.WINDOWRESIZED,
                pygame.WINDOWSIZECHANGED,
                pygame.WINDOWDISPLAYCHANGED,
                pygame.WINDOWMOVED,
            ):
                # 跨显示器时像素倍率可能变化，必须重新获取绘图表面。
                self._sync_window_surface()
            elif event.type == pygame.MOUSEMOTION:
                self.mouse_pos = self._surface_point(event.pos)
                if self.speed_dragging and self.modal is None:
                    self._set_speed_from_x(self.mouse_pos[0])
            elif event.type == pygame.WINDOWFOCUSLOST:
                self.speed_dragging = False
                self.drag_start = None
                self.pressed_action = None
                # 切换窗口只清理手动输入，后台 AI 对局继续执行。
                if self.pending_move and self.pending_move.source == "manual":
                    self.pending_move = None
            elif event.type == pygame.KEYDOWN:
                self._key_down(event)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                position = self._surface_point(event.pos)
                self.mouse_pos = position
                self.focus_action = None
                self.pressed_action = self._action_at(position)
                if self.board_rect.collidepoint(position) and self.modal is None:
                    self.drag_start = position
                if (
                    self.modal is None
                    and self.speed_track.inflate(0, self._px(22)).collidepoint(position)
                ):
                    self.speed_dragging = True
                    self.drag_start = None
                    self._set_speed_from_x(position[0])
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                position = self._surface_point(event.pos)
                self.mouse_pos = position
                action = self._action_at(position)
                if self.speed_dragging:
                    self._set_speed_from_x(position[0])
                elif action is not None and action == self.pressed_action:
                    self._activate(action)
                elif self.drag_start and self.modal is None:
                    self._finish_swipe(position)
                self.pressed_action = None
                self.drag_start = None
                self.speed_dragging = False

    def _key_down(self, event: pygame.event.Event) -> None:
        self._layout_modal()
        if event.key == pygame.K_ESCAPE:
            if self.modal:
                self._activate("modal_continue" if self.modal == "win" else "modal_dismiss")
            else:
                self.running = False
            return
        if event.key == pygame.K_TAB:
            source = self.modal_buttons if self.modal else self.buttons
            actions = [name for name, button in source.items() if button.enabled]
            if actions:
                step = -1 if getattr(event, "mod", 0) & pygame.KMOD_SHIFT else 1
                current = (
                    actions.index(self.focus_action)
                    if self.focus_action in actions else (-1 if step == 1 else 0)
                )
                self.focus_action = actions[(current + step) % len(actions)]
            return
        if self.modal:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if self.focus_action in self.modal_buttons:
                    self._activate(self.focus_action)
                else:
                    self._activate(
                        "modal_continue" if self.modal == "win"
                        else "modal_dismiss" if self.modal == "help"
                        else "modal_restart"
                    )
            return
        if event.key == pygame.K_F1:
            self._activate("help")
            return
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and self.focus_action:
            self._activate(self.focus_action)
            return
        if event.key in KEY_DIRECTIONS:
            self._pause_auto()
            self.focus_action = None
            self._move(KEY_DIRECTIONS[event.key])
        elif event.key == pygame.K_r:
            self._new_game()
        elif event.key == pygame.K_z:
            self._undo()
        elif event.key in (pygame.K_SPACE, pygame.K_p):
            self._activate("auto")
        elif event.key == pygame.K_h:
            self._activate("hint")
        elif event.key == pygame.K_n:
            self._activate("single")
        elif event.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
            self._activate("speed_up")
        elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self._activate("speed_down")

    def _action_at(self, position: tuple[int, int]) -> str | None:
        self._layout_modal()
        source = self.modal_buttons if self.modal else self.buttons
        return next(
            (action for action, button in source.items() if button.is_click(position)),
            None,
        )

    def _activate(self, action: str) -> None:
        if action in self.buttons and not self.buttons[action].enabled:
            return
        if action in ("size_down", "size_up"):
            delta = 1 if action == "size_up" else -1
            self.selected_size = self.config.clamp_size(self.selected_size + delta)
        elif action in ("new_game", "modal_restart"):
            self._new_game()
        elif action == "undo":
            self._undo()
        elif action in ("auto", "hint"):
            if action == "auto":
                if self.auto_enabled:
                    self._pause_auto("自动已关闭")
                else:
                    self.auto_enabled = True
                self.next_auto_at = 0.0
            else:
                self.hint_enabled = not self.hint_enabled
                if not self.hint_enabled:
                    self.hint_direction = None
                    self.hint_revision = -1
                    self._cancel_ai("hint", "提示已关闭")
        elif action == "single" and self.ai_inflight is None:
            self._request_ai("single")
        elif action.startswith("strength_"):
            self.ai_level = int(action.rsplit("_", 1)[1])
            self.ai_generation += 1
            self.hint_revision = -1
            self.hint_direction = None
            self.search_status = f"AI 强度已切换为{self.config.ai_levels[self.ai_level].label}"
            self.search_detail = ""
        elif action in ("speed_down", "speed_up"):
            delta = 1 if action == "speed_up" else -1
            self.speed_level = max(0, min(len(self.config.auto_delays) - 1, self.speed_level + delta))
        elif action == "modal_continue":
            self.focus_action = None
            self.game.continue_after_win()
            self.pending_modal = None
            self.pending_move = None
            self.modal = "over" if self.game.state == "over" else None
        elif action == "modal_dismiss":
            self.focus_action = None
            if self.modal == "help":
                self.search_status = "AI 已就绪"
                self.search_detail = ""
            self.modal = None
        elif action == "help" and self.modal is None and self.pending_modal is None:
            self._pause_auto()
            self.ai_generation += 1
            self.focus_action = None
            self.pending_move = None
            self.search_status = "已暂停 · 查看操作说明"
            self.search_detail = ""
            self.modal = "help"
        self._refresh_buttons()

    def _new_game(self) -> None:
        self.size = self.selected_size
        self.game = self._make_game(self.size)
        self.board_revision += 1
        self.ai_generation += 1
        self.auto_enabled = False
        self._clear_transient_state("新棋局已开始")
        self._sync_modal()
        self._refresh_buttons()

    def _clear_transient_state(self, status: str) -> None:
        self.focus_action = None
        self.hint_direction = None
        self.hint_revision = -1
        self.modal = None
        self.pending_modal = None
        self.move_animation = None
        self.pending_move = None
        self.tile_pulses.clear()
        self.score_bursts.clear()
        self.search_status = status
        self.search_detail = ""

    def _undo(self) -> None:
        if self.game.undo():
            self._pause_auto()
            self.ai_generation += 1
            self.board_revision += 1
            self._clear_transient_state("已撤销上一步")
            self._refresh_buttons()

    def _pause_auto(self, status: str = "自动已暂停") -> None:
        self.auto_enabled = False
        if self.pending_move and self.pending_move.source == "auto":
            self.pending_move = None
        self._cancel_ai("auto", status)

    def _cancel_ai(self, purpose: str, status: str) -> None:
        """Cancel one purpose while preserving the single in-flight worker slot."""
        if self.ai_inflight is not None and self.ai_inflight.purpose == purpose:
            self.ai_inflight_cancelled = True
            self.search_status = status
            self.search_detail = ""

    def _finish_swipe(self, end: tuple[int, int]) -> None:
        if not self.drag_start:
            return
        dx, dy = end[0] - self.drag_start[0], end[1] - self.drag_start[1]
        if max(abs(dx), abs(dy)) < max(24, self.board_rect.width * 0.035):
            return
        self._pause_auto()
        if abs(dx) > abs(dy):
            self._move("R" if dx > 0 else "L")
        else:
            self._move("D" if dy > 0 else "U")

    def _set_speed_from_x(self, mouse_x: int) -> None:
        fraction = (mouse_x - self.speed_track.left) / max(1, self.speed_track.width)
        last = len(self.config.auto_delays) - 1
        self.speed_level = max(0, min(last, round(fraction * last)))

    def _move(self, direction: str, *, source: str = "manual") -> bool:
        if self.modal or self.game.state != "running":
            return False
        if source == "auto" and not self.auto_enabled:
            return False
        animation = self.move_animation
        if animation is not None:
            if time.monotonic() < animation.started_at + animation.duration:
                # 只保留最近一次快速输入，让当前滑动完整播放后再执行。
                # A manual action takes precedence over a background result.
                if source != "manual" and self.pending_move and self.pending_move.source == "manual":
                    return False
                self.pending_move = PendingMove(
                    direction, source, self.board_revision, self.ai_generation
                )
                return False
            self.move_animation = None
            # The latest input replaces any action queued for the expired slide.
            self.pending_move = None
        result = self.game.step(direction)
        if not result.moved:
            self._sync_modal()
            return False
        self.board_revision += 1
        self.hint_direction = None
        self.hint_revision = -1
        gain = result.score_gain
        self._start_move_animations(result)
        self.search_status = f"+{format_integer(gain)} 分" if gain else "移动完成"
        self._sync_modal()
        now = time.monotonic()
        animation_end = (
            self.move_animation.started_at + self.move_animation.duration
            if self.move_animation is not None
            else now
        )
        self.next_auto_at = max(
            now + self.config.auto_delays[self.speed_level], animation_end + 0.012
        )
        return True

    def _advance_move_animation(self) -> None:
        animation = self.move_animation
        if animation is None:
            return
        if time.monotonic() < animation.started_at + animation.duration:
            return
        self.move_animation = None
        if self.pending_modal is not None:
            self.modal = self.pending_modal
            self.pending_modal = None
            self.pending_move = None
            self._refresh_buttons()
            return
        pending = self.pending_move
        self.pending_move = None
        if pending is None or pending.revision != self.board_revision:
            return
        if pending.source != "manual" and pending.generation != self.ai_generation:
            return
        self._move(pending.direction, source=pending.source)

    def _advance_effects(self) -> None:
        """Expire visual effects in the update phase; rendering stays read-only."""
        now = time.monotonic()
        self.tile_pulses = {
            cell: pulse for cell, pulse in self.tile_pulses.items()
            if now < pulse.started_at + pulse.duration
        }
        self.score_bursts = [
            burst for burst in self.score_bursts
            if now < burst.started_at + burst.duration
        ]

    def _start_move_animations(self, result: StepResult) -> None:
        """Translate StepResult metadata into time-based, non-blocking effects."""

        now = time.monotonic()
        duration = self.config.animation_ms / 1000.0
        if self.auto_enabled:
            # 高速自动模式缩短动画，但仍让每次合并完整显示。
            duration = min(
                duration,
                max(0.045, self.config.auto_delays[self.speed_level] * 0.66),
            )

        if any(motion.moved for motion in result.motions):
            # 静止棋块在下、滑动棋块在上；每次移动排序一次，不必逐帧排序。
            motions = tuple(sorted(result.motions, key=lambda motion: motion.moved))
            self.move_animation = MoveAnimation(motions, now, duration)
            effects_at = now + duration
        else:
            self.move_animation = None
            effects_at = now

        for row, column in result.merged_cells:
            self.tile_pulses[(row, column)] = TilePulse("merge", effects_at, duration)

        spawned = result.spawned
        if spawned is not None:
            self.tile_pulses[spawned.cell] = TilePulse("spawn", effects_at, duration)

        if result.score_gain > 0:
            self.score_bursts.append(
                ScoreBurst(
                    result.score_gain,
                    effects_at,
                    self.config.score_animation_ms / 1000.0,
                )
            )

    def _sync_modal(self) -> None:
        if self.game.state == "running":
            return
        self.focus_action = None
        target = "win" if self.game.state == "won" else "over"
        self.auto_enabled = False
        animation = self.move_animation
        if (
            animation is not None
            and time.monotonic() < animation.started_at + animation.duration
        ):
            self.pending_modal = target
        else:
            self.modal = target

    def _request_ai(self, purpose: str) -> None:
        if (
            self.ai_inflight is not None
            or self.modal
            or self.pending_modal
            or self.game.state != "running"
        ):
            return
        self.ai_request_id += 1
        level = self.config.ai_levels[self.ai_level]
        request = AIRequest(
            self.ai_request_id, self.board_revision, self.ai_generation, purpose,
            self._snapshot(), level.key, level.time_budget_ms,
        )
        self.ai_inflight = request
        self.ai_inflight_cancelled = False
        if purpose == "hint":
            self.hint_direction = None
        self.search_status = "AI 正在思考…"
        self.search_detail = ""
        self.worker.submit(request)
        self._refresh_buttons()

    def _schedule_ai(self) -> None:
        if not self.running or self.pending_move is not None:
            return
        if self.auto_enabled and time.monotonic() >= self.next_auto_at:
            self._request_ai("auto")
        elif self.hint_enabled and self.hint_revision != self.board_revision:
            self._request_ai("hint")

    def _poll_ai(self) -> None:
        while (response := self.worker.poll()) is not None:
            active = self.ai_inflight
            if active is None or response.request.request_id != active.request_id:
                continue
            self.ai_inflight = None
            cancelled = self.ai_inflight_cancelled
            self.ai_inflight_cancelled = False
            request = response.request
            # 棋盘变化或强度切换后，旧线程结果（包括错误）都不能影响新状态。
            if (
                cancelled
                or request.revision != self.board_revision
                or request.generation != self.ai_generation
            ):
                continue
            if request.purpose == "auto" and not self.auto_enabled:
                continue
            if request.purpose == "hint" and not self.hint_enabled:
                continue
            result = response.result
            direction = result.direction if result is not None else None
            if response.error or direction not in DIRECTION_LABELS:
                if request.purpose == "hint":
                    self.hint_direction = None
                if response.error:
                    self.search_status = "AI 暂时不可用"
                    self.search_detail = response.error[:72]
                else:
                    self.search_status = "当前没有可行移动"
                    self._sync_modal()
                if request.purpose == "auto":
                    self.auto_enabled = False
                elif request.purpose == "hint":
                    # 失败后锁定本棋盘版本，避免每帧重试；移动或重开提示会重试。
                    self.hint_revision = self.board_revision
                continue
            self.search_detail = (
                f"深度 {result.depth} · {result.nodes:,} 节点 · "
                f"{result.elapsed_ms:.0f} ms"
            )
            if request.purpose == "hint":
                self.hint_direction = direction
                self.hint_revision = self.board_revision
                self.search_status = f"建议{DIRECTION_LABELS[direction][1]}"
            else:
                self._move(direction, source=request.purpose)
        self._refresh_buttons()


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    Main(
        size=args.size,
        seed=args.seed,
        screenshot=args.screenshot,
        ui_scale=args.ui_scale,
    ).start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
