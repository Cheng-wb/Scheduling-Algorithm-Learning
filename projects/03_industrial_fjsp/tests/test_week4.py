"""Week 4 测试：资质 / 次生资源 / batching 换型 / WIP 锁定 / 优先级的建模与验证。

和 ``test_foundation.py`` 一样，**期望值来自手写时间线**，不由被测代码生成：
每个实例都配一条手算排程，先证明「手工排程确实通过验证器」，再故意破坏它，
证明验证器报出的是**那一条**诊断而不是碰巧报了点别的。

后半段是「模型覆盖表确实没在说谎」的机械核对：
:data:`MODEL_COVERAGE` 每一行声明的字段，必须真的出现在验证器或求解器的源码里。
这条检查是防「文档漂移」的——表里写「已覆盖」而代码里没有，是最贵的一种错。
"""

from __future__ import annotations

import inspect
import json
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
    Qualification,
    Schedule,
    ScheduledOperation,
    Setup,
    Worker,
    schedule_errors,
    validate_schedule,
)
from fjsp_core.result import ShopResult, validate_result
from fjsp_io.generator import generate_instance
from fjsp_io.json_bundle import (
    BUNDLE_SCHEMA,
    bundles_equal,
    load_bundle,
    make_bundle,
    save_bundle,
)
from fjsp_io.kpi import kpi_report, normalize
from fjsp_shop import constraints2
from fjsp_shop.constraints2 import MODEL_COVERAGE, qualified_machine_ids
from fjsp_shop.registry import get, load_week_modules

# ---------------------------------------------------------------------------
# 手算实例 1：资质 + 次生资源
# ---------------------------------------------------------------------------
# 机器 M0 / M1；工序族 F0 / F1。
# 资质只发两张：(M0, F0) 与 (M1, F1) —— 即 F0 只能在 M0 上做、F1 只能在 M1 上做。
# 工人：W0 只管 M0，W1 只管 M1（cap 1），W2 两台都能开（cap 1）。
#
# 手算排程：
#   A(F0, M0=5) 在 M0[0,5)  → 需要 W0 或 W2
#   C(F1, M1=3) 在 M1[0,3)  → 需要 W1 或 W2
#   B(F1, M1=4) 在 M1[5,9)  → 需要 W1 或 W2（J0 内 A→B，5 >= 5 满足 precedence）
#   Cmax = 9
def qualified_instance() -> FJSPInstance:
    return FJSPInstance(
        jobs=(
            Job("J0", ("A", "B"), release_time=0, due_date=8),
            Job("J1", ("C",), release_time=0, due_date=4),
        ),
        operations=(
            # A 在 M0 与 M1 上**都能加工**，但资质只发了 (M0, F0)：
            # 这样「放到 M1」违反的才是资质，而不是「这道工序本来就不会上 M1」。
            Operation("A", "J0", 0, (("M0", 5), ("M1", 6)), family="F0"),
            Operation("B", "J0", 1, (("M1", 4),), family="F1"),
            Operation("C", "J1", 0, (("M1", 3),), family="F1"),
        ),
        machines=(Machine("M0", "M0"), Machine("M1", "M1")),
        qualifications=(
            Qualification("M0", "F0"),
            Qualification("M1", "F1"),
        ),
        workers=(
            Worker("W0", "小张", ("M0",), 1),
            Worker("W1", "小李", ("M1",), 1),
            Worker("W2", "多面手", ("M0", "M1"), 1),
        ),
    )


def qualified_schedule() -> Schedule:
    return Schedule(
        (
            ScheduledOperation("A", "M0", 0, 5, worker_id="W0"),
            ScheduledOperation("C", "M1", 0, 3, worker_id="W1"),
            ScheduledOperation("B", "M1", 5, 9, worker_id="W1"),
        )
    )


def test_qualified_baseline_schedule_is_valid() -> None:
    """先证明手算排程本身是干净的，后面所有「破坏它」的测试才有意义。"""
    assert schedule_errors(qualified_instance(), qualified_schedule()) == []
    validate_schedule(qualified_instance(), qualified_schedule())


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        # A 是 F0，资质只允许 M0。放到 M1 上必须被拒。
        (
            lambda items: [
                ScheduledOperation("A", "M1", 0, 6, worker_id="W2"),
                ScheduledOperation("C", "M1", 6, 9, worker_id="W1"),
                ScheduledOperation("B", "M1", 9, 13, worker_id="W1"),
            ],
            "qualification: A on M1",
        ),
        # W0 的 machine_ids 只有 M0，让它开 M1 必须被拒。
        (
            lambda items: [
                ScheduledOperation("A", "M0", 0, 5, worker_id="W0"),
                ScheduledOperation("C", "M1", 0, 3, worker_id="W0"),
                ScheduledOperation("B", "M1", 5, 9, worker_id="W1"),
            ],
            "worker: W0 cannot operate M1",
        ),
        # W1 容量 1，两段重叠必须被拒。
        (
            lambda items: [
                ScheduledOperation("A", "M0", 0, 5, worker_id="W0"),
                ScheduledOperation("C", "M1", 2, 5, worker_id="W1"),
                ScheduledOperation("B", "M1", 0, 4, worker_id="W1"),
            ],
            "worker: W1 double-booked",
        ),
    ],
)
def test_qualified_instance_rejections(mutate, expected: str) -> None:
    errors = schedule_errors(qualified_instance(), Schedule(tuple(mutate(None))))
    assert expected in errors, errors


def test_worker_touching_intervals_are_legal() -> None:
    """``[start, end)`` 半开区间：前一段的 end 等于后一段的 start 不算冲突。

    这是整个 M3 反复出现的口径，也是一条容易写错的边界 ——
    如果实现里用了 ``<=`` 而不是 ``<``，紧贴的排程会被误判为资源冲突，
    而紧贴恰恰是**最优排程最常见的形态**。
    """
    # W2 先在 M0 上做到 5，紧接着在 M1 上从 5 开始 —— 两段相接，合法。
    # 如果实现里把边界写成 ``start <= previous_end`` 就会误报 double-booked，
    # 而「紧贴」恰恰是最优排程最常见的形态。
    schedule = Schedule(
        (
            ScheduledOperation("A", "M0", 0, 5, worker_id="W2"),
            ScheduledOperation("C", "M1", 5, 8, worker_id="W2"),
            ScheduledOperation("B", "M1", 8, 12, worker_id="W1"),
        )
    )
    assert schedule_errors(qualified_instance(), schedule) == []


def test_worker_multi_capacity_peak_check() -> None:
    """``capacity > 1`` 走事件点扫描：峰值不超过容量就合法。

    手算三条同区间 [0,10) 的占用、容量 2：进入 0 之后同时为 3 → peak 3 > 2。
    去掉任意一条 → peak 2，合法。
    """
    def instance(capacity: int) -> FJSPInstance:
        return FJSPInstance(
            jobs=(Job("J0", ("A", "B", "C"), release_time=0),),
            operations=(
                Operation("A", "J0", 0, (("M0", 10),)),
                Operation("B", "J0", 1, (("M1", 10),)),
                Operation("C", "J0", 2, (("M2", 10),)),
            ),
            machines=(Machine("M0", "M0"), Machine("M1", "M1"), Machine("M2", "M2")),
            workers=(Worker("W0", "班组", ("M0", "M1", "M2"), capacity),),
        )

    # precedence 不成立（三条同时开工），但本测试只关心 worker 诊断，
    # 所以断言用的是「诊断里有没有那一条」而不是「诊断为空」。
    overlapping = Schedule(
        (
            ScheduledOperation("A", "M0", 0, 10, worker_id="W0"),
            ScheduledOperation("B", "M1", 0, 10, worker_id="W0"),
            ScheduledOperation("C", "M2", 0, 10, worker_id="W0"),
        )
    )
    cap1 = schedule_errors(instance(1), overlapping)
    assert "worker: W0 double-booked" in cap1, cap1

    cap2 = schedule_errors(instance(2), overlapping)
    assert "worker: W0 peak 3 > capacity 2" in cap2, cap2

    cap3 = schedule_errors(instance(3), overlapping)
    assert not [e for e in cap3 if e.startswith("worker:")], cap3


# ---------------------------------------------------------------------------
# WIP / 锁定工序
# ---------------------------------------------------------------------------
def locked_instance() -> FJSPInstance:
    """J0-A 已在机上：锁死机器 M1、锁死开工时刻 2。"""
    return FJSPInstance(
        jobs=(Job("J0", ("A", "B"), release_time=0),),
        operations=(
            Operation(
                "A",
                "J0",
                0,
                (("M0", 4), ("M1", 6)),
                locked_machine_id="M1",
                locked_start=2,
            ),
            Operation("B", "J0", 1, (("M0", 3), ("M1", 5))),
        ),
        machines=(Machine("M0", "M0"), Machine("M1", "M1")),
    )


def test_locked_operation_enforcement() -> None:
    # 锁 M1 / 锁 start=2 → 合法排程是 A@M1[2,8)、B@M0[8,11)（B 只能在 A 之后）
    good = Schedule(
        (
            ScheduledOperation("A", "M1", 2, 8),
            ScheduledOperation("B", "M0", 8, 11),
        )
    )
    assert schedule_errors(locked_instance(), good) == []

    # 换机器 → locked 诊断（机器）
    wrong_machine = Schedule(
        (
            ScheduledOperation("A", "M0", 2, 6),
            ScheduledOperation("B", "M0", 6, 9),
        )
    )
    assert "locked: A machine M0 != M1" in schedule_errors(
        locked_instance(), wrong_machine
    )

    # 换开工时刻 → locked 诊断（时刻）
    wrong_start = Schedule(
        (
            ScheduledOperation("A", "M1", 0, 6),
            ScheduledOperation("B", "M0", 6, 9),
        )
    )
    assert "locked: A start 0 != 2" in schedule_errors(locked_instance(), wrong_start)


def test_locked_operation_serialization_round_trip(tmp_path: Path) -> None:
    """``locked_machine_id`` / ``locked_start`` 必须能穿过 JSON。"""
    from fjsp_io.parser import load_json_instance, save_json_instance

    path = tmp_path / "locked.json"
    save_json_instance(locked_instance(), path)
    assert load_json_instance(path) == locked_instance()


# ---------------------------------------------------------------------------
# batching：工序族 → 换型编码
# ---------------------------------------------------------------------------
def family_instance() -> FJSPInstance:
    """同族免换型、异族必须换型。换型矩阵**故意不满足三角不等式**。

    ``setup(F0->F1)=1``、``setup(F1->F0)=1``、``setup(F0->F0)=0``，
    另加一条 ``setup(F2->F0)=9`` 用来暴露「两两析取」写法会切掉可行解的风险。
    """
    return FJSPInstance(
        jobs=(Job("J0", ("A", "B"), release_time=0),),
        operations=(
            Operation("A", "J0", 0, (("M0", 4),), family="F0"),
            Operation("B", "J0", 1, (("M0", 4),), family="F1"),
        ),
        machines=(Machine("M0", "M0"),),
        setups=(
            Setup("F0", "F0", 0),
            Setup("F0", "F1", 1),
            Setup("F1", "F0", 1),
            Setup("F1", "F1", 0),
        ),
    )


def test_setup_gap_is_required_between_families() -> None:
    # 异族：B 必须等 A 结束 + setup(F0->F1)=1 → start >= 5
    tight = Schedule(
        (
            ScheduledOperation("A", "M0", 0, 4),
            ScheduledOperation("B", "M0", 5, 9),
        )
    )
    assert schedule_errors(family_instance(), tight) == []

    no_gap = Schedule(
        (
            ScheduledOperation("A", "M0", 0, 4),
            ScheduledOperation("B", "M0", 4, 8),
        )
    )
    assert "overlap: M0/B" in schedule_errors(family_instance(), no_gap)


def test_same_family_needs_no_setup() -> None:
    """同族紧贴是合法的 —— 这就是 batching 的**全部**建模收益。"""
    instance = FJSPInstance(
        jobs=(Job("J0", ("A", "B"), release_time=0),),
        operations=(
            Operation("A", "J0", 0, (("M0", 4),), family="F0"),
            Operation("B", "J0", 1, (("M0", 4),), family="F0"),
        ),
        machines=(Machine("M0", "M0"),),
        setups=(Setup("F0", "F0", 0),),
    )
    schedule = Schedule(
        (
            ScheduledOperation("A", "M0", 0, 4),
            ScheduledOperation("B", "M0", 4, 8),
        )
    )
    assert schedule_errors(instance, schedule) == []


def test_no_setup_matrix_means_family_is_not_a_setup_constraint() -> None:
    """只给 ``family`` 不给 ``setups`` 时，换型检查必须关闭。

    这条口径和验证器的 ``check_setup = bool(instance.setups)`` 一致。
    求解器端的对应实现在 :func:`fjsp_shop.constraints2.setup_lookup`：矩阵为空时
    它对任意族对都返回 ``(0, True)``，否则会把所有异族相邻判成「换型未定义」。
    """
    instance = FJSPInstance(
        jobs=(Job("J0", ("A", "B"), release_time=0),),
        operations=(
            Operation("A", "J0", 0, (("M0", 4),), family="F0"),
            Operation("B", "J0", 1, (("M0", 4),), family="F1"),
        ),
        machines=(Machine("M0", "M0"),),
    )
    tight = Schedule(
        (
            ScheduledOperation("A", "M0", 0, 4),
            ScheduledOperation("B", "M0", 4, 8),
        )
    )
    assert schedule_errors(instance, tight) == []
    assert constraints2.setup_lookup(instance, "F0", "F1") == (0, True)
    # 有矩阵时，未定义方向必须显式报出来（不能静默当 0）
    assert constraints2.setup_lookup(family_instance(), "F0", "F2") == (0, False)


# ---------------------------------------------------------------------------
# 端到端：两个注册方法在全约束实例上必须给出能过验证器的排程
# ---------------------------------------------------------------------------
def all_constraints_instance() -> FJSPInstance:
    """手工拼一个**每条约束都在起作用**的实例（比生成器的实例更紧凑）。

    * 机器相关工时 + 柔性：A 在 M0=3 / M1=6，C 在 M1=3 / M0=5
    * 释放：J0 release=1
    * 交期：J0 due=10、J1 due=6
    * 换型：F0 / F1 异族要 2 分钟，同族 0
    * 日历：M0 只在 [6,12) 与 [20,40) 可用
    * 维护：M1 在 [4,7) 停
    * 资质：(M0,F0) (M1,F0) (M1,F1) —— 没有 (M0,F1)，所以 F1 只能上 M1
    * 工人：W0 只会 M0（cap 1），W1 两台都会（cap 1）
    * 锁定：B 锁在 M1、锁 start=9
    """
    return FJSPInstance(
        jobs=(
            Job("J0", ("A", "B"), release_time=1, due_date=10, weight=2.0),
            Job("J1", ("C",), release_time=0, due_date=6, weight=1.0),
        ),
        operations=(
            Operation("A", "J0", 0, (("M0", 3), ("M1", 6)), family="F0"),
            Operation(
                "B",
                "J0",
                1,
                (("M0", 4), ("M1", 4)),
                family="F1",
                locked_machine_id="M1",
                locked_start=9,
            ),
            Operation("C", "J1", 0, (("M1", 3), ("M0", 5)), family="F1"),
        ),
        machines=(Machine("M0", "M0", calendar_id="CAL0"), Machine("M1", "M1")),
        calendars=(Calendar("CAL0", ((6, 12), (20, 40))),),
        maintenances=(Maintenance("MT0", "M1", ((4, 7),)),),
        qualifications=(
            Qualification("M0", "F0"),
            Qualification("M1", "F0"),
            Qualification("M1", "F1"),
        ),
        workers=(
            Worker("W0", "小张", ("M0",), 1),
            Worker("W1", "小李", ("M0", "M1"), 1),
        ),
        setups=(
            Setup("F0", "F0", 0),
            Setup("F0", "F1", 2),
            Setup("F1", "F0", 2),
            Setup("F1", "F1", 0),
        ),
    )


def test_all_constraints_instance_has_a_hand_checked_solution() -> None:
    """手算一条可行排程，确认这个实例**不是**无解的。

    没有这条，``full`` 返回 UNKNOWN 时你分不清是「模型不会」还是「实例没解」。

    手算：C(F1) 上 M1[0,3)（避开维护 [4,7)）；A 上 M0 —— 日历窗是 [6,12) 与
    [20,40)，所以最早只能到 6（这就是「日历真的在起作用」：没有窗时 release=1
    就能开工）；B 锁在 M1 start=9，[9,13) 与维护窗不相交。
    Cmax = max(9, 13) = 13，而且 **13 就是最优值**：B 锁死在 [9,13)，下界就是 13。
    """
    schedule = Schedule(
        (
            ScheduledOperation("C", "M1", 0, 3, worker_id="W1"),
            ScheduledOperation("A", "M0", 6, 9, worker_id="W0"),
            ScheduledOperation("B", "M1", 9, 13, worker_id="W1"),
        )
    )
    assert schedule_errors(all_constraints_instance(), schedule) == []


def test_all_constraints_instance_forces_the_calendar_window() -> None:
    """A 只可能上 M0，而 M0 的最早可用窗从 6 开始 —— 所以 A 不可能早于 6。

    M1 走不通：A 在 M1 上要 6 分钟，[1,7) 撞维护 [4,7)，[7,13) 撞锁定的 B[9,13)。
    """
    instance = all_constraints_instance()
    # A 在 M1 上确实「本来就会做」（machine_times 里有），被挡住的只有时间窗
    assert instance.operation("A").time_on("M1") == 6
    assert schedule_errors(
        instance,
        Schedule(
            (
                ScheduledOperation("C", "M1", 0, 3, worker_id="W1"),
                ScheduledOperation("A", "M1", 1, 7, worker_id="W1"),
                ScheduledOperation("B", "M1", 9, 13, worker_id="W1"),
            )
        ),
    ), "A 在 M1 上 [1,7) 必须撞维护窗"


@pytest.mark.parametrize("method", ["fjsp_cpsat_qualified", "fjsp_cpsat_full"])
def test_registered_solvers_return_validator_passing_schedules(method: str) -> None:
    load_week_modules()
    instance = all_constraints_instance()
    spec = {"objective": "makespan", "time_limit": 10.0, "seed": 0}
    result = get(method)(instance, dict(spec))
    assert isinstance(result, ShopResult)
    assert result.schedule is not None, (result.status, result.detail)
    assert validate_result(instance, result) == []
    # 目标值必须能被独立评估器复核（不是求解器自己报的数）
    from fjsp_core.objective import evaluate

    assert result.objective == evaluate(instance, result.schedule, spec["objective"])
    # 每道工序都必须被指派资源（本模型选择「强制占用」语义）
    assert all(item.worker_id is not None for item in result.schedule.operations)
    items = {item.operation_id: item for item in result.schedule.operations}
    # 锁定工序必须落在锁死的机器与时刻上
    assert (items["B"].machine_id, items["B"].start_time) == ("M1", 9)
    # A 必须晚于 release=1、且不能晚于 B 的开工（J0 内 precedence）
    assert items["A"].start_time >= 1
    assert items["A"].end_time <= items["B"].start_time
    # 手算下界 13：B 锁死在 [9,13) ⇒ 任何可行解的目标都不小于 13
    assert result.objective >= 13.0
    # 而 13 是可达的（见手算排程），所以求解器不该给出更差的解
    assert result.objective <= 13.0


def test_full_solver_respects_maintenance_and_calendar() -> None:
    """``full`` 的排程不能碰到 M1 的维护窗、也不能越出 M0 的日历窗。"""
    load_week_modules()
    instance = all_constraints_instance()
    result = get("fjsp_cpsat_full")(
        instance, {"objective": "makespan", "time_limit": 10.0, "seed": 0}
    )
    items = {item.operation_id: item for item in result.schedule.operations}
    # M1 维护 [4,7)：C 在 M1 上时，必须完全不与它相交
    if items["C"].machine_id == "M1":
        assert items["C"].end_time <= 4 or items["C"].start_time >= 7
    # M0 日历窗：A 与 B 落在 M0 上时，必须整体落在某个窗内
    for operation_id in ("A", "B"):
        item = items[operation_id]
        if item.machine_id == "M0":
            assert any(
                lo <= item.start_time and item.end_time <= hi
                for lo, hi in ((6, 12), (20, 40))
            )


def test_setup_time_is_counted_by_the_full_solver_objective() -> None:
    """``total_setup_time`` 目标下，``full`` 报的 breakdown 必须与独立评估一致。"""
    load_week_modules()
    instance = family_instance()
    result = get("fjsp_cpsat_full")(
        instance, {"objective": "total_setup_time", "time_limit": 5.0, "seed": 0}
    )
    assert validate_result(instance, result) == []
    from fjsp_core.objective import total_setup_time

    assert result.breakdown["setup"] == float(total_setup_time(instance, result.schedule))
    # 手算：A(F0) 在 [0,4)、B(F1) 在 [5,9) → 恰好一次 F0->F1 换型 = 1
    assert result.objective == 1.0


def test_urgency_changes_the_objective_but_not_the_feasible_set() -> None:
    """优先级只进目标函数。打开 ``urgency`` 后**可行性诊断不变**，目标值可以变。"""
    load_week_modules()
    instance = FJSPInstance(
        jobs=(
            Job("J0", ("A",), release_time=0, due_date=2, weight=1.0, priority=0),
            Job("J1", ("B",), release_time=0, due_date=2, weight=1.0, priority=5),
        ),
        operations=(
            Operation("A", "J0", 0, (("M0", 3),)),
            Operation("B", "J1", 0, (("M0", 3),)),
        ),
        machines=(Machine("M0", "M0"),),
    )
    spec = {"objective": "weighted_tardiness", "time_limit": 5.0, "seed": 0}
    plain = get("fjsp_cpsat_full")(instance, dict(spec))
    urgent = get("fjsp_cpsat_full")(instance, {**spec, "urgency": True})

    assert validate_result(instance, plain) == []
    assert validate_result(instance, urgent) == []

    # 手算：只有一台机器、两道 3 分钟的工序、交期都是 2，所以 Cmax 恒为 6，
    # 先做的那道迟 1、后做的那道迟 4。两个顺序在**不带权**的 Σw_jT_j 下同分：
    #   A 先：T_A=1(w=1), T_B=4(w=1)  →  1 + 4 = 5
    # 所以 plain 的目标值一定是 5.0，与顺序无关。
    assert plain.objective == 5.0
    # 打开 urgency 后 J1(priority=5) 的有效权重变成 1·(1+5)=6：
    #   A 先：1·1 + 6·4 = 25      B 先：6·1 + 1·4 = 10
    # 于是最优顺序翻转为「B 先上机」。这就是「优先级进目标函数」的全部含义。
    assert urgent.objective == 10.0
    first = min(urgent.schedule.operations, key=lambda item: item.start_time)
    assert first.operation_id == "B", "紧急订单应该先上机"
    # 而 plain 的目标值在这个新顺序下不变 —— 反过来也说明 urgency 没有动可行域
    assert urgent.detail["urgency_applied"] is True


# ---------------------------------------------------------------------------
# KPI
# ---------------------------------------------------------------------------
def test_kpi_hand_checked_values() -> None:
    """手算：Cmax=9、J0 迟 1 天、J1 迟 -1（提前）→ ΣT=1、准时率 1/2。"""
    instance = qualified_instance()
    schedule = qualified_schedule()
    report = kpi_report(instance, schedule)

    assert report.cmax == 9
    # J0 完成 9 > due 8 → 迟 1；J1 完成 3 <= due 4 → 不迟
    assert report.total_tardiness == 1
    assert report.weighted_tardiness == 1.0  # J0 权重 1.0
    assert (report.jobs_on_time, report.jobs_with_due_date) == (1, 2)
    assert report.on_time_rate == 0.5
    assert report.setup_time == 0  # 没给 setups 矩阵
    # 工人负载：W0 做 A 5 分钟，W1 做 C 3 + B 4 = 7 分钟
    assert report.worker_load == {"W0": 5, "W1": 7, "W2": 0}
    # W2 完全没被用到 → utilization 记 0.0，不能是 NaN（JSON 不允许）
    assert report.worker_kpi[2].utilization == 0.0
    assert report.worker_kpi[0].span == 5
    assert report.worker_kpi[1].span == 9  # [0,3) 与 [5,9) → 可见窗口 0..9


def test_kpi_normalize_and_zero_denominator() -> None:
    instance = qualified_instance()
    report = kpi_report(instance, qualified_schedule())
    assert normalize(report, report) == {
        "cmax": 1.0,
        "total_tardiness": 1.0,
        "setup": 1.0,
    }
    # 参考排程 setup=0 → 分母为 0，返回 1.0（约定），不是 inf/nan
    assert normalize(report, report)["setup"] == 1.0


@pytest.mark.parametrize("method", ["fjsp_cpsat_qualified", "fjsp_cpsat_full"])
def test_json_bundle_round_trip_equality(method: str, tmp_path: Path) -> None:
    """instance + result + KPI 写进一个文件，读回来**逐字段相等**。"""
    load_week_modules()
    instance = all_constraints_instance()
    result = get(method)(instance, {"objective": "makespan", "time_limit": 10.0, "seed": 0})

    path = tmp_path / f"{method}.bundle.json"
    written = save_bundle(path, instance, result)
    loaded = load_bundle(path)

    assert bundles_equal(loaded, written) == []
    assert loaded.instance == instance
    assert loaded.kpi == written.kpi
    assert loaded.schema == BUNDLE_SCHEMA
    assert loaded.result.schedule == result.schedule
    # 再写一次字节完全相同 —— round-trip 不含任何「重新计算」
    again = tmp_path / "again.json"
    save_bundle(again, loaded.instance, loaded.result)
    assert again.read_text(encoding="utf-8") == path.read_text(encoding="utf-8")


def test_bundle_refuses_invalid_schedule(tmp_path: Path) -> None:
    """装进归档前先验证。求解器说可行不算数。"""
    instance = qualified_instance()
    bad = ShopResult(
        method="hand",
        status="FEASIBLE",
        # A 是 F0，放到 M1 上违反资质
        schedule=Schedule(
            (
                ScheduledOperation("A", "M1", 0, 5, worker_id="W2"),
                ScheduledOperation("C", "M1", 5, 8, worker_id="W1"),
                ScheduledOperation("B", "M1", 8, 12, worker_id="W1"),
            )
        ),
        objective=12.0,
    )
    with pytest.raises(ValueError, match="invalid schedule"):
        save_bundle(tmp_path / "bad.json", instance, bad)


def test_bundle_rejects_unknown_schema(tmp_path: Path) -> None:
    instance = qualified_instance()
    payload = make_bundle(instance, _hand_result(), verify=False).to_dict()
    payload["bundle_schema"] = 999
    path = tmp_path / "future.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported bundle_schema"):
        load_bundle(path)


def _hand_result() -> ShopResult:
    return ShopResult(
        method="hand",
        status="FEASIBLE",
        schedule=qualified_schedule(),
        objective=9.0,
    )


# ---------------------------------------------------------------------------
# 模型覆盖表：机械核对「表里说的代码里真有」
# ---------------------------------------------------------------------------
def test_model_coverage_table_shape() -> None:
    assert len(MODEL_COVERAGE) >= 5, "至少要有 5 条真实约束"
    fields = {(row.owner.__name__, row.field) for row in MODEL_COVERAGE}
    assert len(fields) == len(MODEL_COVERAGE), "同一字段不该重复登记"
    # 每条约束都要能指名验证器里的诊断标签（或显式声明「不进验证器」）
    for row in MODEL_COVERAGE:
        assert row.validator_check, row.constraint
        assert row.solver_use, row.constraint
        assert row.evidence, row.constraint


def test_model_coverage_fields_exist_on_the_model() -> None:
    """每一行的 ``field`` 必须在对应的 dataclass 上真的存在（含继承来的）。"""
    for row in MODEL_COVERAGE:
        assert hasattr(row.owner, "__dataclass_fields__"), row.owner
        assert row.field in row.owner.__dataclass_fields__, (
            f"{row.owner.__name__}.{row.field} 不在模型里"
        )


def test_model_coverage_evidence_appears_in_code() -> None:
    """每一行声明的 ``evidence`` 标识符必须真的出现在验证器或求解器源码里。

    这是防「文档漂移」的核心检查：表里写「已覆盖」而代码里 grep 不到，
    这条约束就只是文档里的一句好话。
    """
    from fjsp_core import schedule_validation

    haystack = inspect.getsource(schedule_validation) + inspect.getsource(constraints2)
    for row in MODEL_COVERAGE:
        for token in row.evidence:
            assert token in haystack, (
                f"约束「{row.constraint}」声明了证据 {token!r}，"
                "但验证器与求解器的源码里都找不到它"
            )


def test_model_coverage_field_is_read_at_runtime() -> None:
    """更强的核对：把字段真的改一下，验证器或求解器的行为必须跟着变。

    只查源码会漏掉「字符串恰好同名但没被读」的情况。这里用四个可观察的字段
    （``release_time`` / ``family`` / ``locked_machine_id`` / ``capacity``）
    各做一次「改字段 → 诊断变化」的实验。
    """
    from dataclasses import replace

    base = qualified_instance()
    clean = qualified_schedule()
    assert schedule_errors(base, clean) == []

    # 1) release_time：把 J0 的释放时间推到 3 → A 在 [0,5) 违反 release
    delayed = replace(base, jobs=tuple(
        replace(job, release_time=3) if job.id == "J0" else job for job in base.jobs
    ))
    assert "release: A" in schedule_errors(delayed, clean)

    # 2) family + qualifications：把 A 的族改成没发过资质的 F2 → qualification
    refamilied = replace(base, operations=tuple(
        replace(op, family="F2") if op.id == "A" else op for op in base.operations
    ))
    assert "qualification: A on M0" in schedule_errors(refamilied, clean)

    # 3) locked_machine_id：把 A 锁到 M1 → 机器不符
    locked = replace(base, operations=tuple(
        replace(op, locked_machine_id="M1") if op.id == "A" else op
        for op in base.operations
    ))
    assert "locked: A machine M0 != M1" in schedule_errors(locked, clean)

    # 4) Worker.capacity：把 W1 的容量改成 2 → 原诊断换口径（double-booked 消失）
    loosened = replace(base, workers=tuple(
        replace(worker, capacity=2) if worker.id == "W1" else worker
        for worker in base.workers
    ))
    overlapping = Schedule(
        (
            ScheduledOperation("A", "M0", 0, 5, worker_id="W0"),
            ScheduledOperation("C", "M1", 2, 5, worker_id="W1"),
            ScheduledOperation("B", "M1", 0, 4, worker_id="W1"),
        )
    )
    assert "worker: W1 double-booked" in schedule_errors(base, overlapping)
    assert "worker: W1 double-booked" not in schedule_errors(loosened, overlapping)


# ---------------------------------------------------------------------------
# 求解器辅助函数（不经过 CP-SAT 也能核对的那部分）
# ---------------------------------------------------------------------------
def test_qualified_machine_ids_matches_the_validator() -> None:
    """``qualified_machine_ids`` 与验证器的资质口径必须逐字一致。

    两处实现如果分叉，会出现「求解器认为可以、验证器认为不行」的排程 ——
    而本模块的契约是「返回的排程永远过验证器」。
    """
    instance = qualified_instance()
    for op in instance.operations:
        allowed = set(qualified_machine_ids(instance, op))
        hand = {
            q.machine_id for q in instance.qualifications if q.family == op.family
        }
        assert allowed == hand, op.id

    # 没有资质表时不做限制（与验证器的 ``if instance.qualifications`` 一致）
    base = qualified_instance()
    no_quals = FJSPInstance(
        jobs=base.jobs, operations=base.operations, machines=base.machines
    )
    # 没有资质表时不收窄 —— 与验证器的 ``if instance.qualifications`` 完全一致。
    # A 的 machine_times 里本来就有 M0 与 M1，所以这里应当两台的都在。
    assert set(qualified_machine_ids(no_quals, no_quals.operations[0])) == {"M0", "M1"}


def test_time_horizon_covers_release_and_calendar() -> None:
    instance = all_constraints_instance()
    horizon = constraints2.time_horizon(instance)
    # 日历最晚窗到 40、维护到 7、锁定 start=12 → 地平线必须不小于 40
    assert horizon >= 40


def test_registry_exposes_both_week4_methods() -> None:
    load_week_modules()
    from fjsp_shop.registry import available

    names = available()
    assert "fjsp_cpsat_qualified" in names
    assert "fjsp_cpsat_full" in names


# ---------------------------------------------------------------------------
# 生成器上的集成：``configs/month3.json`` 的两个工业实例
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "generator_kwargs",
    [
        dict(
            seed=202, jobs=6, machines=4, operations_per_job=3,
            flexibility=2, worker_count=2, setup_families=2,
        ),
        dict(
            seed=203, jobs=8, machines=5, operations_per_job=3, flexibility=3,
            setup_families=3, calendar_windows=1, maintenance_count=2,
            worker_count=3, locked_count=1, release_max=6,
        ),
    ],
)
def test_generated_industrial_instances_are_solvable(generator_kwargs: dict) -> None:
    """两个批次实例都能被 ``fjsp_cpsat_full`` 解出**过验证器**的排程。

    预算取 **15 秒** —— 就是 ``configs/month3.json`` 的批次预算，这样测试口径
    与实际跑批次的口径一致。**不要往下调**：``ind_qualified`` 的精确换型模型
    在 5 秒内连一个可行解都找不到（``UNKNOWN``），把预算调小只会让这条测试
    变成一条与批次无关的假失败。
    """
    load_week_modules()
    instance = generate_instance(**generator_kwargs)
    # 这两个实例在 configs/month3.json 里就是这两个目标。
    objective = "weighted_sum" if generator_kwargs["seed"] == 203 else "makespan"
    result = get("fjsp_cpsat_full")(
        instance, {"objective": objective, "time_limit": 15.0, "seed": 0}
    )
    assert result.schedule is not None, (result.status, result.detail)
    assert validate_result(instance, result) == []
    assert result.objective is not None and result.objective > 0
    from fjsp_core.objective import evaluate

    assert result.objective == evaluate(instance, result.schedule, objective)


def test_solvers_are_deterministic_under_a_fixed_seed() -> None:
    """同输入 + 同种子 + 单线程 → 同输出。这是 Week 1 定下的可复现契约。"""
    load_week_modules()
    instance = all_constraints_instance()
    spec = {"objective": "makespan", "time_limit": 3.0, "seed": 7}
    first = get("fjsp_cpsat_full")(instance, dict(spec))
    second = get("fjsp_cpsat_full")(instance, dict(spec))
    assert first.objective == second.objective
    assert first.detail["num_search_workers"] == 1
    assert [
        (item.operation_id, item.machine_id, item.start_time)
        for item in first.schedule.operations
    ] == [
        (item.operation_id, item.machine_id, item.start_time)
        for item in second.schedule.operations
    ]
