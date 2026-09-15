"""objective.py 的单元测试：用手算小实例对拍指标。"""

from scheduling_core.models import Instance, Job, Machine, Operation
from scheduling_core.objective import (
    job_completion_times,
    makespan,
    max_lateness,
    total_completion_time,
    total_flow_time,
    total_tardiness,
    weighted_completion_time,
)
from scheduling_core.schedule import Schedule, ScheduledOperation


def _two_job_instance():
    m1 = Machine(id="M1", name="M1")

    o1 = Operation(
        id="O1", job_id="J1", processing_time=3, eligible_machine_ids=("M1",)
    )
    o2 = Operation(
        id="O2", job_id="J2", processing_time=2, eligible_machine_ids=("M1",)
    )

    j1 = Job(id="J1", operation_ids=("O1",), release_time=0, due_date=4, weight=2.0)
    j2 = Job(id="J2", operation_ids=("O2",), release_time=0, due_date=10, weight=1.0)

    return Instance(jobs=(j1, j2), operations=(o1, o2), machines=(m1,))


def _two_job_schedule():
    # O1: 0-3, O2: 3-5 → C1=3, C2=5
    return Schedule(
        operations=(
            ScheduledOperation("O1", "M1", 0, 3),
            ScheduledOperation("O2", "M1", 3, 5),
        )
    )


def test_makespan():
    assert makespan(_two_job_instance(), _two_job_schedule()) == 5


def test_total_completion_time():
    assert total_completion_time(_two_job_instance(), _two_job_schedule()) == 8


def test_total_tardiness():
    # max(0,3-4) + max(0,5-10) = 0
    assert total_tardiness(_two_job_instance(), _two_job_schedule()) == 0


def test_weighted_completion_time():
    # 2*3 + 1*5 = 11
    assert weighted_completion_time(_two_job_instance(), _two_job_schedule()) == 11.0


def test_total_flow_time():
    # (3-0) + (5-0) = 8
    assert total_flow_time(_two_job_instance(), _two_job_schedule()) == 8


def test_hand_computed_nonzero_tardiness():
    # 参考文档第 26 节练习 2：C1=5,d1=4,w1=2；C2=8,d2=10,w2=3；C3=6,d3=6,w3=1
    m1 = Machine(id="M1", name="M1")

    o1 = Operation(
        id="O1", job_id="J1", processing_time=5, eligible_machine_ids=("M1",)
    )
    o2 = Operation(
        id="O2", job_id="J2", processing_time=3, eligible_machine_ids=("M1",)
    )
    o3 = Operation(
        id="O3", job_id="J3", processing_time=1, eligible_machine_ids=("M1",)
    )

    j1 = Job(id="J1", operation_ids=("O1",), release_time=0, due_date=4, weight=2.0)
    j2 = Job(id="J2", operation_ids=("O2",), release_time=0, due_date=10, weight=3.0)
    j3 = Job(id="J3", operation_ids=("O3",), release_time=0, due_date=6, weight=1.0)

    inst = Instance(jobs=(j1, j2, j3), operations=(o1, o2, o3), machines=(m1,))

    # 只为对拍 objective 的数学；可行性校验是 Week 2 的职责
    schedule = Schedule(
        operations=(
            ScheduledOperation("O1", "M1", 0, 5),
            ScheduledOperation("O2", "M1", 5, 8),
            ScheduledOperation("O3", "M1", 5, 6),
        )
    )

    assert makespan(inst, schedule) == 8
    assert total_completion_time(inst, schedule) == 19  # 5 + 8 + 6
    assert total_tardiness(inst, schedule) == 1  # 1 + 0 + 0
    assert weighted_completion_time(inst, schedule) == 40.0  # 10 + 24 + 6


def test_total_flow_time_with_release():
    # 参考文档第 26 节练习 3：F1=5, F2=5, F3=4
    m1 = Machine(id="M1", name="M1")

    o1 = Operation(
        id="O1", job_id="J1", processing_time=5, eligible_machine_ids=("M1",)
    )
    o2 = Operation(
        id="O2", job_id="J2", processing_time=5, eligible_machine_ids=("M1",)
    )
    o3 = Operation(
        id="O3", job_id="J3", processing_time=4, eligible_machine_ids=("M1",)
    )

    j1 = Job(id="J1", operation_ids=("O1",), release_time=0)
    j2 = Job(id="J2", operation_ids=("O2",), release_time=3)
    j3 = Job(id="J3", operation_ids=("O3",), release_time=2)

    inst = Instance(jobs=(j1, j2, j3), operations=(o1, o2, o3), machines=(m1,))

    schedule = Schedule(
        operations=(
            ScheduledOperation("O1", "M1", 0, 5),
            ScheduledOperation("O2", "M1", 5, 8),
            ScheduledOperation("O3", "M1", 5, 6),
        )
    )

    # (5-0) + (8-3) + (6-2) = 14
    assert total_flow_time(inst, schedule) == 14


def test_max_lateness():
    # C1=5,d1=4 → L1=1；C2=8,d2=10 → L2=-2 → Lmax = 1
    m1 = Machine(id="M1", name="M1")

    o1 = Operation(
        id="O1", job_id="J1", processing_time=5, eligible_machine_ids=("M1",)
    )
    o2 = Operation(
        id="O2", job_id="J2", processing_time=3, eligible_machine_ids=("M1",)
    )

    j1 = Job(id="J1", operation_ids=("O1",), release_time=0, due_date=4)
    j2 = Job(id="J2", operation_ids=("O2",), release_time=0, due_date=10)

    inst = Instance(jobs=(j1, j2), operations=(o1, o2), machines=(m1,))

    schedule = Schedule(
        operations=(
            ScheduledOperation("O1", "M1", 0, 5),
            ScheduledOperation("O2", "M1", 5, 8),
        )
    )

    assert max_lateness(inst, schedule) == 1


def test_max_lateness_can_be_negative():
    # 所有 job 都提前完成时 Lmax < 0
    m1 = Machine(id="M1", name="M1")

    o1 = Operation(
        id="O1", job_id="J1", processing_time=2, eligible_machine_ids=("M1",)
    )

    j1 = Job(id="J1", operation_ids=("O1",), release_time=0, due_date=10)

    inst = Instance(jobs=(j1,), operations=(o1,), machines=(m1,))

    schedule = Schedule(operations=(ScheduledOperation("O1", "M1", 0, 2),))

    assert max_lateness(inst, schedule) == -8


def test_total_tardiness_ignores_missing_due_date():
    m1 = Machine(id="M1", name="M1")

    o1 = Operation(
        id="O1", job_id="J1", processing_time=10, eligible_machine_ids=("M1",)
    )
    o2 = Operation(
        id="O2", job_id="J2", processing_time=1, eligible_machine_ids=("M1",)
    )

    j1 = Job(id="J1", operation_ids=("O1",), release_time=0, due_date=2, weight=1.0)
    j2 = Job(id="J2", operation_ids=("O2",), release_time=0, due_date=None, weight=1.0)

    inst = Instance(jobs=(j1, j2), operations=(o1, o2), machines=(m1,))

    schedule = Schedule(
        operations=(
            ScheduledOperation("O1", "M1", 0, 10),
            ScheduledOperation("O2", "M1", 10, 11),
        )
    )

    # J1 迟交 8，J2 无交期不参与
    assert total_tardiness(inst, schedule) == 8


def test_job_completion_times_takes_max_over_operations():
    m1 = Machine(id="M1", name="M1")
    m2 = Machine(id="M2", name="M2")

    o1 = Operation(
        id="O1", job_id="J1", processing_time=3, eligible_machine_ids=("M1",)
    )
    o2 = Operation(
        id="O2", job_id="J1", processing_time=2, eligible_machine_ids=("M2",)
    )

    j1 = Job(id="J1", operation_ids=("O1", "O2"), release_time=0)

    inst = Instance(jobs=(j1,), operations=(o1, o2), machines=(m1, m2))

    schedule = Schedule(
        operations=(
            ScheduledOperation("O1", "M1", 0, 3),
            ScheduledOperation("O2", "M2", 0, 5),
        )
    )

    # J1 的完工时间取两工序的最大 end_time
    assert job_completion_times(inst, schedule) == {"J1": 5}
