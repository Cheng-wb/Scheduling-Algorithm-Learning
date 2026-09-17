"""Week 3 CP-SAT 区间模型的验收测试。

三条原则贯穿全文件：

1. **手算优先**。所有小实例的期望值都来自显式时间线推导（写在注释里），
   不是由被测代码生成的。
2. **独立交叉验证**。能落到单工序的实例一律与 M1 的 ``oracle.exhaustive_optimum``
   （独立穷举）对拍；``Cmax`` 下界用 M1 的 ``parallel_makespan_lower_bound``。
3. **不信任求解器**。每个返回的排程都过 M1 的独立验证器 ``validate_schedule``；
   ``best_bound`` 只认求解器自己给的值，取不到必须是 ``None``。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from opt_common.bridge import (  # noqa: E402
    M2_OBJECTIVES,
    Instance,
    Job,
    Machine,
    Operation,
    Schedule,
    generate_instance,
    makespan,
    parallel_lpt,
    validate_schedule,
)
from opt_models.cpsat_models import (  # noqa: E402
    WEIGHT_SCALE,
    build_cpsat_model,
    cpsat_cumulative,
    cpsat_jsp,
    cpsat_parallel,
    cumulative_profile,
    solve_model_invalid_demo,
)
from opt_solvers.registry import available, get  # noqa: E402
from opt_solvers.result import validate_result  # noqa: E402

GENEROUS = 10.0  # 手算实例都很小，10 秒足够跑出 OPTIMAL
REGISTERED = ("cpsat_parallel", "cpsat_jsp", "cpsat_cumulative")


# --- 手工构造实例的辅助函数 ------------------------------------------------


def make_instance(
    machines: int,
    job_routes: list[tuple[list[int], tuple[tuple[str, ...], ...]]],
    *,
    release_times: list[int] | None = None,
    due_dates: list[int | None] | None = None,
    weights: list[float] | None = None,
) -> Instance:
    """手工搭实例：``job_routes[j] = ([p0, p1, ...], (machines_of_op0, ...))``。"""
    resource = tuple(Machine(f"M{i}", f"Machine {i}") for i in range(machines))
    jobs: list[Job] = []
    operations: list[Operation] = []
    for index, (times, eligibility) in enumerate(job_routes):
        job_id = f"J{index}"
        route = tuple(f"{job_id}_O{k}" for k in range(len(times)))
        jobs.append(
            Job(
                job_id,
                route,
                release_time=(release_times or [0] * len(job_routes))[index],
                due_date=(due_dates or [None] * len(job_routes))[index],
                weight=(weights or [1.0] * len(job_routes))[index],
            )
        )
        for operation_id, duration, machines_of_op in zip(route, times, eligibility):
            operations.append(
                Operation(operation_id, job_id, duration, tuple(machines_of_op))
            )
    return Instance(tuple(jobs), tuple(operations), resource)


def parallel_instance(times: list[int], machines: int, **kwargs) -> Instance:
    """`P||Cmax` 形式：每个 job 恰好一道工序，全机器合格。"""
    eligible = tuple(f"M{i}" for i in range(machines))
    return make_instance(
        machines,
        [(times, (eligible,) * len(times)) for times in [[p] for p in times]],
        **kwargs,
    )


# --- 1. 小型 JSP：手算 Cmax -------------------------------------------------


def test_two_job_jsp_hand_computed_cmax() -> None:
    """2 job × 2 工序的固定路由 JSP，手算最优 Cmax = 7。

    J0：O0 在 M0（p=3）→ O1 在 M1（p=2），job 总工时 5
    J1：O0 在 M1（p=2）→ O1 在 M0（p=4），job 总工时 6

    下界：M0 必须加工 3 + 4 = 7 个时间单位，所以 Cmax >= 7。
    达到 7 的时间线（手算）：
        M0: J0_O0 0-3, J1_O1 3-7
        M1: J1_O0 0-2, J0_O1 3-5
    逐条核对：J0 有 0-3 在 3-5 之前；J1 有 0-2 在 3-7 之前；
    两台机器各自无重叠。所以最优值恰为 7。
    """
    instance = make_instance(
        2,
        [
            ([3, 2], (("M0",), ("M1",))),
            ([2, 4], (("M1",), ("M0",))),
        ],
    )
    result = cpsat_jsp(instance, {"objective": "makespan", "time_limit": GENEROUS})

    assert result.status == "OPTIMAL"
    assert result.objective == 7.0
    validate_schedule(instance, result.schedule)
    assert makespan(instance, result.schedule) == 7

    by_id = {item.operation_id: item for item in result.schedule.operations}
    # 机器分配必须落在路由上（每个工序只有一个合格机器）
    assert by_id["J0_O0"].machine_id == "M0"
    assert by_id["J0_O1"].machine_id == "M1"
    assert by_id["J1_O0"].machine_id == "M1"
    assert by_id["J1_O1"].machine_id == "M0"
    # precedence
    assert by_id["J0_O0"].end_time <= by_id["J0_O1"].start_time
    assert by_id["J1_O0"].end_time <= by_id["J1_O1"].start_time
    # M1 上的两道工序不能重叠
    m1 = sorted(
        (item for item in result.schedule.operations if item.machine_id == "M1"),
        key=lambda item: item.start_time,
    )
    assert m1[0].end_time <= m1[1].start_time


def test_jsp_fixed_route_uses_one_interval_per_operation() -> None:
    """经典 JSP 路由（每工序单合格机器）下没有 presence 变量：一工序一区间。"""
    fixed = make_instance(
        2,
        [
            ([3, 2], (("M0",), ("M1",))),
            ([2, 4], (("M1",), ("M0",))),
        ],
    )
    built = build_cpsat_model(fixed, "makespan", prefer_fixed_route=True)
    assert built.presence == {}, "单合格机器时不应产生可选区间"
    assert set(built.chosen_machine) == {"J0_O0", "J0_O1", "J1_O0", "J1_O1"}

    # 柔性路由（两个工序都有两个合格机器）时才需要 presence
    flexible = make_instance(
        2,
        [([3, 2], (("M0", "M1"), ("M0", "M1")))],
    )
    built_flexible = build_cpsat_model(flexible, "makespan", prefer_fixed_route=True)
    assert len(built_flexible.presence) == 4


def test_jsp_respects_release_times_in_operation_chain() -> None:
    """释放时间落在 job 上：整条工序链都不得早于 rj 开工。"""
    instance = make_instance(
        2,
        [
            ([3, 2], (("M0",), ("M1",))),
            ([2, 4], (("M1",), ("M0",))),
        ],
        release_times=[0, 5],
    )
    result = cpsat_jsp(instance, {"objective": "makespan", "time_limit": GENEROUS})
    assert result.status == "OPTIMAL"
    validate_schedule(instance, result.schedule)
    for item in result.schedule.operations:
        if item.operation_id.startswith("J1"):
            assert item.start_time >= 5
    # J1 的最短流程是 2 + 4 = 6，从 5 起最早 11 完工
    assert makespan(instance, result.schedule) == 11


# --- 2. 并行机：下界与独立穷举 ----------------------------------------------


@pytest.mark.parametrize(
    ("times", "machines", "expected"),
    [
        ([8, 7, 6, 5], 2, 13),  # 手算：LB = max(8, ceil(26/2)) = 13，可达
        ([9, 8, 7, 6, 5, 4], 3, 13),  # 手算：LB = max(9, ceil(39/3)) = 13，可达
        ([5, 5, 4, 4, 3, 3, 3], 3, 9),  # 手算：LB = max(5, ceil(27/3)) = 9，可达
    ],
)
def test_parallel_matches_lower_bound_when_tight(
    times: list[int], machines: int, expected: int
) -> None:
    """下界紧的实例上，CP-SAT 的 Cmax 必须等于 M1 的下界公式。"""
    instance = parallel_instance(times, machines)
    from scheduling_algorithms.rules import parallel_makespan_lower_bound

    lower = parallel_makespan_lower_bound(instance)
    assert lower == expected

    result = cpsat_parallel(instance, {"objective": "makespan", "time_limit": GENEROUS})
    assert result.status == "OPTIMAL"
    assert result.objective == float(lower), "LB <= OPT <= Cmax，两端相等即证明最优"
    assert result.best_bound == float(lower)
    validate_schedule(instance, result.schedule)


def test_parallel_beats_lpt_where_lpt_is_suboptimal() -> None:
    """M1 的反例：p=[3,3,2,2,2] 2 台机器，LPT 得 7，最优是 6。"""
    instance = parallel_instance([3, 3, 2, 2, 2], 2)
    lpt_schedule = parallel_lpt(instance)
    assert makespan(instance, lpt_schedule) == 7

    result = cpsat_parallel(instance, {"objective": "makespan", "time_limit": GENEROUS})
    assert result.objective == 6.0
    validate_schedule(instance, result.schedule)


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 4, 5, 6, 7])
@pytest.mark.parametrize(
    "objective", ["makespan", "total_tardiness", "weighted_completion_time"]
)
def test_parallel_matches_exhaustive_optimum(seed: int, objective: str) -> None:
    """与 M1 的独立穷举对拍：目标值必须逐位相等。"""
    from scheduling_algorithms.oracle import exhaustive_optimum

    instance = generate_instance(seed, jobs=4, machines=2, release_max=3)
    reference, _, _ = exhaustive_optimum(instance, objective, limit=200_000)

    result = cpsat_parallel(
        instance, {"objective": objective, "time_limit": GENEROUS, "seed": 0}
    )
    assert result.status == "OPTIMAL"
    assert result.objective == float(reference)
    validate_schedule(instance, result.schedule)


# --- 3. Cumulative：容量约束真的收紧了吗 ------------------------------------


def test_cumulative_capacity_tightens_the_optimum() -> None:
    """手算：2 台机器、3 个 job、每个 p=5，容量 1 时只能串行。

    - 只有 NoOverlap（= cpsat_parallel）：两台机器并行 → Cmax = 10。
    - 再加一条 Cumulative（capacity=1，每个工序占 1 单位）：
      任意时刻至多一个工序在跑 → 三道工序必须串行 → Cmax = 15。
    """
    instance = parallel_instance([5, 5, 5], 2)

    parallel_result = cpsat_parallel(
        instance, {"objective": "makespan", "time_limit": GENEROUS}
    )
    assert parallel_result.objective == 10.0
    # 没有容量约束时，峰值并发就是机器数
    assert cumulative_profile(instance, parallel_result.schedule, 1)[0] == 2

    tight = cpsat_cumulative(
        instance,
        {
            "objective": "makespan",
            "time_limit": GENEROUS,
            "resource_capacity": 1,
            "resource_demand": 1,
        },
    )
    assert tight.status == "OPTIMAL"
    assert tight.objective == 15.0, "容量 1 把三道工序压成串行"
    # 独立复核容量约束：M1 的验证器不覆盖 Cumulative 语义
    assert cumulative_profile(instance, tight.schedule, 1)[0] == 1
    validate_schedule(instance, tight.schedule)

    # 容量放宽到 2 时约束变冗余，回到 10
    loose = cpsat_cumulative(
        instance,
        {
            "objective": "makespan",
            "time_limit": GENEROUS,
            "resource_capacity": 2,
            "resource_demand": 1,
        },
    )
    assert loose.objective == 10.0
    assert cumulative_profile(instance, loose.schedule, 1)[0] == 2


def test_cumulative_default_capacity_is_redundant() -> None:
    """默认 ``resource_capacity`` 取机器数：容量约束不改变最优值。"""
    instance = parallel_instance([3, 3, 2, 2, 2], 2)
    default = cpsat_cumulative(instance, {"objective": "makespan", "time_limit": GENEROUS})
    plain = cpsat_parallel(instance, {"objective": "makespan", "time_limit": GENEROUS})
    assert default.objective == plain.objective == 6.0


def test_cumulative_demand_two_on_three_machines() -> None:
    """手算：3 台机器、4 个 job p=4，每工序占 2 单位、容量 3。

    容量 3 / 每工序 2 单位 ⇒ 任意时刻至多 1 个工序在跑（2 + 2 = 4 > 3）
    ⇒ 4 道工序全部串行 ⇒ Cmax = 16（只用 NoOverlap 时是 8）。
    """
    instance = parallel_instance([4, 4, 4, 4], 3)
    plain = cpsat_parallel(instance, {"objective": "makespan", "time_limit": GENEROUS})
    assert plain.objective == 8.0

    result = cpsat_cumulative(
        instance,
        {
            "objective": "makespan",
            "time_limit": GENEROUS,
            "resource_capacity": 3,
            "resource_demand": 2,
        },
    )
    assert result.objective == 16.0
    assert cumulative_profile(instance, result.schedule, 2)[0] == 2
    validate_schedule(instance, result.schedule)


# --- 4. 状态词表 ------------------------------------------------------------


def test_infeasible_instance_returns_infeasible() -> None:
    """需求 2 单位 > 容量 1 单位：单个工序自己就违反容量，无解。"""
    instance = parallel_instance([5, 5, 5], 2)
    result = cpsat_cumulative(
        instance,
        {
            "objective": "makespan",
            "time_limit": GENEROUS,
            "resource_capacity": 1,
            "resource_demand": 2,
        },
    )
    assert result.status == "INFEASIBLE"
    assert result.objective is None
    assert result.schedule is None
    # INFEASIBLE 时 BestObjectiveBound() 会返回 0，绝不能当成界写进结果
    assert result.best_bound is None
    assert result.gap is None


def test_model_invalid_is_reported_separately_from_infeasible() -> None:
    """变量域为空 ⇒ ``MODEL_INVALID``，而不是 ``INFEASIBLE``。

    非法模型根本没进入搜索，求解器直接拒绝它——两者在状态词表上必须分开。
    """
    instance = parallel_instance([5, 5, 5], 2)
    result = solve_model_invalid_demo(instance, {"objective": "makespan", "time_limit": 1.0})
    assert result.status == "MODEL_INVALID"
    assert result.objective is None
    assert result.best_bound is None
    assert result.detail["cp_status"] == "MODEL_INVALID"


def test_unknown_status_returns_no_solution() -> None:
    """预算太小时 CP-SAT 给 UNKNOWN；此时 ``Value()`` 是未初始化内存，不能读。"""
    instance = generate_instance(50, jobs=25, machines=3)
    result = cpsat_parallel(
        instance, {"objective": "makespan", "time_limit": 0.01, "seed": 0}
    )
    assert result.status == "UNKNOWN"
    assert result.schedule is None
    assert result.objective is None
    assert result.best_bound is None


def test_feasible_status_has_bound_below_objective() -> None:
    """时间限制内的可行解：bound 来自求解器，且严格低于已找到的目标值。"""
    instance = generate_instance(51, jobs=25, machines=3)
    result = cpsat_parallel(
        instance, {"objective": "makespan", "time_limit": 0.05, "seed": 0}
    )
    assert result.status == "FEASIBLE"
    assert result.objective is not None
    assert result.best_bound is not None
    assert result.best_bound < result.objective
    assert result.gap is not None and result.gap > 0.0
    validate_schedule(instance, result.schedule)


def test_unknown_objective_is_failed_not_model_invalid() -> None:
    """spec 写错是调用方的问题，记 FAILED；MODEL_INVALID 只留给求解器的判断。"""
    instance = parallel_instance([1, 1], 1)
    result = cpsat_parallel(instance, {"objective": "no_such_objective"})
    assert result.status == "FAILED"
    assert "unknown objective" in result.detail["failure_reason"]


def test_bad_time_scale_is_rejected() -> None:
    instance = parallel_instance([1, 1], 1)
    for bad in (0, -3, 2.5):
        result = cpsat_parallel(
            instance, {"objective": "makespan", "time_scale": bad, "time_limit": 1.0}
        )
        assert result.status == "FAILED", f"time_scale={bad} 应被拒绝"


# --- 5. 整数时间缩放 --------------------------------------------------------


def test_integer_time_scaling_keeps_the_optimum_and_unscaled_times() -> None:
    """把时间放大 3 倍建模，最优值不变，返回的排程仍是真实时间单位。

    先决条件：M1 的 ``processing_time`` 是 int，所以 ``end = start + p * scale``
    整除回 ``start // scale`` 与 ``end // scale`` 时差恰好是 ``p``。
    """
    instance = parallel_instance([3, 3, 2, 2, 2], 2)
    plain = cpsat_parallel(instance, {"objective": "makespan", "time_limit": GENEROUS})
    scaled = cpsat_parallel(
        instance, {"objective": "makespan", "time_scale": 3, "time_limit": GENEROUS}
    )

    assert plain.objective == scaled.objective == 6.0
    assert scaled.detail["time_scale"] == 3
    # 返回的排程必须是真实时间单位，且通过独立验证（validator 会查 duration）
    validate_schedule(instance, scaled.schedule)
    for item in scaled.schedule.operations:
        operation = next(op for op in instance.operations if op.id == item.operation_id)
        assert item.end_time - item.start_time == operation.processing_time


def test_scaling_rescales_objective_units_for_completion_time() -> None:
    """放大后的 CP-SAT 目标要除回时间单位，才与 M1 的口径一致。"""
    instance = parallel_instance([4, 4, 4], 2)
    result = cpsat_parallel(
        instance,
        {"objective": "total_completion_time", "time_scale": 5, "time_limit": GENEROUS},
    )
    assert result.detail["objective_divisor"] == 5.0
    assert result.detail["cp_objective_matches_m1"] is True
    assert result.objective == float(M2_OBJECTIVES["total_completion_time"](instance, result.schedule))


# --- 6. 目标口径与权重缩放 --------------------------------------------------


@pytest.mark.parametrize("objective", sorted(M2_OBJECTIVES))
def test_objective_equals_m1_evaluator(objective: str) -> None:
    """每个目标都由 M1 的 ``objective.py`` 在返回排程上复核一遍。"""
    instance = parallel_instance([3, 3, 2, 2, 2], 2, due_dates=[4] * 5, weights=[1, 2, 3, 1, 1])
    result = cpsat_parallel(
        instance, {"objective": objective, "time_limit": GENEROUS, "seed": 0}
    )
    assert result.status == "OPTIMAL"
    expected = float(M2_OBJECTIVES[objective](instance, result.schedule))
    assert result.objective == expected
    assert result.detail["cp_objective_matches_m1"] is True


def test_weight_scaling_uses_integer_coefficients() -> None:
    """float 权重必须先变成整数系数；本例手算 WSPT 顺序 = 17.5。"""
    instance = make_instance(
        1,
        [
            ([5], (("M0",),)),
            ([5], (("M0",),)),
        ],
        weights=[0.5, 2.5],
    )
    result = cpsat_parallel(
        instance, {"objective": "weighted_completion_time", "time_limit": GENEROUS}
    )
    # 手算：J1 的 p/w = 2 远小于 J0 的 10，所以 J1 先 → 2.5*5 + 0.5*10 = 17.5
    assert result.objective == 17.5
    assert result.detail["objective_divisor"] == float(WEIGHT_SCALE)


def test_too_small_weight_is_reported_not_silently_truncated() -> None:
    """权重小到取整为 0 时必须报错，而不是悄悄改变目标函数。"""
    instance = make_instance(
        1,
        [
            ([5], (("M0",),)),
            ([5], (("M0",),)),
        ],
        weights=[1e-9, 1.0],
    )
    result = cpsat_parallel(
        instance, {"objective": "weighted_completion_time", "time_limit": GENEROUS}
    )
    assert result.status == "FAILED"
    assert "weight too small" in result.detail["failure_reason"]


def test_empty_instance_is_trivially_optimal() -> None:
    instance = Instance((), (), (Machine("M0", "M0"),))
    result = cpsat_parallel(instance, {"objective": "makespan", "time_limit": GENEROUS})
    assert result.status == "OPTIMAL"
    assert result.objective == 0.0
    validate_schedule(instance, result.schedule)


# --- 7. 资格限制与释放时间 --------------------------------------------------


def test_machine_eligibility_is_honoured() -> None:
    """只有一个合格机器的工序必须落在那一台上。"""
    instance = make_instance(
        2,
        [
            ([4], (("M0",),)),
            ([4], (("M0", "M1"),)),
            ([4], (("M1",),)),
        ],
    )
    result = cpsat_parallel(instance, {"objective": "makespan", "time_limit": GENEROUS})
    assert result.objective == 8.0, "J0 只能上 M0、J2 只能上 M1，必然有一个机器上两道工序"
    validate_schedule(instance, result.schedule)
    by_id = {item.operation_id: item for item in result.schedule.operations}
    assert by_id["J0_O0"].machine_id == "M0"
    assert by_id["J2_O0"].machine_id == "M1"
    assert result.detail["cp_objective_matches_m1"] is True


def test_release_time_shifts_start_but_does_not_change_machine_choice() -> None:
    instance = parallel_instance([5, 5, 5], 2, release_times=[0, 3, 9])
    result = cpsat_parallel(instance, {"objective": "makespan", "time_limit": GENEROUS})
    assert result.status == "OPTIMAL"
    # 手算下界：r=9 且 p=5 ⇒ 最早 14 完工，所以 Cmax >= 14；两台机器可达
    assert result.objective == 14.0
    validate_schedule(instance, result.schedule)


# --- 8. 统一接口纪律 --------------------------------------------------------


def test_three_method_names_are_registered() -> None:
    for name in REGISTERED:
        assert name in available(), f"{name} 必须在注册表里，否则月末批次会记 FAILED"


@pytest.mark.parametrize("method", REGISTERED)
def test_every_returned_schedule_passes_independent_validator(method: str) -> None:
    """统一纪律：求解器说 OPTIMAL 不等于解可行。"""
    instance = generate_instance(60, jobs=5, machines=2, operations_per_job=2)
    result = get(method)(instance, {"objective": "makespan", "time_limit": GENEROUS, "seed": 0})
    assert result.status in ("OPTIMAL", "FEASIBLE")
    validate_schedule(instance, result.schedule)
    assert validate_result(instance, result) == []
    assert isinstance(result.schedule, Schedule)


@pytest.mark.parametrize("method", REGISTERED)
def test_build_and_solve_time_are_separate(method: str) -> None:
    instance = generate_instance(61, jobs=8, machines=3)
    result = get(method)(instance, {"objective": "makespan", "time_limit": GENEROUS})
    assert result.build_time >= 0.0
    assert result.solve_time > 0.0
    assert result.wall_time == pytest.approx(result.build_time + result.solve_time)
    assert "cp_status" in result.detail


def test_iterations_count_branches_and_conflicts_are_recorded() -> None:
    instance = parallel_instance([3, 3, 2, 2, 2], 2)
    result = cpsat_parallel(instance, {"objective": "makespan", "time_limit": GENEROUS})
    assert result.iterations == result.detail["branches"]
    assert isinstance(result.detail["conflicts"], int)


def test_solver_is_deterministic_under_fixed_seed() -> None:
    """同一实例 + 同一 spec ⇒ 同一目标值（单 worker + 固定种子）。"""
    instance = generate_instance(62, jobs=8, machines=3)
    spec = {"objective": "makespan", "time_limit": GENEROUS, "seed": 7}
    first = cpsat_parallel(instance, spec)
    second = cpsat_parallel(instance, spec)
    assert first.objective == second.objective


# --- 9. 独立复核 Cumulative -------------------------------------------------


def test_cumulative_profile_detects_a_violation_independently() -> None:
    """M1 验证器不覆盖 Cumulative，所以容量必须能被独立重算出来。"""
    instance = parallel_instance([5, 5, 5], 2)
    parallel_result = cpsat_parallel(
        instance, {"objective": "makespan", "time_limit": GENEROUS}
    )
    peak, moment = cumulative_profile(instance, parallel_result.schedule, 1)
    assert peak == 2
    assert moment == 0, "两个工序都在 0 时刻开工"
    # M1 的验证器对这份排程毫无异议：容量语义完全在它视野之外
    validate_schedule(instance, parallel_result.schedule)
