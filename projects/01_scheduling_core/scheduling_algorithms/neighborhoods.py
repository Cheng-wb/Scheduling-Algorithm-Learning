"""交换、插入与机器指派邻域；只产生新候选解。"""

from dataclasses import replace
from collections.abc import Iterator
from scheduling_core.models import Instance
from scheduling_core.solution import Candidate


def swap(candidate: Candidate, i: int, j: int) -> Candidate:
    _indices(candidate, i, j)
    order = list(candidate.order)
    order[i], order[j] = order[j], order[i]
    return replace(candidate, order=tuple(order))


def insert(candidate: Candidate, i: int, j: int) -> Candidate:
    """把原位置 i 的元素移到结果的 j 位置。"""
    _indices(candidate, i, j)
    order = list(candidate.order)
    order.insert(j, order.pop(i))
    return replace(candidate, order=tuple(order))


def _indices(candidate: Candidate, i: int, j: int) -> None:
    if not (0 <= i < len(candidate.order) and 0 <= j < len(candidate.order)):
        raise IndexError("move indices outside permutation")


def reassign(
    instance: Instance, candidate: Candidate, index: int, machine: str
) -> Candidate:
    if not 0 <= index < len(instance.operations):
        raise IndexError("operation index outside instance")
    if machine not in instance.operations[index].eligible_machine_ids:
        raise ValueError("illegal assignment")
    assignments = list(candidate.assignments)
    assignments[index] = machine
    return replace(candidate, assignments=tuple(assignments))


def neighbors(instance: Instance, candidate: Candidate) -> Iterator[Candidate]:
    """固定扫描顺序，去除 swap/insert 重合解以及自身。"""
    seen = {candidate}
    for i in range(len(candidate.order)):
        for j in range(len(candidate.order)):
            for moved in (swap(candidate, i, j), insert(candidate, i, j)):
                if moved not in seen:
                    seen.add(moved)
                    yield moved
    for i, op in enumerate(instance.operations):
        for machine in sorted(op.eligible_machine_ids):
            moved = reassign(instance, candidate, i, machine)
            if moved not in seen:
                seen.add(moved)
                yield moved
