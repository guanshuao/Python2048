"""SDL/DPI 初始化、窗口管理，以及逻辑坐标到实际像素的转换。"""

from __future__ import annotations

import ctypes
import os


# 这些环境变量必须在导入 pygame/SDL 之前设置。
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
if os.name == "nt":
    # SDL 跟踪各显示器的 DPI；下面的 Win32 调用为旧后端提供兼容。
    os.environ.setdefault("SDL_WINDOWS_DPI_AWARENESS", "permonitorv2")


def _enable_high_dpi_awareness() -> float:
    """Opt into native Windows pixels before SDL creates the application window."""

    if os.name != "nt":
        return 1.0
    try:
        # -4 是 Windows 预定义的 PER_MONITOR_AWARE_V2 句柄，不是内存地址。
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except (AttributeError, OSError):
                pass
    try:
        return max(
            1.0,
            min(4.0, ctypes.windll.user32.GetDpiForSystem() / 96.0),
        )
    except (AttributeError, OSError, TypeError, ValueError):
        return 1.0


SYSTEM_DPI_SCALE = _enable_high_dpi_awareness()

import pygame

from config import AppConfig


def _fit_to_desktop(width: int, height: int) -> tuple[int, int]:
    desktop_sizes = pygame.display.get_desktop_sizes()
    if not desktop_sizes:
        return width, height
    desktop_width, desktop_height = desktop_sizes[0]
    scale = min(
        1.0,
        desktop_width * 0.94 / max(1, width),
        desktop_height * 0.90 / max(1, height),
    )
    return round(width * scale), round(height * scale)


def create_display(
    config: AppConfig,
    display_scale: float,
    screenshot: str | None,
    ui_scale: float | None,
) -> tuple[pygame.Window | None, pygame.Surface]:
    """Initialize pygame and create the native window or display fallback."""

    if screenshot:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    os.environ.setdefault("SDL_VIDEO_CENTERED", "1")
    pygame.init()

    window_width = round(config.window_width * display_scale)
    window_height = round(config.window_height * display_scale)
    if not screenshot:
        window_width, window_height = _fit_to_desktop(
            window_width, window_height
        )

    window: pygame.Window | None = None
    try:
        window = pygame.Window(
            title="2048 · AI Lab",
            size=(window_width, window_height),
            position=pygame.WINDOWPOS_CENTERED,
            resizable=True,
            allow_high_dpi=True,
            hidden=bool(screenshot),
        )
        window.minimum_size = (
            config.min_window_width,
            config.min_window_height,
        )
        screen = window.get_surface()
    except (AttributeError, TypeError, pygame.error):
        # 部分旧 SDL / 无界面后端不支持 Window，清理后回退到 display。
        if window is not None:
            window.destroy()
            window = None
        pygame.display.set_caption("2048 · AI Lab")
        if ui_scale is None and not screenshot:
            window_width = round(window_width * SYSTEM_DPI_SCALE)
            window_height = round(window_height * SYSTEM_DPI_SCALE)
            window_width, window_height = _fit_to_desktop(
                window_width, window_height
            )
        screen = pygame.display.set_mode(
            (window_width, window_height), pygame.RESIZABLE
        )
    return window, screen


class DisplayMixin:
    """Display operations for a host with ``window``, ``screen`` and ``_layout``."""

    def _flip(self) -> None:
        if self.window is not None:
            self.window.flip()
        else:
            pygame.display.flip()

    def _logical_window_size(self) -> tuple[int, int]:
        if self.window is not None:
            return tuple(int(value) for value in self.window.size)
        try:
            return tuple(int(value) for value in pygame.display.get_window_size())
        except pygame.error:
            return self.screen.get_size()

    @staticmethod
    def _scale_point(
        position: tuple[float, float],
        logical_size: tuple[int, int],
        surface_size: tuple[int, int],
    ) -> tuple[int, int]:
        """Map SDL logical-window coordinates to native surface pixels."""

        logical_width, logical_height = logical_size
        surface_width, surface_height = surface_size
        return (
            round(float(position[0]) * surface_width / max(1, logical_width)),
            round(float(position[1]) * surface_height / max(1, logical_height)),
        )

    def _surface_point(self, position: tuple[float, float]) -> tuple[int, int]:
        return self._scale_point(
            position, self._logical_window_size(), self.screen.get_size()
        )

    def _sync_window_surface(self) -> None:
        if self.window is not None:
            self.screen = self.window.get_surface()
        self._layout()

    def _resize_display(self, size: tuple[int, int]) -> None:
        """通过当前窗口后端调整尺寸并重建布局。"""

        width = max(1, int(size[0]))
        height = max(1, int(size[1]))
        if self.window is not None:
            self.window.size = (width, height)
            self.screen = self.window.get_surface()
        else:
            self.screen = pygame.display.set_mode(
                (width, height), pygame.RESIZABLE
            )
        self._layout()
