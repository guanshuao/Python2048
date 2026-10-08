"""Expectimax 搜索与预算控制；评分实现位于 ai_heuristic，公开入口保持兼容。"""

from __future__ import annotations

import math
import time
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache

from ai_heuristic import (
    _evaluate,
    _evaluate_cached,
    _exponent_array,
    _snake_arrays,
    evaluate_board,
)
from ai_numeric import evaluate_exponents
from game_rules import (
    Board,
    DIRECTIONS,
    MoveResult,
    SpawnOutcome,
    SPAWN_DISTRIBUTION,
    _empty_cells_normalized,
    _merge_short_line,
    _with_tile,
    normalize_board,
    simulate_move,
)
from search_profiles import AI_PROFILES, SearchSettings, non_negative_integer


__all__ = [
    "SearchSettings",
    "AI_PROFILES",
    "SearchResult",
    "ExpectimaxAI",
    "evaluate_board",
    "clear_search_caches",
]


@dataclass(frozen=True, slots=True)
class SearchResult:
    """A complete description of one AI decision."""

    direction: str | None
    value: float
    depth: int
    nodes: int
    elapsed_ms: float
    move_values: tuple[tuple[str, float], ...] = ()


class _SearchInterrupted(RuntimeError):
    """Internal control flow used when a search budget is exhausted."""


@lru_cache(maxsize=65_536)
def _move_cached(board: Board, direction: str) -> MoveResult:
    return simulate_move(board, direction)


def _search_move(board: Board, direction: str) -> MoveResult:
    return (
        _move_cached(board, direction)
        if len(board) <= 4
        else simulate_move(board, direction)
    )


def clear_search_caches() -> None:
    """性能基准用的冷启动：清空局面/移动/行缓存，正常游玩无需逐步清理。"""

    _evaluate_cached.cache_clear()
    _move_cached.cache_clear()
    _merge_short_line.cache_clear()


def _merge_utility(score_gain: int) -> float:
    return math.log2(score_gain + 1) * 0.35 if score_gain else 0.0


class ExpectimaxAI:
    """Expectimax with deterministic tie-breaking and bounded computation."""

    def __init__(self, profile: str | SearchSettings = "balanced") -> None:
        if isinstance(profile, SearchSettings):
            self.settings = profile
        else:
            try:
                self.settings = AI_PROFILES[str(profile).lower()]
            except KeyError as exc:
                raise ValueError(f"unknown AI profile: {profile!r}") from exc

    def choose_move(
        self,
        tiles: Iterable[Iterable[int]],
        *,
        time_budget_ms: int | None = None,
        node_budget: int | None = None,
    ) -> SearchResult:
        if time_budget_ms is not None:
            time_budget_ms = non_negative_integer(time_budget_ms, "time_budget_ms")
        if node_budget is not None:
            node_budget = non_negative_integer(node_budget, "node_budget")
        board = normalize_board(tiles)
        started = time.perf_counter()
        legal_results = tuple(
            (direction, move)
            for direction in DIRECTIONS
            if (move := _search_move(board, direction)).moved
        )
        if not legal_results:
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            return SearchResult(None, -math.inf, 0, 0, elapsed_ms, ())

        completed_values = tuple(
            (
                direction,
                _evaluate(move.board) + _merge_utility(move.score_gain),
            )
            for direction, move in legal_results
        )
        completed_depth = 0

        # 显式节点预算不叠加默认时间限制，让相同局面的基准可以复现。
        if time_budget_ms is None and node_budget is None:
            time_budget_ms = self.settings.time_budget_ms

        self._deadline = (
            started + time_budget_ms / 1000.0
            if time_budget_ms is not None
            else math.inf
        )
        self._node_budget = node_budget
        self._nodes = 0
        self._max_cache: dict[tuple[Board, int], float] = {}
        self._chance_cache: dict[tuple[Board, int], float] = {}
        self._spawn_cache: dict[Board, tuple[SpawnOutcome, ...]] = {}
        self._cell_cache: dict[Board, tuple[tuple[int, int], ...]] = {}
        max_depth, self._chance_limit = self._search_limits(len(board))

        if self._node_budget != 0 and (
            time_budget_ms is None or time_budget_ms > 0
        ):
            for depth in range(1, max_depth + 1):
                try:
                    values = self._root_values(legal_results, depth)
                except _SearchInterrupted:
                    break
                completed_depth = depth
                completed_values = values

        # 只采用完整搜索层；中断时沿用上一层，零预算时使用一步评分。
        best_direction, best_value = max(completed_values, key=lambda item: item[1])
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return SearchResult(
            direction=best_direction,
            value=best_value,
            depth=completed_depth,
            nodes=self._nodes,
            elapsed_ms=elapsed_ms,
            move_values=completed_values,
        )

    def _search_limits(self, size: int) -> tuple[int, int]:
        """大棋盘同时限制搜索深度与随机位置数量，避免分支数膨胀。"""
        return self.settings.limits(size)

    def _check_deadline(self, force: bool = False) -> None:
        # 节点预算模式不读时钟；UI 的时间预算模式仍在关键分支强制检查。
        if self._deadline != math.inf and (
            force or self._nodes % self.settings.deadline_check_interval == 0
        ):
            if time.perf_counter() >= self._deadline:
                raise _SearchInterrupted

    def _visit(self) -> None:
        if self._node_budget is not None and self._nodes >= self._node_budget:
            raise _SearchInterrupted
        self._check_deadline()
        self._nodes += 1

    def _root_values(
        self,
        legal_results: tuple[tuple[str, MoveResult], ...],
        depth: int,
    ) -> tuple[tuple[str, float], ...]:
        values = []
        for direction, move in legal_results:
            self._check_deadline(force=True)
            value = _merge_utility(move.score_gain)
            value += self._chance_value(move.board, depth - 1)
            values.append((direction, value))
        return tuple(values)

    def _max_value(self, board: Board, moves_left: int) -> float:
        if moves_left <= 0:
            self._visit()
            return _evaluate(board)
        key = (board, moves_left)
        cached = self._max_cache.get(key)
        if cached is not None:
            self._check_deadline(force=True)
            return cached
        self._visit()

        best = -math.inf
        for direction in DIRECTIONS:
            move = _search_move(board, direction)
            if not move.moved:
                continue
            value = _merge_utility(move.score_gain)
            value += self._chance_value(move.board, moves_left - 1)
            best = max(best, value)
        if best == -math.inf:
            best = _evaluate(board)
        self._max_cache[key] = best
        return best

    def _selected_outcomes(self, board: Board) -> tuple[SpawnOutcome, ...]:
        outcomes = self._spawn_cache.get(board)
        if outcomes is not None:
            return outcomes

        selected_cells = self._selected_cells(board)
        if not selected_cells:
            self._spawn_cache[board] = ()
            return ()

        probability_per_cell = 1.0 / len(selected_cells)
        outcomes = tuple(
            SpawnOutcome(
                probability * probability_per_cell,
                _with_tile(board, row, col, value),
            )
            for row, col in selected_cells
            for value, probability in SPAWN_DISTRIBUTION
        )
        self._spawn_cache[board] = outcomes
        return outcomes

    def _selected_cells(self, board: Board) -> tuple[tuple[int, int], ...]:
        """Sample whole dihedral coordinate orbits to preserve positional symmetry.

        Orbits contain at most eight positions. The target limits the number of
        selected orbits; sparse orbits can produce fewer positions than the target.
        A custom target below eight can require one orbit of up to eight cells.
        """
        cached = self._cell_cache.get(board)
        if cached is not None:
            return cached
        cells = _empty_cells_normalized(board)
        if len(cells) <= self._chance_limit:
            selected = cells
        else:
            size = len(board)
            orbits: dict[tuple[int, int], list[tuple[int, int]]] = {}
            for row, col in cells:
                vertical = min(row, size - 1 - row)
                horizontal = min(col, size - 1 - col)
                key = (min(vertical, horizontal), max(vertical, horizontal))
                orbits.setdefault(key, []).append((row, col))
            groups = [orbits[key] for key in sorted(orbits)]
            group_count = min(len(groups), max(1, self._chance_limit // 8))
            indices = ((2 * index + 1) * len(groups) // (2 * group_count)
                       for index in range(group_count))
            selected = tuple(sorted(cell for index in indices for cell in groups[index]))
        self._cell_cache[board] = selected
        return selected

    def _chance_leaf_value(self, board: Board) -> float:
        """Reuse one exponent array instead of encoding every spawned leaf board."""
        cells = self._selected_cells(board)
        if not cells:
            return _evaluate(board)
        logs = _exponent_array(board)
        paths, weights = _snake_arrays(len(board))
        total = 0.0
        probability_per_cell = 1.0 / len(cells)
        # Match the allocating path's built-in sum (compensated on newer Python).
        probability_sum = sum(probability * probability_per_cell
                              for _ in cells for _, probability in SPAWN_DISTRIBUTION)
        for row, col in cells:
            for tile, probability in SPAWN_DISTRIBUTION:
                self._check_deadline(force=True)
                self._visit()
                logs[row, col] = tile.bit_length() - 1
                child = evaluate_exponents(logs, paths, weights)
                weight = probability * probability_per_cell
                total += weight * child
            logs[row, col] = 0.0
        return total / probability_sum

    def _chance_value(self, board: Board, moves_left: int) -> float:
        key = (board, moves_left)
        cached = self._chance_cache.get(key)
        if cached is not None:
            self._check_deadline(force=True)
            return cached
        self._visit()

        if moves_left == 0:
            value = self._chance_leaf_value(board)
            self._chance_cache[key] = value
            return value

        outcomes = self._selected_outcomes(board)
        if not outcomes:
            value = self._max_value(board, moves_left)
            self._chance_cache[key] = value
            return value

        probability_sum = sum(outcome.probability for outcome in outcomes)
        total = 0.0
        for outcome in outcomes:
            self._check_deadline(force=True)
            child = self._max_value(outcome.board, moves_left)
            total += outcome.probability * child
        value = total / probability_sum
        self._chance_cache[key] = value
        return value
