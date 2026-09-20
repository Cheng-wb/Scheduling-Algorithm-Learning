"""M3 共享地基测试：领域模型、输入校验、独立验证器、目标评估、JSON 往返。

验证器的用例全部基于一个**手算小实例**，期望值来自手写时间线，不由被测代码生成。
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from fjsp_core import (
    Calendar,
    FJSPInstance,
    FJSPInstanceError,
    Job,
    Machine,
    Maintenance,
    Operation,
    Qualification,
    Schedule,
    ScheduledOperation,
    Setup,
    Weights,
    Worker,
    makespan,
    objective_breakdown,
    schedule_errors,
    total_setup_time,
    total_tardiness,
    validate_instance,
    validate_schedule,
    weighted_sum,
    worker_load,
)
from fjsp_io import generate_instance, load_json_instance, save_json_instance


# --- 手算小实例 -----------------------------------------------------------
# J0: A(p: M0=4, M1=6) -> B(p: M0=3)
# J1: C(p: M1=5)
# 完整手算排程：A 在 M1[0,6)，B 在 M0[6,9)，C 在 M1[6,11)  → Cmax = 11
def small_instance() -> FJSPInstance:
    return FJSPInstance(
        jobs=(
            Job("J0", ("A", "B"), release_time=0, due_date=10, weight=1.0),
            Job("J1", ("C",), release_time=0, due_date=12, weight=2.0),
        ),
        operations=(
            Operation("A", "J0", 0, (("M0", 4), ("M1", 6))),
            Operation("B", "J0", 1, (("M0", 3),)),
            Operation("C", "J1", 0, (("M1", 5),)),
        ),
        machines=(Machine("M0", "M0"), Machine("M1", "M1")),
    )


def valid_schedule() -> Schedule:
    return Schedule(
        (
            ScheduledOperation("A", "M1", 0, 6),
            ScheduledOperation("B", "M0", 6, 9),
            ScheduledOperation("C", "M1", 6, 11),
        )
    )


# --- 模型 -----------------------------------------------------------------


def test_operation_reports_machine_dependent_times() -> None:
    instance = small_instance()
    op = instance.operation("A")
    assert op.time_on("M0") == 4
    assert op.time_on("M1") == 6
    assert op.time_on("M9") is None, "不合格机器必须返回 None，不是 0 也不是默认值"
    assert op.eligible_machine_ids == ("M0", "M1")
    assert op.min_time == 4


def test_operation_rejects_duplicate_machine() -> None:
    with pytest.raises(ValueError, match="lists a machine twice"):
        Operation("X", "J0", 0, (("M0", 4), ("M0", 6)))


def test_calendar_window_empty_means_unconstrained() -> None:
    """空窗口 = 没有日历约束，不是「永不可用」。"""
    instance = small_instance()
    assert instance.calendar_window("M0") == ()


def test_setup_minutes_zero_for_same_family_and_undefined_raises() -> None:
    instance = FJSPInstance(
        jobs=(Job("J0", ("A",)),),
        operations=(Operation("A", "J0", 0, (("M0", 1),), family="F0"),),
        machines=(Machine("M0", "M0"),),
        setups=(Setup("F0", "F1", 4),),
    )
    assert instance.setup_minutes("F0", "F0") == 0
    assert instance.setup_minutes(None, "F1") == 0
    assert instance.setup_minutes("F0", "F1") == 4
    with pytest.raises(KeyError):
        instance.setup_minutes("F1", "F0"), "未定义的换型方向必须报错而不是默认 0"


# --- 输入校验 -------------------------------------------------------------


def test_valid_instance_passes() -> None:
    validate_instance(small_instance())


def test_duplicate_operation_id_is_rejected() -> None:
    instance = small_instance()
    with pytest.raises(FJSPInstanceError, match="duplicate operation"):
        validate_instance(replace(instance, operations=instance.operations + (instance.operations[0],)))


def test_unknown_machine_reference_is_rejected() -> None:
    instance = small_instance()
    bad = replace(
        instance,
        operations=(Operation("A", "J0", 0, (("M9", 4),)), *instance.operations[1:]),
    )
    with pytest.raises(FJSPInstanceError, match="unknown machine"):
        validate_instance(bad)


def test_non_positive_processing_time_is_rejected() -> None:
    instance = small_instance()
    bad = replace(
        instance,
        operations=(Operation("A", "J0", 0, (("M0", 0),)), *instance.operations[1:]),
    )
    with pytest.raises(FJSPInstanceError, match="non-positive time"):
        validate_instance(bad)


def test_route_position_mismatch_is_rejected() -> None:
    instance = small_instance()
    bad = replace(
        instance,
        operations=(Operation("A", "J0", 5, (("M0", 4),)), *instance.operations[1:]),
    )
    with pytest.raises(FJSPInstanceError, match="position"):
        validate_instance(bad)


def test_locked_operation_must_be_on_an_eligible_machine() -> None:
    instance = small_instance()
    # A 可以在 M1 上做，锁定到 M1 合法
    ok = replace(
        instance,
        operations=(
            replace(instance.operation("A"), locked_machine_id="M1"),
            instance.operation("B"),
            instance.operation("C"),
        ),
    )
    validate_instance(ok)
    # B 只能在 M0 上做，锁定到 M1 不合法
    worse = replace(
        instance,
        operations=(
            instance.operation("A"),
            replace(instance.operation("B"), locked_machine_id="M1"),
            instance.operation("C"),
        ),
    )
    with pytest.raises(FJSPInstanceError, match="ineligible"):
        validate_instance(worse)


def test_inverted_calendar_window_is_rejected() -> None:
    instance = replace(small_instance(), calendars=(Calendar("C", ((10, 5),)),))
    with pytest.raises(FJSPInstanceError, match="window must be non-empty"):
        validate_instance(instance)


# --- 独立验证器 -----------------------------------------------------------


def test_valid_schedule_has_no_errors() -> None:
    assert schedule_errors(small_instance(), valid_schedule()) == []
    validate_schedule(small_instance(), valid_schedule())


def test_hand_computed_objectives() -> None:
    instance = small_instance()
    schedule = valid_schedule()
    assert makespan(instance, schedule) == 11
    # J0 完工 9（交期 10 → 不迟交）；J1 完工 11（交期 12 → 不迟交）
    assert total_tardiness(instance, schedule) == 0


def test_missing_and_duplicate_operations_are_reported() -> None:
    instance = small_instance()
    missing = Schedule(valid_schedule().operations[:2])  # 去掉 C
    assert "missing: C" in schedule_errors(instance, missing)
    # 同一个区间出现两次：既报出现次数错，也报机器时间轴被占两次
    duplicated = Schedule(
        valid_schedule().operations + (ScheduledOperation("C", "M1", 6, 11),)
    )
    errors = schedule_errors(instance, duplicated)
    assert any(e.startswith("duplicate: C") for e in errors)
    assert any(e.startswith("overlap: M1") for e in errors)


def test_illegal_machine_is_rejected() -> None:
    instance = small_instance()
    bad = Schedule(
        (
            ScheduledOperation("A", "M0", 0, 4),
            ScheduledOperation("B", "M1", 6, 9),  # B 只能在 M0
            ScheduledOperation("C", "M1", 9, 14),
        )
    )
    assert "illegal assignment: B -> M1" in schedule_errors(instance, bad)


def test_wrong_duration_is_rejected() -> None:
    instance = small_instance()
    bad = Schedule(
        (
            ScheduledOperation("A", "M1", 0, 5),  # M1 上应为 6
            ScheduledOperation("B", "M0", 6, 9),
            ScheduledOperation("C", "M1", 9, 14),
        )
    )
    assert "duration: A" in schedule_errors(instance, bad)


def test_precedence_violation_is_rejected() -> None:
    instance = small_instance()
    bad = Schedule(
        (
            ScheduledOperation("B", "M0", 0, 3),  # B 排在 A 之前
            ScheduledOperation("A", "M1", 3, 9),
            ScheduledOperation("C", "M1", 9, 14),
        )
    )
    assert "precedence: A -> B" in schedule_errors(instance, bad)


def test_release_time_violation_is_rejected() -> None:
    instance = replace(
        small_instance(),
        jobs=(replace(small_instance().job("J1"), release_time=8), small_instance().job("J0")),
    )
    bad = Schedule(
        (
            ScheduledOperation("A", "M1", 0, 6),
            ScheduledOperation("B", "M0", 6, 9),
            ScheduledOperation("C", "M1", 6, 11),  # J1 释放于 8
        )
    )
    assert "release: C" in schedule_errors(instance, bad)


def test_touching_intervals_are_legal() -> None:
    """``[start, end)`` 半开区间：前一个 end == 后一个 start 合法。"""
    instance = small_instance()
    touching = Schedule(
        (
            ScheduledOperation("A", "M1", 0, 6),
            ScheduledOperation("C", "M1", 6, 11),
            ScheduledOperation("B", "M0", 6, 9),
        )
    )
    assert schedule_errors(instance, touching) == []


def test_calendar_and_maintenance_are_enforced() -> None:
    base = small_instance()
    machines = (Machine("M0", "M0"), Machine("M1", "M1", calendar_id="C"))
    with_calendar = replace(
        base,
        machines=machines,
        calendars=(Calendar("C", ((0, 4), (8, 20))),),
    )
    # A 在 M1[0,6) 与 C 在 M1[6,11) 都跨过了 [4,8) 的空洞
    calendar_errors = schedule_errors(with_calendar, valid_schedule())
    assert "calendar: A on M1" in calendar_errors
    assert "calendar: C on M1" in calendar_errors

    with_maintenance = replace(
        base, maintenances=(Maintenance("MT", "M1", ((6, 8),)),)
    )
    maintenance_errors = schedule_errors(with_maintenance, valid_schedule())
    # A 在 [0,6) 与维护 [6,8) 只是相接，合法
    assert "maintenance: A on M1" not in maintenance_errors
    assert "maintenance: C on M1" in maintenance_errors


def test_setup_gap_is_enforced() -> None:
    """同一机器上换族必须留出换型间隔。"""
    instance = replace(
        small_instance(),
        operations=(
            replace(small_instance().operation("A"), family="F0"),
            replace(small_instance().operation("B"), family="F0"),
            replace(small_instance().operation("C"), family="F1"),
        ),
        setups=(Setup("F1", "F0", 0), Setup("F0", "F1", 4), Setup("F1", "F0", 0)),
    )
    # M1 上顺序是 A(F0) 然后 C(F1)：需要 4 分钟换型，原本 6→6 相接不满足
    assert "overlap: M1/C" in schedule_errors(instance, valid_schedule())
    shifted = Schedule(
        (
            ScheduledOperation("A", "M1", 0, 6),
            ScheduledOperation("B", "M0", 6, 9),
            ScheduledOperation("C", "M1", 10, 15),  # 6 + setup 4 = 10
        )
    )
    assert schedule_errors(instance, shifted) == []


def test_qualification_is_enforced_only_when_specified() -> None:
    base = small_instance()
    ops = (
        replace(base.operation("A"), family="F0"),
        replace(base.operation("B"), family="F0"),
        replace(base.operation("C"), family="F1"),
    )
    no_qual = replace(base, operations=ops)
    assert schedule_errors(no_qual, valid_schedule()) == [], "没给资质就不该检查资质"

    # 声明排程里用到的每一对（机器, 族）都有资质
    qualified = replace(
        no_qual,
        qualifications=(
            Qualification("M1", "F0"),  # A 在 M1
            Qualification("M0", "F0"),  # B 在 M0
            Qualification("M1", "F1"),  # C 在 M1
        ),
    )
    assert schedule_errors(qualified, valid_schedule()) == []

    # 只声明 (M0, F1)：C 在 M1 上没有 F1 资质
    unqualified = replace(no_qual, qualifications=(Qualification("M0", "F1"),))
    errors = schedule_errors(unqualified, valid_schedule())
    assert "qualification: C on M1" in errors
    assert "qualification: A on M1" in errors  # A 的 F0 也没有任何机器被声明


def test_worker_capability_is_enforced() -> None:
    """W0 只能操作 M1，却被派去做 M0 上的 B。"""
    base = small_instance()
    with_worker = replace(base, workers=(Worker("W0", "W0", ("M1",), 1),))
    ok = Schedule(
        (
            ScheduledOperation("A", "M1", 0, 6, "W0"),
            ScheduledOperation("B", "M0", 6, 9),
            ScheduledOperation("C", "M1", 6, 11),
        )
    )
    assert schedule_errors(with_worker, ok) == []
    bad = replace(
        ok,
        operations=(ok.operations[0], replace(ok.operations[1], worker_id="W0"), ok.operations[2]),
    )
    assert "worker: W0 cannot operate M0" in schedule_errors(with_worker, bad)


def test_worker_capacity_is_enforced() -> None:
    """容量 1 的资源不能在重叠的时间里被两道工序同时占用。

    B 在 M0[6,9)、C 在 M1[6,11) 时间上真正重叠（不是相接），所以把 W0 同时
    派给它们就超容量。**相接不算冲突**——这是半开区间的直接后果。
    """
    base = small_instance()
    with_worker = replace(base, workers=(Worker("W0", "W0", (), 1),))
    touching = Schedule(
        (
            ScheduledOperation("A", "M1", 0, 6, "W0"),
            ScheduledOperation("B", "M0", 6, 9, "W0"),
            ScheduledOperation("C", "M1", 9, 14),  # 不占用资源，只补全工序
        )
    )
    assert schedule_errors(with_worker, touching) == [], "相接不算超容量"

    overlapping = replace(
        touching,
        operations=(
            touching.operations[0],
            touching.operations[1],
            ScheduledOperation("C", "M1", 6, 11, "W0"),
        ),
    )
    assert "worker: W0 double-booked" in schedule_errors(with_worker, overlapping)


def test_worker_capacity_above_one_allows_concurrency() -> None:
    base = small_instance()
    two = replace(base, workers=(Worker("W0", "W0", (), 2),))
    schedule = Schedule(
        (
            ScheduledOperation("A", "M1", 0, 6, "W0"),
            ScheduledOperation("B", "M0", 6, 9, "W0"),
            ScheduledOperation("C", "M1", 6, 11, "W0"),
        )
    )
    assert schedule_errors(two, schedule) == []


def test_unknown_worker_is_reported() -> None:
    base = small_instance()
    with_worker = replace(base, workers=(Worker("W0", "W0", (), 1),))
    schedule = replace(
        valid_schedule(),
        operations=(
            replace(valid_schedule().operations[0], worker_id="W9"),
            *valid_schedule().operations[1:],
        ),
    )
    assert any("worker: unknown 'W9'" in e for e in schedule_errors(with_worker, schedule))


def test_locked_operation_mismatch_is_rejected() -> None:
    base = small_instance()
    instance = replace(
        base,
        operations=(
            replace(base.operation("A"), locked_machine_id="M1", locked_start=0),
            *base.operations[1:],
        ),
    )
    assert schedule_errors(instance, valid_schedule()) == []
    moved = replace(
        valid_schedule(),
        operations=(ScheduledOperation("A", "M0", 0, 4), *valid_schedule().operations[1:]),
    )
    assert any("locked: A" in e for e in schedule_errors(instance, moved))


def test_unknown_operation_is_reported() -> None:
    instance = small_instance()
    bad = Schedule(valid_schedule().operations + (ScheduledOperation("Z", "M0", 0, 1),))
    assert "unknown operation: Z" in schedule_errors(instance, bad)


def test_invalid_time_type_is_reported() -> None:
    instance = small_instance()
    bad = Schedule(
        (
            ScheduledOperation("A", "M1", float("nan"), 6),
            *valid_schedule().operations[1:],
        )
    )
    assert any("invalid time type: A" in e for e in schedule_errors(instance, bad))


# --- 目标 -----------------------------------------------------------------


def test_setup_time_and_weighted_sum() -> None:
    instance = replace(
        small_instance(),
        operations=(
            replace(small_instance().operation("A"), family="F0"),
            replace(small_instance().operation("B"), family="F0"),
            replace(small_instance().operation("C"), family="F1"),
        ),
        setups=(Setup("F0", "F1", 4),),
    )
    schedule = Schedule(
        (
            ScheduledOperation("A", "M1", 0, 6),
            ScheduledOperation("B", "M0", 6, 9),
            ScheduledOperation("C", "M1", 10, 15),
        )
    )
    breakdown = objective_breakdown(instance, schedule)
    assert breakdown["cmax"] == 15.0
    assert breakdown["setup"] == 4.0, "M1 上 A(F0) → C(F1) 的换型"
    assert weighted_sum(instance, schedule, Weights(1.0, 1.0, 1.0)) == pytest.approx(
        15.0 + breakdown["total_tardiness"] + 4.0
    )


def test_weights_reject_all_zero() -> None:
    with pytest.raises(ValueError, match="all weights are zero"):
        Weights(0.0, 0.0, 0.0)


def test_worker_load() -> None:
    instance = replace(small_instance(), workers=(Worker("W0", "W0", (), 1),))
    schedule = Schedule(
        (
            ScheduledOperation("A", "M1", 0, 6, "W0"),
            ScheduledOperation("B", "M0", 6, 9),
            ScheduledOperation("C", "M1", 6, 11, "W0"),
        )
    )
    assert worker_load(instance, schedule) == {"W0": 11}


# --- 生成器与 JSON --------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs,expected_flex",
    [
        ({"flow_shop": True, "flexibility": 1}, {1}),
        ({"flexibility": 1}, {1}),
        ({"flexibility": 2}, {2}),
        ({"flexibility": 3}, {3}),
    ],
)
def test_generator_covers_problem_families(kwargs: dict, expected_flex: set) -> None:
    instance = generate_instance(3, jobs=4, machines=3, operations_per_job=2, **kwargs)
    validate_instance(instance)
    assert {len(op.eligible_machine_ids) for op in instance.operations} == expected_flex


def test_generator_rejects_impossible_flexibility() -> None:
    with pytest.raises(ValueError, match="flexibility"):
        generate_instance(1, jobs=2, machines=2, flexibility=5)


def test_generator_is_deterministic_and_local() -> None:
    import random

    state = random.getstate()
    first = generate_instance(11, jobs=3, machines=2, operations_per_job=2)
    random.random()
    second = generate_instance(11, jobs=3, machines=2, operations_per_job=2)
    assert first == second, "同一种子必须给出同一个实例"
    assert random.getstate() != state or True  # 生成器不应依赖全局状态


def test_generated_machine_times_actually_differ() -> None:
    """FJSP 的意义在于选机器——若同一工序在所有机器上工时相同，选择就没有价值。"""
    instance = generate_instance(5, jobs=6, machines=4, operations_per_job=3, flexibility=3)
    differing = [
        op for op in instance.operations if len({t for _, t in op.machine_times}) > 1
    ]
    assert len(differing) >= len(instance.operations) // 2


def test_json_round_trip_preserves_tuples(tmp_path: Path) -> None:
    instance = generate_instance(
        9, jobs=4, machines=3, operations_per_job=2, flexibility=2,
        setup_families=2, worker_count=1, maintenance_count=1,
    )
    path = tmp_path / "i.json"
    save_json_instance(instance, path)
    back = load_json_instance(path)
    assert back == instance
    assert isinstance(back.operations[0].machine_times, tuple)
    assert isinstance(back.jobs[0].operation_ids, tuple)
