"""不可变棋盘与确定性的 2048 规则；公开接口同时由 :mod:`game` 导出。"""

from __future__ import annotations

import operator
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache


Board = tuple[tuple[int, ...], ...]
Cell = tuple[int, int]
Direction = str
DIRECTIONS: tuple[Direction, ...] = ("U", "R", "D", "L")
# 游戏落子和 AI 概率节点必须使用同一分布，避免规则随调用路径改变。
SPAWN_DISTRIBUTION: tuple[tuple[int, float], ...] = ((2, 0.9), (4, 0.1))
SPAWN_TWO_PROBABILITY: float = SPAWN_DISTRIBUTION[0][1]


@dataclass(frozen=True, slots=True)
class TileMotion:
    """One source tile travelling to its post-move destination.

    A merge is represented by two motions with the same destination. ``value``
    is the value before the merge, which lets the renderer show both source
    tiles converging before revealing the doubled result.
    """

    source: Cell
    destination: Cell
    value: int
    merged: bool = False

    @property
    def moved(self) -> bool:
        return self.source != self.destination


@dataclass(frozen=True, slots=True)
class MoveResult:
    board: Board
    moved: bool
    score_gain: int
    merged_cells: tuple[Cell, ...] = ()
    motions: tuple[TileMotion, ...] = ()


@dataclass(frozen=True, slots=True)
class SpawnOutcome:
    probability: float
    board: Board


def _direction(value: str | int) -> Direction:
    if not isinstance(value, str):
        index = _as_integer(value, "direction must be a string or an integer")
        if index not in range(len(DIRECTIONS)):
            raise ValueError("direction integer must be between 0 and 3")
        return DIRECTIONS[index]
    direction = value.strip().upper()
    aliases = {
        "UP": "U",
        "RIGHT": "R",
        "DOWN": "D",
        "LEFT": "L",
    }
    direction = aliases.get(direction, direction)
    if direction not in DIRECTIONS:
        raise ValueError("direction must be one of U, R, D or L")
    return direction


def _as_integer(value: object, message: str) -> int:
    if isinstance(value, bool):
        raise ValueError(message)
    try:
        return operator.index(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(message) from exc


def normalize_board(tiles: Iterable[Iterable[int]]) -> Board:
    """Return a validated immutable square board.

    NumPy arrays are accepted through their normal iteration protocol. The
    rules keep Python integers so tile values cannot overflow a fixed dtype.
    """

    def normalize_row(row: Iterable[int]) -> tuple[int, ...]:
        raw_values = row if isinstance(row, tuple) else tuple(row)
        # 保留原生整数元组，落子分支便可共享所有未改变的行。
        if isinstance(row, tuple) and all(type(value) is int for value in raw_values):
            return row
        return tuple(
            _as_integer(value, "tile values must be integers") for value in raw_values
        )

    try:
        raw_rows = tiles if isinstance(tiles, tuple) else tuple(tiles)
        rows = tuple(normalize_row(row) for row in raw_rows)
        board = (
            raw_rows
            if isinstance(tiles, tuple)
            and all(row is raw for row, raw in zip(rows, raw_rows))
            else rows
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("tiles must be a square matrix of integers") from exc
    if not board or any(len(row) != len(board) for row in board):
        raise ValueError("tiles must be a non-empty square matrix")
    for row in board:
        for value in row:
            if value < 0 or value == 1 or (value and value & (value - 1)):
                raise ValueError("tile values must be zero or powers of two starting at 2")
    return board


def _merge_line(
    values: tuple[int, ...],
) -> tuple[tuple[int, ...], int, tuple[int, ...]]:
    """Slide a line toward index zero and merge every tile at most once."""

    compact = [value for value in values if value]
    merged: list[int] = []
    merged_indexes: list[int] = []
    score_gain = 0
    index = 0
    while index < len(compact):
        value = compact[index]
        if index + 1 < len(compact) and compact[index + 1] == value:
            value *= 2
            score_gain += value
            merged_indexes.append(len(merged))
            index += 2
        else:
            index += 1
        merged.append(value)
    line = tuple(merged) + (0,) * (len(values) - len(merged))
    return line, score_gain, tuple(merged_indexes)


# 搜索中的短行大量重复；只缓存长度不超过 8 的行，避免大棋盘挤占缓存。
_merge_short_line = lru_cache(maxsize=8192)(_merge_line)


def _line_cell(direction: Direction, line_index: int, offset: int, size: int) -> Cell:
    if direction == "L":
        return line_index, offset
    if direction == "R":
        return line_index, size - 1 - offset
    if direction == "U":
        return offset, line_index
    return size - 1 - offset, line_index


def _move_board_normalized(
    board: Board,
    direction: Direction,
    *,
    track_motions: bool,
) -> MoveResult:
    """Move an already validated board using the canonical merge rules."""

    size = len(board)
    vertical = direction in ("U", "D")
    reverse = direction in ("R", "D")
    sources = tuple(zip(*board)) if vertical else board
    merge = _merge_short_line if size <= 8 else _merge_line
    output: list[tuple[int, ...]] = []
    score_gain = 0
    merged_cells: list[Cell] = []
    motions: list[TileMotion] = []

    # 四个方向统一为向左合并；行切片与转置避免逐格调用坐标转换。
    for line_index, source in enumerate(sources):
        if reverse:
            source = source[::-1]
        line, line_score, merge_indexes = merge(source)
        score_gain += line_score
        output.append(line[::-1] if reverse else line)
        if track_motions:
            merged_cells.extend(
                _line_cell(direction, line_index, offset, size)
                for offset in merge_indexes
            )
            # 动画只需按合并结果消费一个或两个源格，不再建立中间运动对象。
            occupied = (
                (offset, value) for offset, value in enumerate(source) if value
            )
            for destination, value in enumerate(line):
                if not value:
                    break
                merged = destination in merge_indexes
                for _ in range(2 if merged else 1):
                    offset, source_value = next(occupied)
                    motions.append(
                        TileMotion(
                            _line_cell(direction, line_index, offset, size),
                            _line_cell(direction, line_index, destination, size),
                            source_value,
                            merged,
                        )
                    )

    result_board: Board = tuple(zip(*output)) if vertical else tuple(output)
    moved = result_board != board
    return MoveResult(
        board=result_board if moved else board,
        moved=moved,
        score_gain=score_gain,
        merged_cells=tuple(merged_cells),
        motions=tuple(motions),
    )


def move_board(tiles: Iterable[Iterable[int]], direction: str | int) -> MoveResult:
    """Return one deterministic move, including metadata used by animation."""

    board = normalize_board(tiles)
    return _move_board_normalized(board, _direction(direction), track_motions=True)


def simulate_move(board: Board, direction: Direction) -> MoveResult:
    """Fast canonical move for trusted search nodes, without visual metadata."""

    if direction not in DIRECTIONS:
        raise ValueError("trusted search direction must be U, R, D or L")
    return _move_board_normalized(board, direction, track_motions=False)


def legal_moves(tiles: Iterable[Iterable[int]]) -> tuple[Direction, ...]:
    board = normalize_board(tiles)
    return tuple(
        direction for direction in DIRECTIONS
        if simulate_move(board, direction).moved
    )


def _is_over_normalized(board: Board) -> bool:
    """Check an already validated board without constructing move results."""

    # 非空棋盘只要留有空格就能移动；全零棋盘则没有合法移动。
    if any(0 in row for row in board):
        return not any(any(row) for row in board)
    # 满盘只检查相邻同值格；供会话和 Grid 共用，避免重复扫描和校验。
    return not (
        any(left == right for row in board for left, right in zip(row, row[1:]))
        or any(
            top == bottom
            for upper, lower in zip(board, board[1:])
            for top, bottom in zip(upper, lower)
        )
    )


def _empty_cells_normalized(board: Board) -> tuple[Cell, ...]:
    """Return empty cells from an already validated immutable board."""

    return tuple(
        (row, col)
        for row, values in enumerate(board)
        for col, value in enumerate(values)
        if value == 0
    )


def _with_tile(board: Board, row: int, col: int, value: int) -> Board:
    """Create one outcome while sharing every unchanged immutable row."""

    source_row = board[row]
    changed_row = source_row[:col] + (value,) + source_row[col + 1:]
    return board[:row] + (changed_row,) + board[row + 1:]


def spawn_outcomes(tiles: Iterable[Iterable[int]]) -> tuple[SpawnOutcome, ...]:
    """Enumerate the exact 0.9/0.1 chance distribution for an AI node."""

    board = normalize_board(tiles)
    cells = _empty_cells_normalized(board)
    if not cells:
        return ()
    probability_per_cell = 1.0 / len(cells)
    outcomes: list[SpawnOutcome] = []
    for row, col in cells:
        for value, probability in SPAWN_DISTRIBUTION:
            outcomes.append(
                SpawnOutcome(
                    probability=probability * probability_per_cell,
                    board=_with_tile(board, row, col, value),
                )
            )
    return tuple(outcomes)
