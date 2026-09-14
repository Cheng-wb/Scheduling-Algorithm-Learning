"""models.py 的单元测试：创建 + 不可变性。"""

from dataclasses import FrozenInstanceError

import pytest

from scheduling_core.models import Instance, Job, Machine, Operation


def _make_instance() -> Instance:
    """Day2.md 第 11 节的两台机器小实例。"""
    m1 = Machine(id="M1", name="Machine 1")
    m2 = Machine(id="M2", name="Machine 2")

    o1 = Operation(id="O1", job_id="J1", processing_time=3, eligible_machine_ids=("M1", "M2"))
    o2 = Operation(id="O2", job_id="J1", processing_time=2, eligible_machine_ids=("M2",))
    o3 = Operation(id="O3", job_id="J2", processing_time=4, eligible_machine_ids=("M1",))

    j1 = Job(id="J1", operation_ids=("O1", "O2"), release_time=0, due_date=8)
    j2 = Job(id="J2", operation_ids=("O3",), release_time=1, due_date=7)

    return Instance(jobs=(j1, j2), operations=(o1, o2, o3), machines=(m1, m2))


def test_create_machine():
    m = Machine(id="M1", name="Machine 1")
    assert m.id == "M1"
    assert m.name == "Machine 1"


def test_create_operation():
    op = Operation(id="O1", job_id="J1", processing_time=3, eligible_machine_ids=("M1", "M2"))
    assert op.id == "O1"
    assert op.job_id == "J1"
    assert op.processing_time == 3
    assert op.eligible_machine_ids == ("M1", "M2")


def test_job_defaults():
    j = Job(id="J1", operation_ids=("O1",))
    assert j.release_time == 0
    assert j.due_date is None
    assert j.weight == 1.0


def test_create_instance():
    inst = _make_instance()
    assert len(inst.jobs) == 2
    assert len(inst.operations) == 3
    assert len(inst.machines) == 2


def test_frozen_reassignment_raises():
    m = Machine(id="M1", name="Machine 1")
    with pytest.raises(FrozenInstanceError):
        m.id = "M99"


def test_eligible_machine_ids_is_immutable_tuple():
    op = Operation(id="O1", job_id="J1", processing_time=3, eligible_machine_ids=("M1", "M2"))
    assert isinstance(op.eligible_machine_ids, tuple)
    # tuple 没有 append，能从根本上防止 op.eligible_machine_ids.append("M99")
    assert not hasattr(op.eligible_machine_ids, "append")
