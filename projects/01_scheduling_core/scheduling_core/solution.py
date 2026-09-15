"""候选解的不可变表示与合法性校验；不负责解码或搜索。"""

from dataclasses import dataclass
from scheduling_core.models import Instance


@dataclass(frozen=True, slots=True)
class Candidate:
    order: tuple[str, ...]
    assignments: tuple[str, ...]


def validate_candidate(instance: Instance, candidate: Candidate) -> None:
    ids = {op.id for op in instance.operations}
    if len(candidate.order) != len(ids) or set(candidate.order) != ids:
        raise ValueError("order must contain every operation exactly once")
    if len(candidate.assignments) != len(instance.operations):
        raise ValueError("assignment length mismatch")
    for op, machine in zip(instance.operations, candidate.assignments, strict=True):
        if machine not in op.eligible_machine_ids:
            raise ValueError(f"illegal assignment: {op.id} -> {machine}")
