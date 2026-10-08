"""评分入口：不可变棋盘 → NumPy 指数数组 → 编译内核，并复用小棋盘缓存。"""

from __future__ import annotations

from collections.abc import Iterable
from functools import lru_cache

import numpy as np

from ai_numeric import evaluate_exponents
from game_rules import Board, normalize_board


@lru_cache(maxsize=16)
def _snake_arrays(size: int) -> tuple[np.ndarray, np.ndarray]:
    """按阶数缓存八种旋转/镜像路径，以及共同的递减权重。"""

    current = tuple(
        (row, col)
        for row in range(size)
        for col in (range(size) if row % 2 == 0 else range(size - 1, -1, -1))
    )
    paths = []
    for _ in range(4):
        for reflected in (False, True):
            paths.append(tuple(
                row * size + (size - 1 - col if reflected else col)
                for row, col in current
            ))
        current = tuple((col, size - 1 - row) for row, col in current)

    weights = np.empty(size * size, dtype=np.float64)
    weight = 1.0
    for index in range(len(weights)):
        weights[index] = weight
        weight *= 0.52
    # 单格棋盘的八条路径重合，去重后仍可走同一个内核。
    return np.asarray(tuple(dict.fromkeys(paths)), dtype=np.int64), weights


def _evaluate_uncached(board: Board) -> float:
    size = len(board)
    logs = _exponent_array(board)
    paths, weights = _snake_arrays(size)
    return evaluate_exponents(logs, paths, weights)


def _exponent_array(board: Board) -> np.ndarray:
    """Encode once; large boards use vectorized exact log2 for representable powers.

    Powers of two are exactly representable below float overflow. An overflow
    during conversion falls back to Python bit lengths of the original tiles.
    """
    size = len(board)
    if size >= 8:
        try:
            logs = np.asarray(board, dtype=np.float64)
        except OverflowError:
            pass
        else:
            np.log2(logs, out=logs, where=logs != 0.0)
            return logs
    return np.fromiter(
        (value.bit_length() - 1 if value else 0 for row in board for value in row),
        dtype=np.float64,
        count=size * size,
    ).reshape(size, size)


@lru_cache(maxsize=65_536)
def _evaluate_cached(board: Board) -> float:
    return _evaluate_uncached(board)


def _evaluate(board: Board) -> float:
    # 小棋盘跨回合复用，大棋盘不进入全局缓存，限制内存占用。
    return _evaluate_cached(board) if len(board) <= 4 else _evaluate_uncached(board)


def evaluate_board(tiles: Iterable[Iterable[int]]) -> float:
    """Evaluate a square board using exponent-based, rotation-symmetric features."""

    return _evaluate(normalize_board(tiles))
