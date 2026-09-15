"""rules.py 的单元测试：单机 SPT/EDD/WSPT/LPT 与释放时间处理。"""

import pytest

from scheduling_core.models import Instance, Job, Machine, Operation
from scheduling_core.objective import (
    makespan,
    max_lateness,
    total_completion_time,
    total_tardiness,
    weighted_completion_time,
)
from scheduling_algorithms.rules import (
    edd,
    lpt,
    parallel_lpt,
    parallel_makespan_lower_bound,
    spt,
    wspt,
)


def _single_machine_instance(jobs_spec):
    """构造单机实例。jobs_spec 元素为 (id, p, r, d, w)。"""
    m1 = Machine(id="M1", name="M1")

    operations = []
    jobs = []

    for jid, p, r, d, w in jobs_spec:
        oid = f"O_{jid}"
        operations.append(
            Operation(
                id=oid, job_id=jid, processing_time=p, eligible_machine_ids=("M1",)
            )
        )
        jobs.append(
            Job(id=jid, operation_ids=(oid,), release_time=r, due_date=d, weight=w)
        )

    return Instance(jobs=tuple(jobs), operations=tuple(operations), machines=(m1,))


def _order(instance, schedule):
    """从 Schedule 提取按开始时间排序的 job id 序列。"""
    op_by_id = {op.id: op for op in instance.operations}
    ordered = sorted(schedule.operations, key=lambda s: s.start_time)
    return [op_by_id[s.operation_id].job_id for s in ordered]


def _day1_instance():
    """Day1.md 第 14 节 / Day4.md 实例 A：带释放时间的 5 job 单机实例。"""
    return _single_machine_instance(
        [
            ("J1", 6, 0, 12, 1.0),
            ("J2", 2, 0, 8, 3.0),
            ("J3", 4, 3, 15, 1.0),
            ("J4", 3, 5, 10, 2.0),
            ("J5", 7, 0, 20, 1.0),
        ]
    )


def test_spt_sorts_by_processing_time():
    inst = _single_machine_instance(
        [
            ("J1", 6, 0, None, 1.0),
            ("J2", 2, 0, None, 1.0),
            ("J3", 4, 0, None, 1.0),
        ]
    )
    assert _order(inst, spt(inst)) == ["J2", "J3", "J1"]


def test_spt_minimizes_total_completion_time():
    inst = _single_machine_instance(
        [
            ("J1", 6, 0, None, 1.0),
            ("J2", 2, 0, None, 1.0),
            ("J3", 4, 0, None, 1.0),
            ("J4", 3, 0, None, 1.0),
            ("J5", 7, 0, None, 1.0),
        ]
    )
    # SPT 顺序 2,3,4,6,7 → C: 2,5,9,15,22 → ΣCj = 53
    assert total_completion_time(inst, spt(inst)) == 53


def test_lpt_sorts_by_longest_processing_time_first():
    inst = _single_machine_instance(
        [
            ("J1", 6, 0, None, 1.0),
            ("J2", 2, 0, None, 1.0),
            ("J3", 4, 0, None, 1.0),
        ]
    )
    assert _order(inst, lpt(inst)) == ["J1", "J3", "J2"]


def test_edd_sorts_by_due_date_and_defers_missing_due_date():
    inst = _single_machine_instance(
        [
            ("J1", 3, 0, 10, 1.0),
            ("J2", 3, 0, 6, 1.0),
            ("J3", 3, 0, None, 1.0),
        ]
    )
    # EDD：J2(d6), J1(d10), J3(无交期排最后)
    assert _order(inst, edd(inst)) == ["J2", "J1", "J3"]


def test_edd_minimizes_max_lateness():
    inst = _single_machine_instance(
        [
            ("J1", 4, 0, 6, 1.0),
            ("J2", 1, 0, 12, 5.0),
            ("J3", 3, 0, 8, 2.0),
            ("J4", 2, 0, 3, 1.0),
        ]
    )
    # EDD 顺序 J4,J1,J3,J2 → C: 2,6,9,10 → Lmax = 1
    assert _order(inst, edd(inst)) == ["J4", "J1", "J3", "J2"]
    assert max_lateness(inst, edd(inst)) == 1


def test_wspt_sorts_by_processing_time_over_weight():
    inst = _single_machine_instance(
        [
            ("J1", 2, 0, None, 1.0),  # 2/1 = 2
            ("J2", 8, 0, None, 5.0),  # 8/5 = 1.6
            ("J3", 5, 0, None, 2.0),  # 5/2 = 2.5
            ("J4", 1, 0, None, 1.0),  # 1/1 = 1
        ]
    )
    # WSPT：J4(1), J2(1.6), J1(2), J3(2.5)
    assert _order(inst, wspt(inst)) == ["J4", "J2", "J1", "J3"]


def test_wspt_minimizes_weighted_completion_time():
    inst = _single_machine_instance(
        [
            ("J1", 4, 0, 6, 1.0),
            ("J2", 1, 0, 12, 5.0),
            ("J3", 3, 0, 8, 2.0),
            ("J4", 2, 0, 3, 1.0),
        ]
    )
    # WSPT 顺序 J2,J3,J4,J1 → C: 1,4,6,10 → ΣwjCj = 5*1 + 2*4 + 1*6 + 1*10 = 29
    assert _order(inst, wspt(inst)) == ["J2", "J3", "J4", "J1"]
    assert weighted_completion_time(inst, wspt(inst)) == 29.0


def test_release_time_defers_start():
    # J2 在 t=5 才释放，即使 SPT 上它更短，也不能在 5 之前开始
    inst = _single_machine_instance(
        [
            ("J1", 10, 0, None, 1.0),
            ("J2", 1, 5, None, 1.0),
        ]
    )
    schedule = spt(inst)
    scheduled = {s.operation_id: s for s in schedule.operations}
    assert scheduled["O_J2"].start_time >= 5


def test_idle_when_no_job_released():
    # J1 做完后（t=2）没有已释放 job，机器空转到 t=10 再加工 J2
    inst = _single_machine_instance(
        [
            ("J1", 2, 0, None, 1.0),
            ("J2", 1, 10, None, 1.0),
        ]
    )
    schedule = spt(inst)
    scheduled = {s.operation_id: s for s in schedule.operations}
    assert scheduled["O_J2"].start_time == 10


def test_ties_break_by_job_id():
    inst = _single_machine_instance(
        [
            ("J2", 3, 0, None, 1.0),
            ("J1", 3, 0, None, 1.0),
            ("J3", 3, 0, None, 1.0),
        ]
    )
    assert _order(inst, spt(inst)) == ["J1", "J2", "J3"]


def test_day1_instance_spt_objectives():
    inst = _day1_instance()
    sched = spt(inst)

    assert _order(inst, sched) == ["J2", "J1", "J4", "J3", "J5"]
    assert makespan(inst, sched) == 22
    assert total_completion_time(inst, sched) == 58
    assert total_tardiness(inst, sched) == 3
    assert weighted_completion_time(inst, sched) == 73.0


def test_day1_instance_lpt_objectives():
    inst = _day1_instance()
    sched = lpt(inst)

    assert _order(inst, sched) == ["J5", "J1", "J3", "J4", "J2"]
    assert makespan(inst, sched) == 22
    assert total_completion_time(inst, sched) == 79
    assert total_tardiness(inst, sched) == 27
    assert weighted_completion_time(inst, sched) == 143.0


def test_rejects_multi_operation_job():
    m1 = Machine(id="M1", name="M1")
    o1 = Operation(
        id="O1", job_id="J1", processing_time=2, eligible_machine_ids=("M1",)
    )
    o2 = Operation(
        id="O2", job_id="J1", processing_time=3, eligible_machine_ids=("M1",)
    )
    j1 = Job(id="J1", operation_ids=("O1", "O2"))

    inst = Instance(jobs=(j1,), operations=(o1, o2), machines=(m1,))

    with pytest.raises(ValueError):
        spt(inst)


def test_rejects_multiple_machines_without_machine_id():
    m1 = Machine(id="M1", name="M1")
    m2 = Machine(id="M2", name="M2")
    o1 = Operation(
        id="O1", job_id="J1", processing_time=2, eligible_machine_ids=("M1",)
    )
    j1 = Job(id="J1", operation_ids=("O1",))

    inst = Instance(jobs=(j1,), operations=(o1,), machines=(m1, m2))

    with pytest.raises(ValueError):
        spt(inst)


def _parallel_instance(processing_times, machine_count=2):
    """构造 r=0、全资格的并行机实例：每个 job 一道工序，p 由列表给出。"""
    machine_ids = tuple(f"M{i}" for i in range(machine_count))
    machines = tuple(Machine(id=mid, name=mid) for mid in machine_ids)

    jobs = []
    operations = []

    for i, p in enumerate(processing_times):
        jid = f"J{i}"
        oid = f"O{i}"
        jobs.append(Job(id=jid, operation_ids=(oid,)))
        operations.append(
            Operation(
                id=oid, job_id=jid, processing_time=p, eligible_machine_ids=machine_ids
            )
        )

    return Instance(jobs=tuple(jobs), operations=tuple(operations), machines=machines)


def test_parallel_lpt_orders_by_longest_first():
    inst = _parallel_instance([3, 8, 5], machine_count=2)
    schedule = parallel_lpt(inst)
    # 加工时间降序：J1(8), J2(5), J0(3)
    assert [s.operation_id for s in schedule.operations] == ["O1", "O2", "O0"]


def test_parallel_lpt_assigns_to_least_loaded_machine():
    inst = _parallel_instance([8, 7, 6, 5], machine_count=2)
    schedule = parallel_lpt(inst)
    # O0(8)->M0, O1(7)->M1, O2(6)->M1(7<8), O3(5)->M0(8<13)
    assert [
        (s.operation_id, s.machine_id, s.start_time, s.end_time)
        for s in schedule.operations
    ] == [
        ("O0", "M0", 0, 8),
        ("O1", "M1", 0, 7),
        ("O2", "M1", 7, 13),
        ("O3", "M0", 8, 13),
    ]


def test_parallel_lpt_machine_tie_breaks_by_machine_id():
    inst = _parallel_instance([5], machine_count=3)
    schedule = parallel_lpt(inst)
    # 所有机器 ready=0，选 id 最小的 M0
    assert schedule.operations[0].machine_id == "M0"


def test_parallel_lpt_job_tie_breaks_by_job_id():
    inst = _parallel_instance([5, 5], machine_count=2)
    schedule = parallel_lpt(inst)
    assert [s.operation_id for s in schedule.operations] == ["O0", "O1"]
    assert makespan(inst, schedule) == 5


def test_parallel_lpt_makespan_balanced():
    inst = _parallel_instance([8, 7, 6, 5], machine_count=2)
    assert makespan(inst, parallel_lpt(inst)) == 13


def test_parallel_lpt_makespan_matches_hand_computed():
    inst = _parallel_instance([4, 3, 2], machine_count=2)
    assert makespan(inst, parallel_lpt(inst)) == 5


def test_parallel_lpt_schedules_every_operation_once():
    inst = _parallel_instance([8, 7, 6, 5], machine_count=2)
    schedule = parallel_lpt(inst)
    scheduled_ids = [s.operation_id for s in schedule.operations]
    assert sorted(scheduled_ids) == ["O0", "O1", "O2", "O3"]
    assert len(scheduled_ids) == len(set(scheduled_ids)) == 4


def test_parallel_lpt_rejects_multi_operation_job():
    m0 = Machine(id="M0", name="M0")
    m1 = Machine(id="M1", name="M1")
    o1 = Operation(
        id="O1", job_id="J1", processing_time=2, eligible_machine_ids=("M0", "M1")
    )
    o2 = Operation(
        id="O2", job_id="J1", processing_time=3, eligible_machine_ids=("M0", "M1")
    )
    j1 = Job(id="J1", operation_ids=("O1", "O2"))

    inst = Instance(jobs=(j1,), operations=(o1, o2), machines=(m0, m1))

    with pytest.raises(ValueError):
        parallel_lpt(inst)


def test_parallel_makespan_lower_bound_average_dominates():
    inst = _parallel_instance([9, 8, 7, 6, 5, 4], machine_count=3)
    # total=39, ceil(39/3)=13, longest=9 → 13
    assert parallel_makespan_lower_bound(inst) == 13


def test_parallel_makespan_lower_bound_balanced():
    inst = _parallel_instance([8, 7, 6, 5], machine_count=2)
    # total=26, ceil(26/2)=13, longest=8 → 13
    assert parallel_makespan_lower_bound(inst) == 13


def test_parallel_makespan_lower_bound_longest_dominates():
    inst = _parallel_instance([10, 1, 1, 1], machine_count=3)
    # total=13, ceil(13/3)=5, 但最长加工 10 → 10
    assert parallel_makespan_lower_bound(inst) == 10


def test_parallel_makespan_lower_bound_empty():
    inst = _parallel_instance([], machine_count=2)
    assert parallel_makespan_lower_bound(inst) == 0
