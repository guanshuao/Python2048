"""AI 后台线程只接收不可变棋盘快照，pygame 状态始终由主线程管理。"""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass

from ai import ExpectimaxAI, SearchResult
from game_rules import Board


@dataclass(frozen=True, slots=True)
class AIRequest:
    request_id: int
    revision: int
    generation: int
    purpose: str
    board: Board
    profile: str
    budget_ms: int


@dataclass(frozen=True, slots=True)
class AIResponse:
    request: AIRequest
    result: SearchResult | None = None
    error: str = ""


class AIWorker:
    """One daemon search thread; pygame state always stays on the main thread."""

    def __init__(self) -> None:
        self.requests: queue.SimpleQueue[AIRequest | None] = queue.SimpleQueue()
        self.responses: queue.SimpleQueue[AIResponse] = queue.SimpleQueue()
        self.closed = threading.Event()
        self.thread = threading.Thread(target=self._run, name="2048-ai", daemon=True)
        self.thread.start()

    def submit(self, request: AIRequest) -> None:
        if self.closed.is_set():
            raise RuntimeError("AI worker is closed")
        self.requests.put(request)

    def poll(self) -> AIResponse | None:
        try:
            return self.responses.get_nowait()
        except queue.Empty:
            return None

    def close(self, timeout: float = 1.0) -> None:
        """停止接收请求；最多等待 timeout 秒，避免退出界面时无限阻塞。"""

        if not self.closed.is_set():
            self.closed.set()
            self.requests.put(None)
        if threading.current_thread() is not self.thread:
            self.thread.join(max(0.0, timeout))

    def _run(self) -> None:
        while True:
            request = self.requests.get()
            if request is None or self.closed.is_set():
                return
            try:
                result = ExpectimaxAI(request.profile).choose_move(
                    request.board, time_budget_ms=request.budget_ms
                )
                self.responses.put(AIResponse(request, result=result))
            except Exception as exc:  # 传回主线程显示错误，避免搜索线程悄悄退出。
                self.responses.put(
                    AIResponse(request, error=f"{type(exc).__name__}: {exc}")
                )
