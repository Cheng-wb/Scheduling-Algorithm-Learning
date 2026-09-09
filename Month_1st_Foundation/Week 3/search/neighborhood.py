"""Move 返回新列表；生成器逐个产生邻居，不负责排程和评价。

输入应为任务不重复的排列。索引从 0 开始，不接受负索引。
"""

from collections.abc import Iterator, Sequence
from random import Random
from typing import TypeVar

T = TypeVar("T")


def _check_indices(solution, i, j):
    for index in (i, j):
        if type(index) is not int:
            raise TypeError("indices must be integers")
        if not 0 <= index < len(solution):
            raise IndexError("index outside the solution")


def swap(solution: Sequence[T], i: int, j: int) -> list[T]:
    _check_indices(solution, i, j)
    neighbor = list(solution)
    neighbor[i], neighbor[j] = neighbor[j], neighbor[i]
    return neighbor


def insert(solution: Sequence[T], from_idx: int, to_idx: int) -> list[T]:
    """取出任务再插入；to_idx 是该任务在结果中的最终索引。"""
    _check_indices(solution, from_idx, to_idx)
    neighbor = list(solution)
    job = neighbor.pop(from_idx)
    neighbor.insert(to_idx, job)
    return neighbor


def reverse(solution: Sequence[T], i: int, j: int) -> list[T]:
    """反转闭区间 [i, j]，要求 i <= j。"""
    _check_indices(solution, i, j)
    if i > j:
        raise ValueError("reverse requires i <= j")
    neighbor = list(solution)
    neighbor[i:j + 1] = neighbor[i:j + 1][::-1]
    return neighbor


def generate_swap_neighbors(solution: Sequence[T]) -> Iterator[list[T]]:
    for i in range(len(solution)):
        for j in range(i + 1, len(solution)):
            yield swap(solution, i, j)


def generate_insert_neighbors(solution: Sequence[T]) -> Iterator[list[T]]:
    for i in range(len(solution)):
        for j in range(len(solution)):
            # 相邻任务前移与后移产生同一排列，仅保留后移。
            if i != j and i != j + 1:
                yield insert(solution, i, j)


def generate_reverse_neighbors(solution: Sequence[T]) -> Iterator[list[T]]:
    for i in range(len(solution)):
        for j in range(i + 1, len(solution)):
            yield reverse(solution, i, j)


def generate_neighbors(solution: Sequence[T], kind: str = "swap") -> Iterator[list[T]]:
    generators = {"swap": generate_swap_neighbors, "insert": generate_insert_neighbors,
                  "reverse": generate_reverse_neighbors}
    if kind not in generators:
        raise ValueError(f"unknown neighborhood: {kind!r}")
    return generators[kind](solution)


def random_swap_neighbor(solution: Sequence[T], rng: Random | None = None) -> list[T]:
    """随机选择两个不同位置；传入局部 Random 对象可复现实验。"""
    if len(solution) < 2:
        raise ValueError("a swap neighbor requires at least two jobs")
    rng = rng if rng is not None else Random()
    i, j = rng.sample(range(len(solution)), 2)
    return swap(solution, i, j)
