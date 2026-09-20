"""M3 Week 3 测试：工业约束 I —— 释放时间、sequence-dependent setup、日历/维护、加权多目标。

对拍纪律（与 M1/M2 相同）：**期望值来自手写时间线**，不由被测代码生成；
凡是「某个排程不合法」的用例，都**手工构造**那个排程，再断言独立验证器给出的
诊断标签——不是拿求解器的输出当反例。

手算实例一览（全部在本文件里显式重建）：

```text
S1   M0: B(6, F1), C(3, F1)；M1: A(4→5, F0)   换型 F0->F1 = 5, F1->F0 = 7
     A 走 M1  -> M0 上只剩同族 F1，Cmax = 9，setup = 0
     A 锁 M0  -> M0 顺序 A,B,C，Cmax = 18，setup = 5（A->B 一次换型）
G1   M0 只有换型：A(2, F0), B(2, F1), C(2, F1)  换型 F0->F1 = 3, F1->F0 = 4
     最优顺序 A,B,C -> Cmax = 9，setup = 3（B->C 同族，间隔为 0）
C1   M0 日历 [(0,5),(10,20)] + 维护 (5,10)：X(4), Y(3)  -> Cmax = 13
M1   M0 单机：A(6, F0, d=100), B(2, F1, d=1)   换型 F0->F1 = 1, F1->F0 = 5
     A 先：(Cmax 9, ΣT 8, setup 1)；B 先：(Cmax 13, ΣT 1, setup 5)
     -> α 与 β 的权重取舍在这里是**真实**的，不是搜索噪声
```
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from fjsp_core import (
    Calendar,
    FJSPInstance,
    Job,
    Machine,
    Maintenance,
    Operation,
    Schedule,
    ScheduledOperation,
    Setup,
    Weights,
    makespan,
    objective_breakdown,
    schedule_errors,
    total_setup_time,
    total_tardiness,
    validate_schedule,
    weighted_sum,
)
from fjsp_io import generate_instance
from fjsp_shop.registry import get, load_week_modules

WEEK3_METHODS = ("fjsp_cpsat_setup", "fjsp_cpsat_calendar", "fjsp_cpsat_multiobj")


@pytest.fixture(scope="module", autouse=True)
def _loaded() -> None:
    load_week_modules()


def _solve(method: str, instance: FJSPInstance, **spec):
    spec.setdefault("time_limit", 5.0)
    spec.setdefault("seed", 0)
    return get(method)(instance, spec)


def _sorted(schedule: Schedule) -> list[ScheduledOperation]:
    return sorted(schedule.operations, key=lambda item: (item.machine_id, item.start_time))


# ---------------------------------------------------------------------------
# 手算实例
# ---------------------------------------------------------------------------


def s1_with_m1() -> FJSPInstance:
    """S1：A 可以在 M0(4) 或 M1(5) 上做，B/C 只能在 M0 上，B 与 C 同族 F1。"""
    return FJSPInstance(
        jobs=(Job("J0", ("A",)), Job("J1", ("B",)), Job("J2", ("C",))),
        operations=(
            Operation("A", "J0", 0, (("M0", 4), ("M1", 5)), family="F0"),
            Operation("B", "J1", 0, (("M0", 6),), family="F1"),
            Operation("C", "J2", 0, (("M0", 3),), family="F1"),
        ),
        machines=(Machine("M0", "M0"), Machine("M1", "M1")),
        setups=(Setup("F0", "F1", 5), Setup("F1", "F0", 7)),
    )


def s1_locked_to_m0() -> FJSPInstance:
    """S1 的变体：把 A 锁死在 M0（WIP 语义），于是 M0 上必然发生一次 F0->F1 换型。"""
    base = s1_with_m1()
    return FJSPInstance(
        jobs=base.jobs,
        operations=(
            Operation("A", "J0", 0, (("M0", 4),), family="F0", locked_machine_id="M0"),
            *base.operations[1:],
        ),
        machines=base.machines,
        setups=base.setups,
    )


def same_family_instance() -> FJSPInstance:
    """G1：三台单一机器的工序都挤在 M0 上，其中 B 与 C 同族。"""
    return FJSPInstance(
        jobs=(Job("J0", ("A",)), Job("J1", ("B",)), Job("J2", ("C",))),
        operations=(
            Operation("A", "J0", 0, (("M0", 2),), family="F0"),
            Operation("B", "J1", 0, (("M0", 2),), family="F1"),
            Operation("C", "J2", 0, (("M0", 2),), family="F1"),
        ),
        machines=(Machine("M0", "M0"),),
        setups=(Setup("F0", "F1", 3), Setup("F1", "F0", 4)),
    )


def calendar_instance() -> FJSPInstance:
    """C1：M0 的日历只有 [(0,5),(10,20)] 两段可用。"""
    return FJSPInstance(
        jobs=(Job("J0", ("X",)), Job("J1", ("Y",))),
        operations=(
            Operation("X", "J0", 0, (("M0", 4),)),
            Operation("Y", "J1", 0, (("M0", 3),)),
        ),
        machines=(Machine("M0", "M0", calendar_id="CAL"),),
        calendars=(Calendar("CAL", ((0, 5), (10, 20))),),
    )


def maintenance_instance() -> FJSPInstance:
    """M0 没有日历，只在 [2,6) 计划维护。"""
    return FJSPInstance(
        jobs=(Job("J0", ("X",)), Job("J1", ("Y",))),
        operations=(
            Operation("X", "J0", 0, (("M0", 4),)),
            Operation("Y", "J1", 0, (("M0", 3),)),
        ),
        machines=(Machine("M0", "M0"),),
        maintenances=(Maintenance("MT", "M0", ((2, 6),)),),
    )


def calendar_and_maintenance_instance() -> FJSPInstance:
    """C1 加上维护窗 (5,10)，正好把两段日历之间的空洞也挖掉。"""
    base = calendar_instance()
    return FJSPInstance(
        jobs=base.jobs,
        operations=base.operations,
        machines=base.machines,
        calendars=base.calendars,
        maintenances=(Maintenance("MT", "M0", ((5, 10),)),),
    )


def tradeoff_instance() -> FJSPInstance:
    """M1：手算过的权重取舍实例（见模块 docstring）。"""
    return FJSPInstance(
        jobs=(Job("J0", ("A",), 0, 100), Job("J1", ("B",), 0, 1)),
        operations=(
            Operation("A", "J0", 0, (("M0", 6),), family="F0"),
            Operation("B", "J1", 0, (("M0", 2),), family="F1"),
        ),
        machines=(Machine("M0", "M0"),),
        setups=(Setup("F0", "F1", 1), Setup("F1", "F0", 5)),
    )


def g2_machine_choice() -> FJSPInstance:
    """G2：换型与完工时间**真的打架**的实例（见该用例的 docstring）。

    ``X`` 是同族 ``F0``，它在 M0 上插队不花换型；但 M0 被 ``A(100)`` 占满，
    插进去会把 ``Cmax`` 从 100 顶到 101。于是「省一次换型」与「早一分钟完工」
    各选一台机器，谁也不能同时拿下两个目标。
    """
    return FJSPInstance(
        jobs=(Job("J0", ("A",)), Job("J1", ("B",)), Job("J2", ("X",))),
        operations=(
            Operation("A", "J0", 0, (("M0", 100),), family="F0"),
            Operation("B", "J1", 0, (("M1", 1),), family="F1"),
            Operation("X", "J2", 0, (("M0", 1), ("M1", 1)), family="F0"),
        ),
        machines=(Machine("M0", "M0"), Machine("M1", "M1")),
        setups=(Setup("F0", "F1", 5), Setup("F1", "F0", 5)),
    )


# ---------------------------------------------------------------------------
# 1. 释放时间真的把开工往后推
# ---------------------------------------------------------------------------


def test_release_time_delays_the_start() -> None:
    """手算：X 释放于 5（p=4）→ [5,9)；Y 释放于 9（p=3）→ [9,12)，Cmax = 12。"""
    instance = FJSPInstance(
        jobs=(Job("J0", ("X",), 5), Job("J1", ("Y",), 9)),
        operations=(
            Operation("X", "J0", 0, (("M0", 4),)),
            Operation("Y", "J1", 0, (("M0", 3),)),
        ),
        machines=(Machine("M0", "M0"),),
    )
    result = _solve("fjsp_cpsat_setup", instance, objective="makespan")
    assert result.status == "OPTIMAL"
    assert result.objective == 12
    by_id = result.schedule.by_operation()
    assert by_id["X"].start_time == 5, "释放时间 5 之前不许开工"
    assert by_id["Y"].start_time == 9
    validate_schedule(instance, result.schedule)

    # 手工构造一个「无视释放时间」的排程，验证器必须报 release
    early = Schedule(
        (
            ScheduledOperation("X", "M0", 0, 4),
            ScheduledOperation("Y", "M0", 4, 7),
        )
    )
    assert "release: X" in schedule_errors(instance, early)
    assert "release: Y" in schedule_errors(instance, early)


# ---------------------------------------------------------------------------
# 2. 日历 / 维护：手工构造的违规排程必须被独立验证器拒绝
# ---------------------------------------------------------------------------


def test_calendar_window_violation_is_rejected() -> None:
    """跨过 [5,10) 这段日历空洞的排程，必须被报 ``calendar``。"""
    instance = calendar_instance()
    inside = Schedule(
        (
            ScheduledOperation("X", "M0", 0, 4),
            ScheduledOperation("Y", "M0", 10, 13),
        )
    )
    validate_schedule(instance, inside)  # 手算的两个区间都在可用窗内

    crossing = Schedule(
        (
            ScheduledOperation("X", "M0", 3, 7),  # [3,7) 既不在 (0,5) 也不在 (10,20)
            ScheduledOperation("Y", "M0", 10, 13),
        )
    )
    errors = schedule_errors(instance, crossing)
    assert "calendar: X on M0" in errors, "工序整体落在某一个可用窗内才不会报 calendar"
    assert not any(item.startswith("maintenance") for item in errors), (
        "本实例没有维护窗，诊断里不该出现 maintenance"
    )


def test_maintenance_overlap_is_rejected_but_touching_is_legal() -> None:
    """与维护窗重叠报 ``maintenance``；只是**相接**（end == 维护开始）合法。"""
    instance = maintenance_instance()
    overlapping = Schedule(
        (
            ScheduledOperation("X", "M0", 3, 7),  # 与 (2,6) 真正重叠
            ScheduledOperation("Y", "M0", 7, 10),
        )
    )
    assert "maintenance: X on M0" in schedule_errors(instance, overlapping)

    touching = Schedule(
        (
            ScheduledOperation("Y", "M0", 6, 9),  # 6 == 维护结束，相接
            ScheduledOperation("X", "M0", 9, 13),
        )
    )
    validate_schedule(instance, touching)

    # 求解器给出的排程同样不能碰维护窗：
    # 可用区的第一段 [0,2) 连最短的 Y(3) 都放不下，所以两道工序只能在 6 之后排，
    # 手算 Cmax = 6 + (4 + 3) = 13。
    result = _solve("fjsp_cpsat_calendar", instance, objective="makespan")
    assert result.objective == 13
    assert all(item.start_time >= 6 for item in result.schedule.operations)
    ordered = _sorted(result.schedule)
    assert ordered[0].end_time == ordered[1].start_time, "同一台机器上不重叠也不该故意空转"
    validate_schedule(instance, result.schedule)


def test_calendar_plus_maintenance_hand_computed_optimum() -> None:
    """C1 + 维护 (5,10)：可用区段只剩 [0,5) 与 [10,20)，手算最优 Cmax = 13。"""
    instance = calendar_and_maintenance_instance()
    assert instance.calendar_window("M0") == ((0, 5), (10, 20))
    result = _solve("fjsp_cpsat_calendar", instance, objective="makespan")
    assert result.status == "OPTIMAL"
    assert result.objective == 13
    ordered = _sorted(result.schedule)
    assert (ordered[0].start_time, ordered[0].end_time) == (0, 4)
    assert (ordered[1].start_time, ordered[1].end_time) == (10, 13)
    validate_schedule(instance, result.schedule)


def test_calendar_encodings_agree() -> None:
    """``split`` / ``blocker`` 两条日历编码共用同一份几何计算，最优值必须相同。"""
    instance = calendar_and_maintenance_instance()
    split = _solve("fjsp_cpsat_calendar", instance, objective="makespan")
    blocker = _solve("fjsp_cpsat_setup", instance, objective="makespan")
    assert split.status == blocker.status == "OPTIMAL"
    assert split.objective == blocker.objective == 13
    validate_schedule(instance, split.schedule)
    validate_schedule(instance, blocker.schedule)


def test_operation_that_fits_no_window_is_infeasible() -> None:
    """日历总长 4、工序要 10：建模阶段就能判定不可行，不该返回一个坏排程。"""
    instance = FJSPInstance(
        jobs=(Job("J0", ("X",)),),
        operations=(Operation("X", "J0", 0, (("M0", 10),)),),
        machines=(Machine("M0", "M0", calendar_id="CAL"),),
        calendars=(Calendar("CAL", ((0, 4),)),),
    )
    for method in ("fjsp_cpsat_setup", "fjsp_cpsat_calendar"):
        result = _solve(method, instance, objective="makespan")
        assert result.status == "INFEASIBLE"
        assert result.schedule is None
        assert "fits in no allowed window" in result.detail["failure_reason"]


# ---------------------------------------------------------------------------
# 3. sequence-dependent setup：换型真的变成一段间隔
# ---------------------------------------------------------------------------


def _machine_gaps(instance: FJSPInstance, schedule: Schedule) -> list[tuple[str, int, int]]:
    """机器时间轴上每对相邻工序的 ``(前一道, 间隔, 后一道)``，间隔按时间差算。"""
    by_machine: dict[str, list[ScheduledOperation]] = {}
    for item in schedule.operations:
        by_machine.setdefault(item.machine_id, []).append(item)
    gaps: list[tuple[str, int, int]] = []
    for items in by_machine.values():
        ordered = sorted(items, key=lambda item: item.start_time)
        for previous, current in zip(ordered, ordered[1:]):
            gaps.append(
                (previous.operation_id, current.start_time - previous.end_time, current.operation_id)
            )
    return gaps


def test_setup_gap_between_different_families_and_zero_within_one() -> None:
    """手算 G1：F0 与 F1 之间留 3 分钟换型，两个 F1 之间间隔为 0。

    A(F0) 必须先做（它走别的机器也没有，M0 是唯一机器），之后两道 F1 工序的
    先后由求解器自由决定——所以断言写成**对顺序不敏感**的形式：先 A，换型一次，
    然后同族紧接。手算 Cmax = 2 + 3 + 2 + 2 = 9。
    """
    instance = same_family_instance()
    result = _solve("fjsp_cpsat_setup", instance, objective="makespan")
    assert result.status == "OPTIMAL"
    assert result.objective == 9
    ordered = _sorted(result.schedule)
    assert [item.operation_id for item in ordered][0] == "A", "F0 先做才不用付 F1->F0 的 4 分钟"
    assert (ordered[0].start_time, ordered[0].end_time) == (0, 2)
    assert ordered[1].start_time == 5, "2 + setup(F0->F1) = 5"
    assert ordered[1].end_time == ordered[2].start_time, "同族 F1 不换型，紧接开工"
    assert ordered[2].end_time == 9
    assert _machine_gaps(instance, result.schedule) == [("A", 3, ordered[1].operation_id), (ordered[1].operation_id, 0, ordered[2].operation_id)]
    assert result.breakdown["setup"] == 3.0
    assert total_setup_time(instance, result.schedule) == 3
    validate_schedule(instance, result.schedule)

    # 少留换型的排程必须被拒绝：overlap 诊断就是「换型间隔不足」的表现
    too_tight = Schedule(
        (
            ScheduledOperation("A", "M0", 0, 2),
            ScheduledOperation("B", "M0", 2, 4),  # 缺 3 分钟换型
            ScheduledOperation("C", "M0", 4, 6),
        )
    )
    assert "overlap: M0/B" in schedule_errors(instance, too_tight)


def test_setup_changes_the_machine_choice() -> None:
    """手算 S1：A 放在 M1（5 分钟）比放在 M0（4 分钟）更好，因为 M0 上会多一次换型。"""
    instance = s1_with_m1()
    result = _solve("fjsp_cpsat_setup", instance, objective="makespan")
    assert result.status == "OPTIMAL"
    assert result.objective == 9, "A 走 M1 → M0 上只剩同族 F1 的 B(6)+C(3)"
    assert result.breakdown["setup"] == 0.0
    by_id = result.schedule.by_operation()
    assert by_id["A"].machine_id == "M1", "选机器不能只看 min_time，还要看换型代价"
    validate_schedule(instance, result.schedule)


def test_locked_operation_forces_the_setup_gap() -> None:
    """手算 S1 锁定版：A 锁死 M0 → Cmax 18、setup 5，间隔 [4,9) 恰好是换型时间。

    手算：A(F0) 必须最先做（放最后要付 F1->F0 的 7 分钟，Cmax 变 20）。
    之后两道 F1 工序紧接，所以 M0 时间线是 ``[0,4) 空 5 [9,12) 紧接 [12,18)``。
    """
    instance = s1_locked_to_m0()
    result = _solve("fjsp_cpsat_setup", instance, objective="makespan")
    assert result.status == "OPTIMAL"
    assert result.objective == 18
    assert result.breakdown["setup"] == 5.0
    ordered = _sorted(result.schedule)
    assert ordered[0].operation_id == "A"
    assert ordered[0].machine_id == "M0" and ordered[0].start_time == 0
    assert ordered[1].start_time == 9, "4 + setup(F0->F1) = 9"
    assert ordered[1].end_time == ordered[2].start_time
    assert ordered[2].end_time == 18
    assert _machine_gaps(instance, result.schedule) == [
        ("A", 5, ordered[1].operation_id),
        (ordered[1].operation_id, 0, ordered[2].operation_id),
    ]
    validate_schedule(instance, result.schedule)


def test_setup_objective_picks_the_low_setup_order() -> None:
    """M1 实例：换成 ``total_setup_time`` 目标，仍然选 A 先（A->B 只要 1 分钟换型）。

    注意这条用例**不能**说成「换目标就换顺序」——M1 实例上的单机恒等式
    ``Cmax = Σp + Σsetup`` 决定了「换型最少」与「完工最早」在同一顺位上重合。
    真正会分道扬镳的是多机器下的机器选择，见下一条用例。
    """
    instance = tradeoff_instance()
    by_setup = _solve("fjsp_cpsat_setup", instance, objective="total_setup_time")
    assert by_setup.status == "OPTIMAL"
    assert by_setup.breakdown["setup"] == 1.0, "A 先做时 A->B 的换型只有 1 分钟"
    assert total_setup_time(instance, by_setup.schedule) == 1
    validate_schedule(instance, by_setup.schedule)


def test_setup_objective_and_makespan_objective_disagree_on_machine_choice() -> None:
    """手算 G2：``min Cmax`` 与 ``min setup`` 选出**不同机器**，彼此都不占优。

    ```text
    M0: A(100, F0)                M1: B(1, F1)
    X(1 on M0 / 1 on M1, F0)      换型 F0<->F1 都是 5

    X 走 M1: M1 = 1 + 5 + 1 = 7，M0 = 100   -> Cmax 100，setup 5
    X 走 M0: M0 = 100 + 0 + 1 = 101         -> Cmax 101，setup 0
    ```
    """
    instance = g2_machine_choice()
    by_cmax = _solve("fjsp_cpsat_setup", instance, objective="makespan")
    by_setup = _solve("fjsp_cpsat_setup", instance, objective="total_setup_time")
    assert by_cmax.status == "OPTIMAL" and by_setup.status == "OPTIMAL"
    # objective 是各自的目标值（Cmax / setup），breakdown 里两边的两个分量都要看
    assert (by_cmax.objective, by_cmax.breakdown["cmax"], by_cmax.breakdown["setup"]) == (
        100.0, 100.0, 5.0,
    )
    assert (by_setup.objective, by_setup.breakdown["cmax"], by_setup.breakdown["setup"]) == (
        0.0, 101.0, 0.0,
    )
    assert by_cmax.schedule.by_operation()["X"].machine_id == "M1"
    assert by_setup.schedule.by_operation()["X"].machine_id == "M0"
    # 两条排程都不满足对方的目标：没有哪一条能同时拿下 Cmax 100 与 setup 0。
    validate_schedule(instance, by_cmax.schedule)
    validate_schedule(instance, by_setup.schedule)


# ---------------------------------------------------------------------------
# 4. 多目标：与手算加权和对拍
# ---------------------------------------------------------------------------


def test_multiobj_matches_hand_computed_weighted_sum() -> None:
    """M1 上 β=4：最优排程是 B 先（13, 1, 5），手算加权和 13 + 4×1 + 0 = 17。"""
    instance = tradeoff_instance()
    weights = Weights(1.0, 4.0, 0.0)
    result = _solve(
        "fjsp_cpsat_multiobj",
        instance,
        objective="weighted_sum",
        weights={"alpha": 1.0, "beta": 4.0, "gamma": 0.0},
        normalization={"mode": "none"},  # 原始单位，便于和手算直接对拍
    )
    assert result.objective == 17.0
    assert result.breakdown == {"cmax": 13.0, "total_tardiness": 1.0, "setup": 5.0}
    assert weighted_sum(instance, result.schedule, weights) == 17.0


def test_multiobj_breakdown_always_filled() -> None:
    """三个方法都必须填 ``breakdown``：只报一个加权和会把分量取舍藏起来。"""
    instance = tradeoff_instance()
    for method in WEEK3_METHODS:
        spec = {"objective": "weighted_sum", "weights": {"alpha": 1.0, "beta": 1.0, "gamma": 0.0}}
        result = _solve(method, instance, **spec)
        assert set(result.breakdown) == {"cmax", "total_tardiness", "setup"}, method
        assert result.objective == pytest.approx(
            weighted_sum(instance, result.schedule, Weights(1.0, 1.0, 0.0))
        ), method
        validate_schedule(instance, result.schedule)


def test_weight_sensitivity_changes_the_chosen_schedule() -> None:
    """本实例上 α 与 β 的取舍是**真实**的：β 从 0 提到 1 就换了排程。"""
    instance = tradeoff_instance()
    cheap_cmax = _solve(
        "fjsp_cpsat_multiobj",
        instance,
        objective="weighted_sum",
        weights={"alpha": 1.0, "beta": 0.0, "gamma": 0.0},
    )
    timely = _solve(
        "fjsp_cpsat_multiobj",
        instance,
        objective="weighted_sum",
        weights={"alpha": 1.0, "beta": 1.0, "gamma": 0.0},
    )
    first_cmax = cheap_cmax.schedule.by_operation()
    first_timely = timely.schedule.by_operation()
    assert first_cmax["A"].start_time < first_cmax["B"].start_time, "β=0：先做长活压 Cmax"
    assert first_timely["B"].start_time < first_timely["A"].start_time, "β=1：先做急单压迟交"
    assert cheap_cmax.breakdown["total_tardiness"] > timely.breakdown["total_tardiness"]
    assert cheap_cmax.breakdown["cmax"] < timely.breakdown["cmax"]
    assert cheap_cmax.objective == 9.0 and timely.objective == 14.0


# ---------------------------------------------------------------------------
# 5. 归一化的口径必须在报告里看得见
# ---------------------------------------------------------------------------


def test_normalization_mode_is_recorded_and_changes_the_bound_story() -> None:
    """``none`` 时模型目标就是报告目标，可以报界；``trivial`` 时不行——必须写 None。"""
    instance = tradeoff_instance()
    raw = _solve(
        "fjsp_cpsat_multiobj",
        instance,
        objective="weighted_sum",
        weights={"alpha": 1.0, "beta": 1.0, "gamma": 0.0},
        normalization={"mode": "none"},
    )
    assert raw.status == "OPTIMAL"
    assert raw.best_bound == raw.objective == 14.0

    normalized = _solve(
        "fjsp_cpsat_multiobj",
        instance,
        objective="weighted_sum",
        weights={"alpha": 1.0, "beta": 1.0, "gamma": 0.0},
    )
    assert normalized.detail["normalization"]["mode"] == "trivial"
    assert normalized.status == "FEASIBLE", "求解器证明的是归一化目标，不是报告的目标"
    assert normalized.best_bound is None, "另有一个函数的下界不能冒充这个函数的下界"
    assert normalized.detail["model_status"] == "OPTIMAL"


def test_unknown_objective_and_unknown_normalization_are_failed() -> None:
    instance = tradeoff_instance()
    bad_objective = _solve("fjsp_cpsat_setup", instance, objective="no_such_objective")
    assert bad_objective.status == "FAILED"
    assert bad_objective.schedule is None
    bad_mode = _solve(
        "fjsp_cpsat_multiobj",
        instance,
        objective="weighted_sum",
        weights={"alpha": 1.0},
        normalization={"mode": "made_up"},
    )
    assert bad_mode.status == "FAILED"
    assert "unknown normalization mode" in bad_mode.detail["failure_reason"]


# ---------------------------------------------------------------------------
# 6. 三个方法在完整工业实例上的共同底线
# ---------------------------------------------------------------------------


def industrial_instance() -> FJSPInstance:
    """日历 + 维护 + 换型 + 释放时间同时打开的实例（每个方法都必须全遵守）。"""
    return generate_instance(
        201,
        jobs=4,
        machines=3,
        operations_per_job=2,
        flexibility=2,
        setup_families=2,
        calendar_windows=1,
        maintenance_count=2,
        release_max=5,
    )


@pytest.mark.parametrize("method", WEEK3_METHODS)
def test_every_method_returns_a_validator_approved_schedule(method: str) -> None:
    instance = industrial_instance()
    result = _solve(method, instance, objective="makespan")
    assert result.status in ("OPTIMAL", "FEASIBLE")
    assert result.schedule is not None
    assert schedule_errors(instance, result.schedule) == [], "求解器的输出必须过独立验证器"
    assert makespan(instance, result.schedule) == result.objective
    assert result.breakdown == objective_breakdown(instance, result.schedule)
    assert result.breakdown["cmax"] == makespan(instance, result.schedule)
    assert result.breakdown["total_tardiness"] == total_tardiness(instance, result.schedule)
    assert result.breakdown["setup"] == total_setup_time(instance, result.schedule)


@pytest.mark.parametrize("method", WEEK3_METHODS)
def test_methods_agree_on_the_same_instance(method: str) -> None:
    """同一实例、同一目标下三个模型的最优值必须一致（约束集相同，只是编码不同）。"""
    instance = generate_instance(
        202, jobs=4, machines=3, operations_per_job=2, flexibility=2, setup_families=2
    )
    baseline = _solve("fjsp_cpsat_setup", instance, objective="makespan")
    result = _solve(method, instance, objective="makespan")
    assert result.status == baseline.status == "OPTIMAL"
    assert result.objective == baseline.objective


def test_determinism_same_spec_same_schedule() -> None:
    """单线程搜索 + 固定种子：同一实例同一 spec 必须给出同一个排程。"""
    instance = industrial_instance()
    first = _solve("fjsp_cpsat_multiobj", instance, objective="makespan", time_limit=2.0)
    second = _solve("fjsp_cpsat_multiobj", instance, objective="makespan", time_limit=2.0)
    assert first.schedule == second.schedule
    assert first.objective == second.objective
