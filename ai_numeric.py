"""Numba 评分内核：固定签名提前编译，所有阶数复用同一份机器码。

不启用 fastmath，保留逐项累加顺序，避免微小舍入误差改变接近平局的选择。
"""

from __future__ import annotations

import math

from numba import njit


@njit(
    "float64(float64[:, ::1], int64[:, ::1], float64[::1])",
    cache=True,
    nogil=True,
    fastmath=False,
)
def evaluate_exponents(logs, paths, weights):
    """Score contiguous exponent arrays; zero denotes an empty cell."""

    size = logs.shape[0]
    empty_count = 0
    max_log = 0.0
    smoothness = 0.0
    merge_potential = 0.0
    for row in range(size):
        for col in range(size):
            value = logs[row, col]
            max_log = max(max_log, value)
            if not value:
                empty_count += 1
                continue
            if col + 1 < size and logs[row, col + 1]:
                neighbor = logs[row, col + 1]
                smoothness -= abs(value - neighbor)
                if value == neighbor:
                    merge_potential += 1.0 + value * 0.08
            if row + 1 < size and logs[row + 1, col]:
                neighbor = logs[row + 1, col]
                smoothness -= abs(value - neighbor)
                if value == neighbor:
                    merge_potential += 1.0 + value * 0.08

    # 全空棋盘和无法合并的满棋盘都没有合法移动。
    if empty_count == size * size:
        return -1_000_000.0
    if empty_count == 0 and merge_potential == 0.0:
        return -1_000_000.0 - max_log

    # 单调性跨过空格比较；上面的平滑度只比较物理相邻的非空格。
    horizontal_down = horizontal_up = 0.0
    vertical_down = vertical_up = 0.0
    for row in range(size):
        previous = 0.0
        for col in range(size):
            value = logs[row, col]
            if not value:
                continue
            if previous > value:
                horizontal_up += value - previous
            elif previous and value > previous:
                horizontal_down += previous - value
            previous = value
    for col in range(size):
        previous = 0.0
        for row in range(size):
            value = logs[row, col]
            if not value:
                continue
            if previous > value:
                vertical_up += value - previous
            elif previous and value > previous:
                vertical_down += previous - value
            previous = value
    monotonicity = max(horizontal_down, horizontal_up)
    monotonicity += max(vertical_down, vertical_up)

    on_corner = (
        logs[0, 0] == max_log or logs[0, -1] == max_log
        or logs[-1, 0] == max_log or logs[-1, -1] == max_log
    )
    on_edge = False
    for index in range(size):
        if (
            logs[0, index] == max_log or logs[-1, index] == max_log
            or logs[index, 0] == max_log or logs[index, -1] == max_log
        ):
            on_edge = True
            break
    corner_term = max_log * (1.8 if on_corner else -0.85)
    edge_term = max_log * 0.35 if on_edge else 0.0
    empty_term = empty_count * 3.05 + math.log2(empty_count + 1) * 2.0

    flat = logs.reshape(size * size)
    snake_score = hierarchy_score = -math.inf
    max_squared = max_log * max_log
    for path in paths:
        linear = squared = 0.0
        for index in range(len(weights)):
            value = flat[path[index]]
            weight = weights[index]
            linear += value * weight
            squared += value * value * weight
            # 权重递减：若最大可能单项也无法改变当前浮点和，后续逐项
            # 累加必然不变。间隔检查避免小棋盘开销，也跳过大棋盘次正规数尾部。
            if index >= 31 and index % 16 == 15:
                if (linear + max_log * weight == linear
                        and squared + max_squared * weight == squared):
                    break
        snake_score = max(snake_score, linear)
        hierarchy_score = max(hierarchy_score, squared)
    snake_term = snake_score * 1.75
    hierarchy_term = hierarchy_score * 0.48

    return (
        empty_term
        + monotonicity
        + smoothness * 0.16
        + merge_potential * 0.9
        + corner_term
        + edge_term
        + snake_term
        + hierarchy_term
    )
