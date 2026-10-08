"""2048 会话、随机落子与撤销；同时兼容原有 ``from game import`` 规则接口。"""

from __future__ import annotations

import random
from collections.abc import Iterable
from dataclasses import dataclass

from game_rules import (
    Board,
    Cell,
    DIRECTIONS,
    Direction,
    MoveResult,
    SPAWN_DISTRIBUTION,
    SPAWN_TWO_PROBABILITY,
    SpawnOutcome,
    TileMotion,
    _as_integer,
    _direction,
    _empty_cells_normalized,
    _is_over_normalized,
    _move_board_normalized,
    _with_tile,
    legal_moves,
    move_board,
    normalize_board,
    simulate_move,
    spawn_outcomes,
)
from number_format import format_integer


__all__ = [
    "Board",
    "Cell",
    "Direction",
    "DIRECTIONS",
    "SPAWN_DISTRIBUTION",
    "SPAWN_TWO_PROBABILITY",
    "TileMotion",
    "MoveResult",
    "SpawnedTile",
    "SpawnOutcome",
    "StepResult",
    "normalize_board",
    "move_board",
    "simulate_move",
    "legal_moves",
    "spawn_outcomes",
    "Grid",
    "Game",
]


@dataclass(frozen=True, slots=True)
class SpawnedTile:
    row: int
    col: int
    value: int

    @property
    def cell(self) -> Cell:
        return self.row, self.col


@dataclass(frozen=True, slots=True)
class StepResult:
    board: Board
    moved: bool
    score_gain: int
    spawned: SpawnedTile | None
    state: str
    merged_cells: tuple[Cell, ...] = ()
    motions: tuple[TileMotion, ...] = ()


@dataclass(frozen=True, slots=True)
class _GameSnapshot:
    board: Board
    score: int
    moves: int
    state: str
    won_once: bool
    rng_state: object


def _spawn_random_tile_normalized(
    board: Board, rng: random.Random
) -> tuple[Board, SpawnedTile | None]:
    cells = _empty_cells_normalized(board)
    if not cells:
        return board, None
    row, col = rng.choice(cells)
    value = (
        SPAWN_DISTRIBUTION[0][0]
        if rng.random() < SPAWN_TWO_PROBABILITY
        else SPAWN_DISTRIBUTION[1][0]
    )
    return _with_tile(board, row, col, value), SpawnedTile(row, col, value)


def _validated_target(value: int) -> int:
    target = _as_integer(value, "target must be an integer power of two")
    if target < 2 or target & (target - 1):
        raise ValueError("target must be a power of two starting at 2")
    return target


class Grid:
    """Mutable board state used by :class:`Game`."""

    def __init__(
        self,
        size: int = 4,
        tiles: Iterable[Iterable[int]] | None = None,
        rng: random.Random | None = None,
    ) -> None:
        normalized_size = _as_integer(size, "grid size must be an integer")
        if normalized_size < 2:
            raise ValueError("grid size must be at least 2")
        if rng is not None and not isinstance(rng, random.Random):
            raise ValueError("rng must be a random.Random instance or None")
        self.size = normalized_size
        self.rng = random.Random() if rng is None else rng
        board = (
            normalize_board(tiles)
            if tiles is not None
            else ((0,) * self.size,) * self.size
        )
        if len(board) != self.size:
            raise ValueError("grid size does not match tiles")
        self.tiles = [list(row) for row in board]

    def snapshot(self) -> Board:
        # tiles 可直接改值，但改阶数应通过重新构造 Grid 或 Game.start。
        board = normalize_board(self.tiles)
        if len(board) != self.size:
            raise ValueError("grid size does not match tiles")
        return board

    @property
    def max_tile(self) -> int:
        return max(map(max, self.snapshot()))

    def add_random_tile(self) -> SpawnedTile | None:
        board = self.snapshot()
        try:
            rng_state = self.rng.getstate()
        except NotImplementedError:
            # Grid 本身不需要撤销，SystemRandom 等无状态随机源仍可落子。
            rng_state = None
        try:
            next_board, spawned = _spawn_random_tile_normalized(board, self.rng)
            next_tiles = [list(row) for row in next_board]
        except Exception:
            if rng_state is not None:
                self.rng.setstate(rng_state)
            raise
        self.tiles = next_tiles
        return spawned

    def move(self, direction: str | int) -> MoveResult:
        result = _move_board_normalized(
            self.snapshot(), _direction(direction), track_motions=True
        )
        self.tiles = [list(row) for row in result.board]
        return result

    def is_over(self) -> bool:
        return _is_over_normalized(self.snapshot())

    def is_win(self, target: int = 2048) -> bool:
        return self.max_tile >= _validated_target(target)

    def __str__(self) -> str:
        labels = [
            [format_integer(value) if value else "" for value in row]
            for row in self.snapshot()
        ]
        width = max(4, max(len(label) for row in labels for label in row))
        border = "+" + "+".join("-" * (width + 2) for _ in range(self.size)) + "+"
        rows = [border]
        for row in labels:
            rows.append(
                "|" + "|".join(f" {label:>{width}} " for label in row) + "|"
            )
            rows.append(border)
        return "\n".join(rows)


class Game:
    """Stateful session with deterministic spawning and undo.

    ``best_score`` is the highest score reached by this Game instance, including
    rounds reset with ``start``; undo never reduces it. ``best_tile`` reports the
    current board's maximum, so it can decrease after undo or a new round.
    """

    def __init__(
        self,
        grid_size: int = 4,
        target: int = 2048,
        rng: random.Random | int | None = None,
        history_limit: int = 32,
    ) -> None:
        self.target = _validated_target(target)
        if isinstance(rng, random.Random):
            self.rng = rng
        else:
            seed = None if rng is None else _as_integer(
                rng, "rng must be a random.Random instance, integer seed or None"
            )
            self.rng = random.Random(seed)
        self.history_limit = _as_integer(
            history_limit, "history_limit must be a positive integer"
        )
        if self.history_limit < 1:
            raise ValueError("history_limit must be a positive integer")
        self.best_score = 0
        self._history: list[_GameSnapshot] = []
        # 构造入口必须提供阶数；start(None) 只用于重开已有棋局。
        self.start(_as_integer(grid_size, "grid size must be an integer"))

    @property
    def grid_size(self) -> int:
        return self.grid.size

    @property
    def best_tile(self) -> int:
        return self.grid.max_tile

    @property
    def can_undo(self) -> bool:
        return bool(self._history)

    def start(self, size: int | None = None) -> Grid:
        next_size = (
            _as_integer(size, "grid size must be an integer")
            if size is not None
            else self.grid_size
        )
        if next_size < 2:
            raise ValueError("grid size must be at least 2")
        # 先构造新棋盘；失败时同时恢复随机数状态，避免破坏当前会话。
        try:
            rng_state = self.rng.getstate()
        except NotImplementedError as exc:
            raise ValueError("game rng must support getstate/setstate for undo") from exc
        try:
            next_grid = Grid(next_size, rng=self.rng)
            next_grid.add_random_tile()
            next_grid.add_random_tile()
        except Exception:
            self.rng.setstate(rng_state)
            raise

        self.grid = next_grid
        self.score = 0
        self.moves = 0
        self.state = "running"
        self.won_once = False
        self._history.clear()
        if self.grid.is_win(self.target):
            self.state = "won"
            self.won_once = True
        return self.grid

    def _snapshot(self, board: Board) -> _GameSnapshot:
        return _GameSnapshot(
            board,
            self.score,
            self.moves,
            self.state,
            self.won_once,
            self.rng.getstate(),
        )

    def step(self, direction: str | int) -> StepResult:
        normalized_direction = _direction(direction)
        # tiles 仍允许外部修改，因此只在单步内部复用已校验的不可变快照。
        board = self.grid.snapshot()
        if self.state != "running":
            return StepResult(board, False, 0, None, self.state)

        move = _move_board_normalized(board, normalized_direction, track_motions=True)
        if not move.moved:
            if _is_over_normalized(board):
                self.state = "over"
            return StepResult(move.board, False, 0, None, self.state)

        before = self._snapshot(board)
        # 随机落子成功后一次提交棋盘，失败时保持会话和随机状态可重放。
        try:
            next_board, spawned = _spawn_random_tile_normalized(move.board, self.rng)
            next_tiles = [list(row) for row in next_board]
        except Exception:
            self.rng.setstate(before.rng_state)
            raise

        self.grid.tiles = next_tiles
        self._history.append(before)
        if len(self._history) > self.history_limit:
            del self._history[0]
        self.score += move.score_gain
        self.best_score = max(self.best_score, self.score)
        self.moves += 1

        if not self.won_once and any(
            value >= self.target for row in next_board for value in row
        ):
            self.won_once = True
            self.state = "won"
        elif _is_over_normalized(next_board):
            self.state = "over"

        return StepResult(
            board=next_board,
            moved=True,
            score_gain=move.score_gain,
            spawned=spawned,
            state=self.state,
            merged_cells=move.merged_cells,
            motions=move.motions,
        )

    def undo(self) -> bool:
        if not self._history:
            return False
        previous = self._history.pop()
        self.grid = Grid(len(previous.board), previous.board, self.rng)
        self.score = previous.score
        self.moves = previous.moves
        self.state = previous.state
        self.won_once = previous.won_once
        # 撤销也恢复随机数状态，同一步重做应产生相同的新方块。
        self.rng.setstate(previous.rng_state)
        return True

    def continue_after_win(self) -> bool:
        if self.state != "won":
            return False
        self.state = "over" if self.grid.is_over() else "running"
        return True
