"""Week 3：CP-SAT 区间模型（并行机选择 / 小型 JSP / 有限容量资源）。

三个注册方法（``configs/month2.json`` 按名字调用）：

* ``cpsat_parallel``    同质并行机：每个工序在每台合格机器上一个
  ``OptionalIntervalVar``，一台机器的互斥用 ``AddNoOverlap``，选机用
  ``AddExactlyOne``。
* ``cpsat_jsp``         小型 job shop：工序链用 precedence 串起来，
  单合格机器的工序退化成**一个必选区间**（经典 JSP 形式），
  多合格机器时才用可选区间。
* ``cpsat_cumulative``  在机器互斥之外，再叠一层**有限容量资源**：
  所有工序都要占用 ``resource_demand`` 个单位，任意时刻总占用不得超过
  ``resource_capacity``，用 ``AddCumulative`` 表达。

建模与 M1 语义的对齐
--------------------
不重新定义问题。``Instance`` / ``Schedule`` / ``Objective`` / 独立验证器全部来自
M1（见 :mod:`opt_common.bridge`），本模块只负责「把问题写成一个 CP 模型」，
不负责计时记录与跨方法比较（那些属于 :mod:`opt_experiments`）。

三条纪律：

1. **``build_time`` 与 ``solve_time`` 分开**：前者是建模型的时间，后者是
   ``solver.Solve`` 的时间。
2. **``best_bound`` 只写求解器自己给的值**（``solver.BestObjectiveBound()``）。
   取不到就写 ``None``，**绝不拿目标值冒充下界**。
3. **求解器说 ``OPTIMAL`` 不等于解可行**：返回的排程仍要过 M1 的
   ``schedule_errors``（由调用方 / 测试执行）。

时间与整数
----------
CP-SAT 的变量是整数变量。M1 的 ``processing_time`` / ``release_time`` 本来就是
int，所以 ``time_scale=1`` 是恒等映射；当数据来自「非整数时间单位」（小时、
分钟、或带小数的工时）时，用 ``time_scale`` 把它们放大成整数再建模，
返回排程时再整除回来（``end = start + p * scale``，整除是精确的）。
权重是 float，而 CP-SAT 的目标系数必须是整数，所以
``weighted_completion_time`` 会把权重乘以 ``WEIGHT_SCALE`` 取整。
"""

from __future__ import annotations

import math
import time
from typing import Any

from ortools.sat.python import cp_model

from opt_common.bridge import (
    M2_OBJECTIVES,
    Instance,
    Schedule,
    ScheduledOperation,
    validate_instance,
)
from opt_solvers.registry import register
from opt_solvers.result import SolveResult

DEFAULT_TIME_LIMIT = 10.0

#: 权重是 float，CP-SAT 目标系数必须是整数：先乘 1000 取整，汇报时再除回来。
WEIGHT_SCALE = 1000

#: CP-SAT 原生状态 → M2 统一状态词表。一一对应，不做任何「脑补」。
_CP_STATUS_TO_M2 = {
    cp_model.OPTIMAL: "OPTIMAL",
    cp_model.FEASIBLE: "FEASIBLE",
    cp_model.INFEASIBLE: "INFEASIBLE",
    cp_model.UNKNOWN: "UNKNOWN",
    cp_model.MODEL_INVALID: "MODEL_INVALID",
}

#: 有可行解的状态。只有这两种状态才允许读 ``solver.Value()``。
_SOLVED_STATUSES = (cp_model.OPTIMAL, cp_model.FEASIBLE)


def cp_status_name(status: int) -> str:
    """CP-SAT 原生状态名（``StatusName`` 的薄包装，便于演示）。"""
    return cp_model.CpSolver().StatusName(status)


def m2_status(status: int) -> str:
    """把 CP-SAT 原生状态映射到 :data:`opt_solvers.result.STATUSES`。"""
    try:
        return _CP_STATUS_TO_M2[status]
    except KeyError:  # pragma: no cover - 防御未来新增状态
        return "FAILED"


# --- 建模 -----------------------------------------------------------------


class _BuiltModel:
    """建模产物：模型本身 + 读解时需要的一切句柄。"""

    def __init__(
        self,
        model: cp_model.CpModel,
        instance: Instance,
        starts: dict[str, Any],
        ends: dict[str, Any],
        presence: dict[tuple[str, str], Any],
        chosen_machine: dict[str, str],
        divisor: float,
        horizon: int,
        objective_kind: str,
    ) -> None:
        self.model = model
        self.instance = instance
        self.starts = starts
        self.ends = ends
        self.presence = presence
        self.chosen_machine = chosen_machine
        self.divisor = divisor
        self.horizon = horizon
        self.objective_kind = objective_kind


def _scaled_horizon(instance: Instance, time_scale: int) -> int:
    """所有变量共同的时间上界：完全串行加工一定可行。"""
    total = sum(op.processing_time for op in instance.operations)
    latest_release = max((job.release_time for job in instance.jobs), default=0)
    return (total + latest_release) * time_scale


def _integer_weights(instance: Instance) -> dict[str, int]:
    """把 float 权重放大成整数系数，并检查放大后没有系数退化成 0。"""
    weights = {job.id: round(job.weight * WEIGHT_SCALE) for job in instance.jobs}
    degenerate = [job.id for job in instance.jobs if weights[job.id] < 1]
    if degenerate:
        raise ValueError(
            f"weight too small for integer objective (scale={WEIGHT_SCALE}): {degenerate}"
        )
    return weights


def _objective_expression(
    model: cp_model.CpModel,
    instance: Instance,
    objective_name: str,
    ends: dict[str, Any],
    time_scale: int,
    horizon: int,
) -> tuple[Any, float]:
    """把 M1 的目标翻译成 CP-SAT 线性表达式，并给出「还原成真实单位」的除数。

    返回值 ``(expr, divisor)``：CP-SAT 的 ``ObjectiveValue()`` 除以 ``divisor``
    才是 M1 ``objective.py`` 口径下的目标值。
    """
    has_due = [job for job in instance.jobs if job.due_date is not None]

    # 每个 job 的完工时间 = 它最后一道工序的完工时间
    job_end: dict[str, Any] = {}
    for job in instance.jobs:
        last = job.operation_ids[-1]
        job_end[job.id] = ends[last]

    if not job_end:  # 空实例：所有目标都退化为常量 0
        return 0, float(time_scale)

    if objective_name == "makespan":
        span = model.NewIntVar(0, horizon, "makespan")
        model.AddMaxEquality(span, list(job_end.values()))
        return span, float(time_scale)

    if objective_name == "total_completion_time":
        return sum(job_end.values()), float(time_scale)

    if objective_name == "total_flow_time":
        offset = sum(job.release_time for job in instance.jobs) * time_scale
        return sum(job_end.values()) - offset, float(time_scale)

    if objective_name == "total_tardiness":
        terms = []
        for index, job in enumerate(has_due):
            tardy = model.NewIntVar(0, horizon, f"tardy_{index}_{job.id}")
            due = job.due_date * time_scale
            model.AddMaxEquality(tardy, [job_end[job.id] - due, 0])
            terms.append(tardy)
        if not terms:
            return 0, float(time_scale)
        return sum(terms), float(time_scale)

    if objective_name == "max_lateness":
        terms = []
        for index, job in enumerate(has_due):
            late = model.NewIntVar(-horizon, horizon, f"late_{index}_{job.id}")
            model.AddMaxEquality(late, [job_end[job.id] - job.due_date * time_scale])
            terms.append(late)
        # M1 的 max_lateness 在没有交期时返回 0（max(..., default=0)）
        if not terms:
            return 0, float(time_scale)
        worst = model.NewIntVar(-horizon, horizon, "lmax")
        model.AddMaxEquality(worst, terms)
        return worst, float(time_scale)

    if objective_name == "weighted_completion_time":
        weights = _integer_weights(instance)
        expr = sum(weights[job.id] * job_end[job.id] for job in instance.jobs)
        return expr, float(time_scale) * WEIGHT_SCALE

    raise ValueError(f"unsupported objective for CP-SAT: {objective_name}")


def build_cpsat_model(
    instance: Instance,
    objective_name: str,
    *,
    time_scale: int = 1,
    resource_capacity: int | None = None,
    resource_demand: int = 1,
    prefer_fixed_route: bool = False,
    horizon: int | None = None,
) -> _BuiltModel:
    """建一个区间模型。所有三个注册方法共用这一份建模逻辑。

    参数
    ----
    time_scale
        时间放大倍数，必须 >= 1 的整数；``1`` 表示恒等。
    resource_capacity
        ``None`` 表示不加容量资源；给整数则追加一条 ``AddCumulative``。
    resource_demand
        每个工序在任意时刻占用的资源单位数。
    prefer_fixed_route
        ``True`` 时，**只有一个合格机器**的工序用必选区间（经典 JSP：
        每个工序恰好一个区间）；``False`` 时该工序仍然走可选区间。
    horizon
        ``None`` 时按「全部串行」自动推导；显式给一个过小的值可以让变量域为空，
        用于演示 ``MODEL_INVALID``。
    """
    validate_instance(instance)
    if type(time_scale) is not int or time_scale < 1:
        raise ValueError(f"time_scale must be an integer >= 1, got {time_scale!r}")
    if objective_name not in M2_OBJECTIVES:
        raise ValueError(f"unknown objective: {objective_name}")
    if resource_demand < 1:
        raise ValueError(f"resource_demand must be >= 1, got {resource_demand}")

    if horizon is None:
        horizon = _scaled_horizon(instance, time_scale)

    model = cp_model.CpModel()
    job_by_id = {job.id: job for job in instance.jobs}

    starts: dict[str, Any] = {}
    ends: dict[str, Any] = {}
    presence: dict[tuple[str, str], Any] = {}
    chosen_machine: dict[str, str] = {}
    machine_intervals: dict[str, list[Any]] = {machine.id: [] for machine in instance.machines}
    all_intervals: list[Any] = []
    all_demands: list[int] = []

    for op in instance.operations:
        job = job_by_id[op.job_id]
        size = op.processing_time * time_scale
        # 释放时间是工程约束：变量的下界直接取 r，而不是先放开再加一条约束
        start = model.NewIntVar(job.release_time * time_scale, horizon, f"start_{op.id}")
        end = model.NewIntVar(job.release_time * time_scale + size, horizon, f"end_{op.id}")
        starts[op.id] = start
        ends[op.id] = end

        eligibility = tuple(op.eligible_machine_ids)
        fixed = prefer_fixed_route and len(eligibility) == 1
        if fixed:
            # 经典 JSP：一个工序恰好一个区间，机器由路由给定
            machine_id = eligibility[0]
            interval = model.NewIntervalVar(start, size, end, f"iv_{op.id}")
            machine_intervals[machine_id].append(interval)
            all_intervals.append(interval)
            all_demands.append(resource_demand)
            chosen_machine[op.id] = machine_id
            continue

        # 并行机 / 柔性路由：每台合格机器一个可选区间，恰好一个成立
        presences = []
        for machine_id in eligibility:
            flag = model.NewBoolVar(f"pres_{op.id}_{machine_id}")
            interval = model.NewOptionalIntervalVar(
                start, size, end, flag, f"iv_{op.id}_{machine_id}"
            )
            presence[(op.id, machine_id)] = flag
            presences.append(flag)
            machine_intervals[machine_id].append(interval)
            all_intervals.append(interval)
            all_demands.append(resource_demand)
        if len(presences) == 1:
            # 只有一个选项时 ExactlyOne 退化成「必须为真」
            model.Add(presences[0] == 1)
        else:
            model.AddExactlyOne(presences)

    # 每台机器上不允许重叠：一份 NoOverlap 顶掉所有两两 disjunctive 约束
    for intervals in machine_intervals.values():
        if len(intervals) > 1:
            model.AddNoOverlap(intervals)

    # 每个 job 的工序链：前一道的完工不得晚于后一道的开工
    for job in instance.jobs:
        for before, after in zip(job.operation_ids, job.operation_ids[1:]):
            model.Add(ends[before] <= starts[after])

    if resource_capacity is not None:
        if resource_capacity < 0:
            raise ValueError("resource_capacity must be >= 0")
        model.AddCumulative(all_intervals, all_demands, resource_capacity)

    expr, divisor = _objective_expression(
        model, instance, objective_name, ends, time_scale, horizon
    )
    if isinstance(expr, int):  # 常量目标（例如空实例、或没有任何交期的 Lmax）
        expr = cp_model.LinearExpr.constant(expr)
    model.Minimize(expr)

    return _BuiltModel(
        model=model,
        instance=instance,
        starts=starts,
        ends=ends,
        presence=presence,
        chosen_machine=chosen_machine,
        divisor=divisor,
        horizon=horizon,
        objective_kind=objective_name,
    )


# --- 求解 -----------------------------------------------------------------


def _read_schedule(solver: cp_model.CpSolver, built: _BuiltModel, time_scale: int) -> Schedule:
    """从求解器读出时间值与选机结果，还原成 M1 的 ``Schedule``。

    只有在 ``OPTIMAL`` / ``FEASIBLE`` 下才允许调用：其余状态下 CP-SAT 的
    ``Value()`` 返回的是未初始化的内部值，读出来会得到假数据。
    """
    items = []
    for op in built.instance.operations:
        if op.id in built.chosen_machine:
            machine_id = built.chosen_machine[op.id]
        else:
            eligible = [
                m for m in op.eligible_machine_ids if solver.BooleanValue(built.presence[(op.id, m)])
            ]
            if len(eligible) != 1:
                raise ValueError(
                    f"model did not select exactly one machine for {op.id}: {eligible}"
                )
            machine_id = eligible[0]
        start = solver.Value(built.starts[op.id])
        end = solver.Value(built.ends[op.id])
        # end = start + p * scale，整除回真实时间单位是精确的
        items.append(ScheduledOperation(op.id, machine_id, start // time_scale, end // time_scale))
    return Schedule(tuple(items))


def _solve_built(
    built: _BuiltModel,
    instance: Instance,
    spec: dict[str, Any],
    method: str,
    *,
    build_time: float,
    time_scale: int,
) -> SolveResult:
    """跑求解器并把结果包成统一 ``SolveResult``。"""
    objective_name = built.objective_kind
    time_limit = float(spec.get("time_limit", DEFAULT_TIME_LIMIT) or DEFAULT_TIME_LIMIT)
    seed = int(spec.get("seed", 0) or 0)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = 1  # 确定性：单线程 + 固定种子
    solver.parameters.random_seed = seed

    started = time.perf_counter()
    status = solver.Solve(built.model)
    solve_time = time.perf_counter() - started
    status_name = solver.StatusName(status)
    detail: dict[str, Any] = {
        "cp_status": status_name,
        "time_scale": time_scale,
        "objective_divisor": built.divisor,
        "horizon": built.horizon,
        "time_limit": time_limit,
        "num_search_workers": 1,
        "random_seed": seed,
        "conflicts": int(solver.NumConflicts()),
        "branches": int(solver.NumBranches()),
        "booleans": int(solver.NumBooleans()),
        "cp_wall_time": float(solver.WallTime()),
        "bound_kind": "solver_objective_bound",
    }

    def _finish(
        m2: str,
        *,
        schedule: Schedule | None = None,
        objective: float | None = None,
        best_bound: float | None = None,
        extra: dict[str, Any] | None = None,
    ) -> SolveResult:
        if extra:
            detail.update(extra)
        return SolveResult(
            method=method,
            status=m2,
            objective=objective,
            best_bound=best_bound,
            schedule=schedule,
            build_time=build_time,
            solve_time=solve_time,
            iterations=int(solver.NumBranches()),
            detail=detail,
        )

    if status not in _SOLVED_STATUSES:
        # INFEASIBLE / UNKNOWN / MODEL_INVALID：没有可读的解，也没有可比的界。
        # INFEASIBLE 时 BestObjectiveBound() 会返回 0，直接写进结果就是伪证据。
        detail["raw_best_bound"] = float(solver.BestObjectiveBound())
        return _finish(m2_status(status))

    schedule = _read_schedule(solver, built, time_scale)
    # 目标由 M1 的 objective.py 在返回排程上重新计算：与启发式基线同一口径，
    # 也顺手暴露「模型目标」与「真实目标」不一致这种最隐蔽的建模错误。
    objective = float(M2_OBJECTIVES[objective_name](instance, schedule))
    cp_objective = float(solver.ObjectiveValue()) / built.divisor
    detail["cp_objective"] = cp_objective
    detail["cp_objective_matches_m1"] = math.isclose(cp_objective, objective, abs_tol=1e-6)

    best_bound: float | None = None
    raw_bound = float(solver.BestObjectiveBound()) / built.divisor
    detail["raw_best_bound"] = raw_bound
    if math.isfinite(raw_bound) and raw_bound <= objective + 1e-6:
        best_bound = min(raw_bound, objective)
    elif math.isfinite(raw_bound):
        # 求解器给出高于可行解的下界：不隐藏、也不当成界用
        detail["bound_anomaly"] = raw_bound
    return _finish(
        m2_status(status),
        schedule=schedule,
        objective=objective,
        best_bound=best_bound,
    )


def _spec_int(value: Any, name: str, default: int) -> int:
    """从 ``spec`` 里取一个整型参数；浮点但是整数值的也接受（JSON 里常见）。"""
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be an integer, got {value!r}")
    if float(value) != int(value):
        raise ValueError(f"{name} must be an integer, got {value!r}")
    return int(value)


def _solve_cpsat(
    instance: Instance,
    spec: dict[str, Any],
    method: str,
    *,
    prefer_fixed_route: bool = False,
    use_capacity: bool = False,
) -> SolveResult:
    """三个注册方法的公共前端：建模计时 → 求解计时 → 统一结果。"""
    objective_name = spec.get("objective", "makespan")
    if objective_name not in M2_OBJECTIVES:
        # 与 heuristics.py 同一条纪律：spec 写错记 FAILED，不是模型非法
        return SolveResult(
            method=method,
            status="FAILED",
            detail={"failure_reason": f"unknown objective: {objective_name}", "stage": "spec"},
        )

    started = time.perf_counter()
    try:
        time_scale = _spec_int(spec.get("time_scale"), "time_scale", 1)
        capacity = None
        demand = 1
        if use_capacity:
            demand = _spec_int(spec.get("resource_demand"), "resource_demand", 1)
            capacity = _spec_int(
                spec.get("resource_capacity"), "resource_capacity", len(instance.machines)
            )
        built = build_cpsat_model(
            instance,
            objective_name,
            time_scale=time_scale,
            resource_capacity=capacity,
            resource_demand=demand,
            prefer_fixed_route=prefer_fixed_route,
        )
    except (ValueError, KeyError) as exc:
        return SolveResult(
            method=method,
            status="FAILED",
            detail={"failure_reason": f"{type(exc).__name__}: {exc}", "stage": "spec"},
        )
    build_time = time.perf_counter() - started

    return _solve_built(built, instance, spec, method, build_time=build_time, time_scale=time_scale)


# --- 三个注册方法 ----------------------------------------------------------


@register("cpsat_parallel", "CP-SAT 同质并行机：OptionalIntervalVar + ExactlyOne + NoOverlap")
def cpsat_parallel(instance: Instance, spec: dict[str, Any]) -> SolveResult:
    """同质并行机 ``P||Cmax``（可带释放时间）：选机是可选的区间。"""
    return _solve_cpsat(instance, spec, "cpsat_parallel")


@register("cpsat_jsp", "CP-SAT 小型 job shop：precedence + 每机器 NoOverlap")
def cpsat_jsp(instance: Instance, spec: dict[str, Any]) -> SolveResult:
    """小型 job shop：每个工序一个区间，工序链用 precedence 串起来。

    单合格机器的工序（真正的 JSP 路由）用必选区间；多合格机器时退化成
    可选区间 + ``ExactlyOne``（柔性路由）。
    """
    return _solve_cpsat(instance, spec, "cpsat_jsp", prefer_fixed_route=True)


@register("cpsat_cumulative", "CP-SAT 有限容量资源：AddCumulative 与 NoOverlap 语义对照")
def cpsat_cumulative(instance: Instance, spec: dict[str, Any]) -> SolveResult:
    """在机器互斥之外追加一条 ``AddCumulative`` 容量约束。

    ``resource_capacity`` 默认等于机器数、``resource_demand`` 默认 1；
    默认取值下容量约束是冗余的（NoOverlap 已经保证每台机器至多一个工序），
    因此它与 ``cpsat_parallel`` 同解——这正是「容量约束什么时候真正收紧模型」
    的对照组。
    """
    return _solve_cpsat(instance, spec, "cpsat_cumulative", use_capacity=True)


# --- 诊断与独立检查 --------------------------------------------------------


def solve_model_invalid_demo(instance: Instance, spec: dict[str, Any]) -> SolveResult:
    """**刻意构造的非法模型**：把时间上界设成 -1，变量域为空。

    变量域为空是 CP-SAT 判 ``MODEL_INVALID`` 的典型原因（而不是判
    ``INFEASIBLE``）：模型还没进入搜索，求解器就已经拒绝它了。
    这个函数只为演示状态词表而存在，**不是**一个可用的建模入口。
    """
    objective_name = spec.get("objective", "makespan")
    started = time.perf_counter()
    built = build_cpsat_model(instance, objective_name, time_scale=1, horizon=-1)
    build_time = time.perf_counter() - started
    return _solve_built(built, instance, spec, "cpsat_model_invalid_demo",
                        build_time=build_time, time_scale=1)


def cumulative_profile(
    instance: Instance, schedule: Schedule, demand: int = 1
) -> tuple[int, int | None]:
    """独立重算「任意时刻的并发资源占用」，返回 ``(峰值占用, 峰值时刻)``。

    M1 的 ``validate_schedule`` 只校验机器互斥、机器资格、precedence 与释放时间，
    **不覆盖** Cumulative 的容量约束——那是 M2 在模型层新加的语义。
    所以容量约束必须由这个函数独立复核，不能拿「M1 验证器通过」冒充。
    """
    events: dict[int, int] = {}
    by_id = {op.id: op for op in instance.operations}
    for item in schedule.operations:
        duration = by_id[item.operation_id].processing_time
        if item.end_time - item.start_time != duration:  # pragma: no cover - 防御
            raise ValueError(f"operation {item.operation_id}: duration mismatch")
        events[item.start_time] = events.get(item.start_time, 0) + demand
        events[item.end_time] = events.get(item.end_time, 0) - demand

    peak = 0
    peak_time: int | None = None
    current = 0
    for moment in sorted(events):
        current += events[moment]
        if current > peak:
            peak, peak_time = current, moment
    return peak, peak_time
