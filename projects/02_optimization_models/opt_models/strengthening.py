"""Week 4 的模型强化与初解注入：对称破缺、冗余约束、warm start、variable fixing。

本模块提供三个注册方法（`configs/month2.json` 引用）：

* ``cpsat_symmetry``  —— 同质并行机 CP-SAT 模型 + 对称破缺 + 冗余下界约束；
* ``milp_warmstart``  —— 单机 MILP，用 M1 规则解做 MIP start，并配目标上界割；
* ``milp_fixing``     —— 单机 MILP 的 variable fixing 变体（固定前缀，重解剩余）。

三条贯穿全模块的纪律：

1. **强化不得改变最优值。** 对称破缺只加「每个最优解都能被重标号满足」的约束；
   冗余下界约束由模型自身蕴含；目标上界割来自一个**已知可行解**。
   任何一条都不允许把最优解切掉——测试里用未强化模型和独立枚举对拍。
2. **结果目标值一律用 M1 的 ``objective`` 重算**，不采用求解器自报的数值；
   两者之差作为数值残差记进 ``detail``（求解器自报 = 自己证明自己）。
3. **没有 bound 就写 ``None``**。整数目标的界可以安全下取整，但绝不能上取整，
   也绝不能把 ``objective`` 填进 ``best_bound``。

返回的排程一律先过 M1 的独立验证器；不通过就记 ``FAILED``，而不是把
「求解器说可行」当成可行。
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any, Callable

from opt_common.bridge import (
    M2_OBJECTIVES,
    Instance,
    Schedule,
    ScheduledOperation,
    edd,
    lpt,
    parallel_lpt,
    schedule_errors,
    spt,
    wspt,
)
from opt_solvers.registry import register
from opt_solvers.result import SolveResult

#: M1 规则入口。``parallel_lpt`` 在单机实例上退化为 LPT 顺序，仍可作为初解来源。
RULES: dict[str, Callable[[Instance], Schedule]] = {
    "spt": spt,
    "edd": edd,
    "wspt": wspt,
    "lpt": lpt,
    "parallel_lpt": parallel_lpt,
}

#: 被本模块显式支持的目标。CP-SAT 侧只做机器对称目标（``makespan``）与
#: 机器非对称目标（``total_tardiness``）两类，其余目标直接记 FAILED，
#: 不做「假装支持」。
CPSAT_OBJECTIVES = ("makespan", "total_tardiness")


# --------------------------------------------------------------------------
# 公共工具
# --------------------------------------------------------------------------
def detect_machine_symmetry(instance: Instance) -> bool:
    """识别同质机器对称性：所有工序的可选机器集合都等于全部机器。

    满足时，「把机器编号重排一遍」是模型的一个**对称变换**：任何可行排程
    重标号后仍然可行，且每条机器上的负载集合不变。这正是对称破缺的合法性来源。
    只要有任意一道工序的资格集合小于全部机器，这个变换就不再保持可行性——
    此时本函数返回 ``False``，调用方**必须放弃**按机器编号做的对称破缺。
    """
    machine_ids = {machine.id for machine in instance.machines}
    if len(machine_ids) < 2:
        return False
    return all(set(op.eligible_machine_ids) == machine_ids for op in instance.operations)


def machine_loads(instance: Instance, schedule: Schedule) -> dict[str, int]:
    """每台机器上的总加工量（用于对称破缺的声明式检查）。"""
    loads = {machine.id: 0 for machine in instance.machines}
    for item in schedule.operations:
        loads[item.machine_id] += item.end_time - item.start_time
    return loads


def makespan_lower_bound(instance: Instance) -> int:
    """同质并行机 makespan 的下界：``max(M1 下界, max_j (r_j + p_j))``。

    第一项是 M1 的 ``parallel_makespan_lower_bound``（总负载平摊与最长工序）；
    第二项在有释放时间时必须补上：任何工序都不可能早于 ``r_j + p_j`` 完成。
    待排工序为空时返回 0。
    """
    processing = [op.processing_time for op in instance.operations]
    if not processing:
        return 0
    total = sum(processing)
    longest = max(processing)
    machines = max(1, len(instance.machines))
    staffed = max(
        job.release_time + _job_processing(instance, job.id) for job in instance.jobs
    )
    return max(longest, math.ceil(total / machines), staffed)


def _job_processing(instance: Instance, job_id: str) -> int:
    return sum(op.processing_time for op in instance.operations if op.job_id == job_id)


def _single_operation_layout(instance: Instance) -> bool:
    """是否为「每 Job 恰好一道工序」的布局（M1 规则与本模块的 MILP 都要求）。"""
    return all(len(job.operation_ids) == 1 for job in instance.jobs)


def _objective_name(spec: dict[str, Any], default: str = "makespan") -> str:
    return str(spec.get("objective", default))


def _objective_value(instance: Instance, schedule: Schedule, name: str) -> float:
    """**唯一**的目标值来源：M1 的评价器。求解器自报值只进 detail。"""
    if name not in M2_OBJECTIVES:
        raise ValueError(f"unknown objective: {name}")
    return float(M2_OBJECTIVES[name](instance, schedule))


def _floor_bound(value: float | None, objective: float | None) -> float | None:
    """把求解器报的回界转成**安全**的整数下界。

    本模块处理的目标（makespan / total_tardiness）取值都是整数，因此任何合法
    下界都可以下取整后仍然合法。反向（上取整）会把界抬到最优值之上，制造
    「gap 恒为 0」的伪证据。``1e-6`` 容差用于吸收 CBC / CP-SAT 打印出的
    ``65.999999999`` 这类浮点噪声。
    """
    if value is None:
        return None
    floored = float(math.floor(value + 1e-6))
    if objective is None:
        return floored
    return min(floored, float(objective))


def _sequence_from_schedule(instance: Instance, schedule: Schedule) -> list[int]:
    """把 M1 规则返回的 ``Schedule`` 还原成「工序下标排列」。

    关键坑：规则的**静态排序键**与它实际排出的**加工顺序**在有释放时间时
    并不相同（non-delay 列表调度会先做已释放里优先级最高的那个）。所以初解
    必须按 ``start_time`` 反解，而不是重放规则的排序键。
    """
    index = {op.id: position for position, op in enumerate(instance.operations)}
    ordered = sorted(schedule.operations, key=lambda item: item.start_time)
    return [index[item.operation_id] for item in ordered]


def _seed_schedule(
    instance: Instance, objective_name: str, rule: str
) -> tuple[str, Schedule, float, dict[str, float]]:
    """跑 M1 规则取初解。``rule="best"`` 时取多条规则里目标值最小的那条。

    规则不适用（多工序、单机规则用在并行机上等）时抛 ``ValueError``，这里
    按「该规则出局」处理，继续试下一条，而不是伪造一个初解。
    """
    if rule != "best" and rule not in RULES:
        raise ValueError(f"unknown rule: {rule}")
    candidates = list(RULES) if rule == "best" else [rule]
    values: dict[str, float] = {}
    best: tuple[str, Schedule, float] | None = None
    for name in candidates:
        try:
            schedule = RULES[name](instance)
            if schedule_errors(instance, schedule):
                continue
        except (ValueError, IndexError, KeyError):
            continue
        value = _objective_value(instance, schedule, objective_name)
        values[name] = value
        if best is None or value < best[2]:
            best = (name, schedule, value)
    if best is None:
        raise ValueError(f"no rule produced a feasible schedule for rule={rule!r}")
    return best[0], best[1], best[2], values


def _finish(
    instance: Instance,
    method: str,
    schedule: Schedule | None,
    objective_name: str,
    *,
    status: str,
    best_bound: float | None,
    solve_time: float,
    build_time: float = 0.0,
    iterations: int | None = None,
    solver_objective: float | None = None,
    detail: dict[str, Any] | None = None,
) -> SolveResult:
    """收口：用独立验证器把关，再用 M1 评价器重算目标值。"""
    detail = dict(detail or {})
    if schedule is None:
        detail.setdefault("failure_reason", "no schedule returned")
        return SolveResult(
            method=method,
            status=status,
            objective=None,
            best_bound=None,
            schedule=None,
            build_time=build_time,
            solve_time=solve_time,
            iterations=iterations,
            detail=detail,
        )

    errors = schedule_errors(instance, schedule)
    if errors:
        # 求解器自称可行不算数：独立验证器说了才算。
        detail["validation_errors"] = errors[:5]
        detail["failure_reason"] = "independent validator rejected returned schedule"
        return SolveResult(
            method=method,
            status="FAILED",
            objective=None,
            best_bound=None,
            schedule=None,
            build_time=build_time,
            solve_time=solve_time,
            iterations=iterations,
            detail=detail,
        )

    objective = _objective_value(instance, schedule, objective_name)
    if solver_objective is not None:
        detail["solver_objective"] = solver_objective
        detail["objective_residual"] = round(objective - solver_objective, 9)
    return SolveResult(
        method=method,
        status=status,
        objective=objective,
        best_bound=_floor_bound(best_bound, objective),
        schedule=schedule,
        build_time=build_time,
        solve_time=solve_time,
        iterations=iterations,
        detail=detail,
    )


# --------------------------------------------------------------------------
# 并行机 CP-SAT 模型（cpsat_symmetry）
# --------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class ParallelModelContext:
    """CP-SAT 并行机模型的可复用骨架。

    变量与约束的语义只在这里定义一次：诊断模块（Week 4 Day 3）在自己的
    可满足性模型里直接复用，避免出现「两套模型、两种语义」。
    """

    model: Any
    instance: Instance
    objective: str
    horizon: int
    lower_bound: int
    machines: tuple[str, ...]
    operations: tuple[str, ...]
    start: dict[tuple[str, str], Any]
    end: dict[tuple[str, str], Any]
    literal: dict[tuple[str, str], Any]
    interval: dict[tuple[str, str], Any]
    end_of_operation: dict[str, Any]
    makespan: Any
    tardiness: dict[str, Any]


def build_parallel_model(
    instance: Instance, objective: str = "makespan", horizon: int | None = None
) -> ParallelModelContext:
    """构造同质并行机 CP-SAT 模型（不含目标、不含强化、不含初解）。

    编码要点：

    * 每个 (工序, 机器) 一个可选区间变量与一个布尔 ``literal``；
    * 每道工序 ``AddExactlyOne``：必须且只能选一台机器；
    * 每台机器 ``AddNoOverlap``：同一台机器上不允许重叠；
    * 未选中的区间没有语义，所以显式约束 ``end == 0``（``OnlyEnforceIf`` 取反），
      这样 ``end_of_operation[o] = Σ_m end[o][m]`` 才是这道工序真正的完工时间。
    """
    from ortools.sat.python import cp_model

    if objective not in CPSAT_OBJECTIVES:
        raise ValueError(f"cpsat parallel model does not support objective: {objective}")
    horizon = horizon or _default_horizon(instance)
    machines = tuple(machine.id for machine in instance.machines)
    operations = tuple(op.id for op in instance.operations)

    model = cp_model.CpModel()
    start: dict[tuple[str, str], Any] = {}
    end: dict[tuple[str, str], Any] = {}
    literal: dict[tuple[str, str], Any] = {}
    interval: dict[tuple[str, str], Any] = {}
    end_of_operation: dict[str, Any] = {}

    for op in instance.operations:
        job = next(job for job in instance.jobs if job.id == op.job_id)
        # 只为**合格机器**建变量：给不合格的 (工序, 机器) 对也建布尔量，模型就能
        # 把工序派给一台它上不了的机器，M1 验证器会直接报 illegal assignment。
        eligible = [mid for mid in machines if mid in op.eligible_machine_ids]
        if not eligible:
            raise ValueError(f"operation {op.id} has no eligible machine")
        for machine_id in eligible:
            key = (op.id, machine_id)
            literal[key] = model.NewBoolVar(f"x_{op.id}_{machine_id}")
            start[key] = model.NewIntVar(job.release_time, horizon, f"s_{op.id}_{machine_id}")
            # end 的下界必须是 0 而不是 r_j：未选中的区间要被显式压成 end == 0，
            # 只有这样 `end_of_operation = Σ_m end[o][m]` 才是真实完工时间。
            end[key] = model.NewIntVar(0, horizon, f"e_{op.id}_{machine_id}")
            interval[key] = model.NewOptionalIntervalVar(
                start[key], op.processing_time, end[key], literal[key], f"iv_{op.id}_{machine_id}"
            )
            model.Add(end[key] == 0).OnlyEnforceIf(literal[key].Not())
        model.AddExactlyOne([literal[(op.id, machine_id)] for machine_id in eligible])
        end_of_operation[op.id] = model.NewIntVar(0, horizon, f"E_{op.id}")
        model.Add(
            end_of_operation[op.id] == sum(end[(op.id, machine_id)] for machine_id in eligible)
        )

    for machine_id in machines:
        intervals = [
            interval[(op.id, machine_id)]
            for op in instance.operations
            if (op.id, machine_id) in interval
        ]
        if intervals:
            model.AddNoOverlap(intervals)

    makespan = model.NewIntVar(0, horizon, "Cmax")
    model.AddMaxEquality(makespan, [end_of_operation[op.id] for op in instance.operations])

    tardiness: dict[str, Any] = {}
    if objective == "total_tardiness":
        for op in instance.operations:
            job = next(job for job in instance.jobs if job.id == op.job_id)
            due = horizon + 1 if job.due_date is None else job.due_date
            tardiness[op.id] = model.NewIntVar(0, horizon, f"T_{op.id}")
            model.Add(tardiness[op.id] >= end_of_operation[op.id] - due)

    return ParallelModelContext(
        model=model,
        instance=instance,
        objective=objective,
        horizon=horizon,
        lower_bound=makespan_lower_bound(instance),
        machines=machines,
        operations=operations,
        start=start,
        end=end,
        literal=literal,
        interval=interval,
        end_of_operation=end_of_operation,
        makespan=makespan,
        tardiness=tardiness,
    )


def _default_horizon(instance: Instance) -> int:
    """合法上界：所有工序串行做完 + 最晚释放时间之后。"""
    total = sum(op.processing_time for op in instance.operations)
    latest = max((job.release_time for job in instance.jobs), default=0)
    return latest + total


def add_load_ordering(context: ParallelModelContext) -> int:
    """对称破缺：按机器负载降序排列机器编号。

    合法性：机器同质（加工时间与机器无关）且所有工序全资格时，把机器编号做
    任意置换仍是同一个可行解集合，且 targets 只要对机器置换不变（本模块的
    ``makespan``、``total_tardiness`` 都满足），最优值就不变。既然任何解都能
    重标号成负载降序，约束 ``load[m] >= load[m+1]`` 不切掉任何最优解。

    **反例警示**：若工序资格集合逐机器不同（``Q``/``R`` 型或有人为资格限制），
    这个置换不再保持可行性，该约束就是错的——所以调用前必须过
    :func:`detect_machine_symmetry`。
    """
    model = context.model
    added = 0
    for left, right in zip(context.machines, context.machines[1:]):
        model.Add(
            sum(
                op.processing_time * context.literal[(op.id, left)]
                for op in context.instance.operations
            )
            >= sum(
                op.processing_time * context.literal[(op.id, right)]
                for op in context.instance.operations
            )
        )
        added += 1
    return added


def add_redundant_bounds(context: ParallelModelContext) -> int:
    """冗余约束：把**解析下界**显式写进模型。

    这一族约束全部由模型自身蕴含，写出来不改变可行解集合、更不改变最优值，
    作用是把它交给求解器的传播器：

    * ``Cmax >= LB``，其中 ``LB = max(max_j p_j, ceil(Σp/m), max_j(r_j+p_j))``；
      这是 M1 已经能解析算出的下界，bound 的改进来自「把已知事实写进模型」，
      不是求解器发现了新东西。
    * 每道工序 ``C_o >= r_o + p_o``：由区间定义 ``C = S + p`` 与 ``S >= r_o``
      蕴含（未选中的那个可选区间被压成 ``end == 0``，所以求和式仍成立）。

    **反例警示**（本文件真实踩过的坑）：曾经这里写过「所有工序完工之和不超过
    ``m·Σp``」。带释放时间时它是**错的**：机器空转会让 ``Σ C_o`` 超过该值，
    于是它把一个合法最优解切掉了。识别方法是让同一个实例在「开/关强化」两种
    设定下各求一次最优——最优值不同即证明这条约束不是冗余约束，而是新约束。
    """
    model = context.model
    added = 0
    if context.objective == "makespan":
        model.Add(context.makespan >= context.lower_bound)
        added += 1
    for op in context.instance.operations:
        job = next(job for job in context.instance.jobs if job.id == op.job_id)
        model.Add(
            context.end_of_operation[op.id] >= job.release_time + op.processing_time
        )
        added += 1
    return added


def solve_parallel_cpsat(
    instance: Instance,
    spec: dict[str, Any],
    *,
    symmetry_breaking: bool,
    redundant_constraints: bool,
    hint_schedule: Schedule | None = None,
    method: str = "cpsat_symmetry",
) -> SolveResult:
    """并行机 CP-SAT 求解，强化学手段由调用方逐项开关（便于做消融）。"""
    objective = _objective_name(spec)
    time_limit = float(spec.get("time_limit", 10.0))
    seed = int(spec.get("seed", 0) or 0)
    workers = int(spec.get("workers", 1) or 1)
    if objective not in CPSAT_OBJECTIVES:
        return SolveResult(
            method=method,
            status="FAILED",
            detail={"failure_reason": f"cpsat parallel model does not support {objective}"},
        )
    if not _single_operation_layout(instance):
        return SolveResult(
            method=method,
            status="FAILED",
            detail={"failure_reason": "parallel model requires exactly one operation per job"},
        )
    if len(instance.machines) < 1 or not instance.operations:
        return SolveResult(
            method=method,
            status="FAILED",
            detail={"failure_reason": "instance has no machine or no operation"},
        )

    from ortools.sat.python import cp_model

    started = time.perf_counter()
    context = build_parallel_model(instance, objective)
    model = context.model
    symmetry_applied = False
    strengths: dict[str, Any] = {"redundant_constraints": 0, "symmetry_rows": 0}
    if redundant_constraints:
        strengths["redundant_constraints"] = add_redundant_bounds(context)
    if symmetry_breaking:
        if detect_machine_symmetry(instance) and objective == "makespan":
            strengths["symmetry_rows"] = add_load_ordering(context)
            symmetry_applied = True
        else:
            # 机器不对称或目标对机器置换不敏感时，按机器编号破缺会切掉最优解。
            strengths["symmetry_skipped_reason"] = (
                "machines are not interchangeable"
                if not detect_machine_symmetry(instance)
                else f"objective {objective} is not invariant under machine relabelling"
            )
    if objective == "makespan":
        model.Minimize(context.makespan)
    else:
        model.Minimize(sum(context.tardiness.values()))

    hint_info: dict[str, Any] = {"hint_given": False}
    if hint_schedule is not None:
        hinted = 0
        for item in hint_schedule.operations:
            key = (item.operation_id, item.machine_id)
            if key in context.literal:
                model.AddHint(context.literal[key], 1)
                hinted += 1
        hint_info = {
            "hint_given": True,
            "hint_literals": hinted,
            "hint_objective": _objective_value(instance, hint_schedule, objective),
        }

    build_time = time.perf_counter() - started
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max(0.001, time_limit)
    solver.parameters.random_seed = seed
    solver.parameters.num_search_workers = max(1, workers)
    call_started = time.perf_counter()
    status_code = solver.Solve(model)
    solve_time = time.perf_counter() - call_started
    status_name = solver.StatusName(status_code)
    detail: dict[str, Any] = {
        "backend": "cp-sat",
        "objective_name": objective,
        "workers": max(1, workers),
        "seed": seed,
        "time_limit": time_limit,
        "solver_status": status_name,
        "solver_wall_time": round(solver.WallTime(), 6),
        "branches": solver.NumBranches(),
        "conflicts": solver.NumConflicts(),
        "num_booleans": solver.NumBooleans(),
        "horizon": context.horizon,
        "lower_bound_analytic": context.lower_bound,
        "symmetry_breaking_applied": symmetry_applied,
        "machine_symmetry_detected": detect_machine_symmetry(instance),
        **strengths,
        **hint_info,
    }
    detail["termination_reason"] = (
        "proved optimal" if status_name == "OPTIMAL" else f"solver returned {status_name}"
    )

    if status_name in ("INFEASIBLE", "MODEL_INVALID"):
        return SolveResult(
            method=method,
            status=status_name,
            build_time=build_time,
            solve_time=solve_time,
            iterations=solver.NumBranches(),
            detail=detail,
        )
    if status_name not in ("OPTIMAL", "FEASIBLE"):
        return SolveResult(
            method=method,
            status="UNKNOWN",
            build_time=build_time,
            solve_time=solve_time,
            iterations=solver.NumBranches(),
            detail=detail,
        )

    schedule = Schedule(
        tuple(
            ScheduledOperation(
                operation_id=op.id,
                machine_id=machine_id,
                start_time=int(solver.Value(context.start[(op.id, machine_id)])),
                end_time=int(solver.Value(context.end_of_operation[op.id])),
            )
            for op in instance.operations
            for machine_id in context.machines
            if (op.id, machine_id) in context.literal
            and solver.Value(context.literal[(op.id, machine_id)]) == 1
        )
    )
    return _finish(
        instance,
        method,
        schedule,
        objective,
        status=status_name,
        best_bound=solver.BestObjectiveBound(),
        solve_time=solve_time,
        build_time=build_time,
        iterations=solver.NumBranches(),
        solver_objective=solver.ObjectiveValue(),
        detail=detail,
    )


@register("cpsat_symmetry", "同质并行机 CP-SAT + 对称破缺 + 冗余下界约束")
def cpsat_symmetry(instance: Instance, spec: dict[str, Any]) -> SolveResult:
    """对称破缺版并行机模型：负载降序 + 解析下界，目标不变、最优值不变。"""
    return solve_parallel_cpsat(
        instance,
        spec,
        symmetry_breaking=True,
        redundant_constraints=True,
        hint_schedule=None,
        method="cpsat_symmetry",
    )


# --------------------------------------------------------------------------
# 单机 MILP（milp_warmstart / milp_fixing）
# --------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class MilpModelContext:
    """单机位置式 MILP 的骨架：``x[j][k]`` 表示 job j 排在位置 k。"""

    solver: Any
    instance: Instance
    objective: str
    horizon: int
    jobs: tuple[str, ...]
    assign: list[list[Any]]
    start: list[Any]
    completion: list[Any]
    tardiness: list[Any]
    expression: Any
    variables: int
    constraints: int


def build_single_machine_milp(instance: Instance, objective: str = "total_tardiness") -> MilpModelContext:
    """位置式单机 MILP（Week 2 的排序变量 + 时间变量 + 迟交变量）。

    三个「不需要 Big-M」的线性化技巧都在这里用上：

    * ``S_k >= Σ_j r_j x[j,k]``：右边只有被选中的那个 job 贡献释放时间；
    * ``C_k = S_k + Σ_j p_j x[j,k]``：完工时间 = 开工 + 加工量；
    * ``T_k >= C_k - Σ_j d_j x[j,k]``：只有被选中的 job 的 due date 生效。

    ``due_date=None`` 的 job 用一个大于 horizon 的等效交期，使它的迟交项恒为 0
    （与 M1「无交期视为 +∞」的约定一致）。
    """
    from ortools.linear_solver import pywraplp

    if objective not in M2_OBJECTIVES:
        raise ValueError(f"unknown objective: {objective}")
    if len(instance.machines) != 1 or not _single_operation_layout(instance):
        raise ValueError("single-machine MILP requires exactly one machine and one operation per job")
    if not instance.jobs:
        raise ValueError("instance has no job")

    jobs = tuple(job.id for job in instance.jobs)
    n = len(jobs)
    index = {job_id: position for position, job_id in enumerate(jobs)}
    processing = {
        job.id: _job_processing(instance, job.id) for job in instance.jobs
    }
    release = {job.id: job.release_time for job in instance.jobs}
    horizon = max((job.release_time for job in instance.jobs), default=0) + sum(
        processing.values()
    )
    due = {
        job.id: (horizon + 1 if job.due_date is None else job.due_date) for job in instance.jobs
    }

    solver = pywraplp.Solver.CreateSolver("CBC_MIXED_INTEGER_PROGRAMMING")
    if solver is None:
        raise RuntimeError("CBC backend unavailable")

    assign = [
        [solver.IntVar(0, 1, f"x_{j}_{k}") for k in range(n)] for j in range(n)
    ]
    for j in range(n):
        solver.Add(sum(assign[j]) == 1)
    for k in range(n):
        solver.Add(sum(assign[j][k] for j in range(n)) == 1)

    start = [solver.NumVar(0, horizon, f"S_{k}") for k in range(n)]
    completion = [solver.NumVar(0, horizon, f"C_{k}") for k in range(n)]
    tardiness = [solver.NumVar(0, horizon, f"T_{k}") for k in range(n)]
    for k in range(n):
        solver.Add(start[k] >= sum(release[jobs[j]] * assign[j][k] for j in range(n)))
        if k:
            solver.Add(start[k] >= completion[k - 1])
        solver.Add(
            completion[k] == start[k] + sum(processing[jobs[j]] * assign[j][k] for j in range(n))
        )
        solver.Add(tardiness[k] >= completion[k] - sum(due[jobs[j]] * assign[j][k] for j in range(n)))

    expression = sum(tardiness) if objective == "total_tardiness" else completion[-1]
    return MilpModelContext(
        solver=solver,
        instance=instance,
        objective=objective,
        horizon=horizon,
        jobs=jobs,
        assign=assign,
        start=start,
        completion=completion,
        tardiness=tardiness,
        expression=expression,
        variables=solver.NumVariables(),
        constraints=solver.NumConstraints(),
    )


def solve_single_machine(
    instance: Instance,
    spec: dict[str, Any],
    *,
    set_hint: bool,
    objective_cutoff: bool,
    fixed_prefix: int,
    hint_schedule: Schedule | None = None,
    method: str,
) -> SolveResult:
    """单机 MILP 求解的统一入口：初解 + 目标上界割 + 前缀固定三件事正交。

    这三件事的性质**完全不同**，必须分开报告：

    * ``set_hint``：只是把初解交给求解器**建议**（CBC ``SetHint``），
      不改变可行域、不保证被采纳，因此对结果质量没有任何保证；
    * ``objective_cutoff``：加 ``obj <= UB``，``UB`` 来自已验证可行的排程，
      是**有效不等式**，不切最优解，把「也许会用初解」变成「不会比初解差」；
    * ``fixed_prefix``：固定初解序列的前若干位置，**会**改变可行域，
      因而**会**改变最优值——它是邻域搜索，不是强化。

    三条结果都写进 ``detail``，方法名与结果一起落进批次结果表。
    """
    objective = _objective_name(spec, "total_tardiness")
    time_limit = float(spec.get("time_limit", 10.0))
    seed = int(spec.get("seed", 0) or 0)
    if objective not in M2_OBJECTIVES:
        return SolveResult(
            method=method,
            status="FAILED",
            detail={"failure_reason": f"unknown objective: {objective}"},
        )
    if len(instance.machines) != 1 or not _single_operation_layout(instance):
        return SolveResult(
            method=method,
            status="FAILED",
            detail={
                "failure_reason": "single-machine MILP requires one machine and one operation per job"
            },
        )

    started = time.perf_counter()
    try:
        context = build_single_machine_milp(instance, objective)
    except (ValueError, RuntimeError) as exc:
        return SolveResult(
            method=method,
            status="FAILED",
            detail={"failure_reason": f"{type(exc).__name__}: {exc}"},
        )
    solver = context.solver
    solver.SetTimeLimit(int(max(1, time_limit * 1000)))
    solver.SetNumThreads(1)
    if seed:
        solver.SetSolverSpecificParametersAsString(f"randomSeed {seed}")

    n = len(context.jobs)
    prefix = max(0, min(int(fixed_prefix), n))
    detail: dict[str, Any] = {
        "backend": "cbc",
        "objective_name": objective,
        "seed": seed,
        "time_limit": time_limit,
        "num_variables": context.variables,
        "num_constraints": context.constraints,
        "horizon": context.horizon,
        "fixed_prefix": prefix,
        "fixed_variables": prefix,
        "free_variables": n - prefix,
    }

    seed_rule = str(spec.get("rule", "best"))
    if hint_schedule is None:
        try:
            seed_rule, hint_schedule, seed_value, rule_values = _seed_schedule(
                instance, objective, seed_rule
            )
        except ValueError as exc:
            return SolveResult(
                method=method,
                status="FAILED",
                build_time=time.perf_counter() - started,
                detail={"failure_reason": f"{type(exc).__name__}: {exc}"},
            )
        detail["seed_rule"] = seed_rule
        detail["seed_objective"] = seed_value
        detail["rule_objectives"] = rule_values
    else:
        seed_value = _objective_value(instance, hint_schedule, objective)
        detail["seed_rule"] = seed_rule
        detail["seed_objective"] = seed_value

    sequence = _sequence_from_schedule(instance, hint_schedule)
    if set_hint:
        for position, op_index in enumerate(sequence):
            variables = context.assign[_job_index_of_op(instance, op_index)]
            solver.SetHint(variables, [1 if k == position else 0 for k in range(n)])
        # SetHint 是「建议」：CBC 不保证采纳，所以这里只记录「给过什么」，
        # 不记录「被采纳了」——后者需要求解器日志才能确认。
        detail["hint_kind"] = "MIP start via CBC SetHint (advisory, not enforced)"
        detail["hint_positions"] = n
    if prefix:
        for position, op_index in enumerate(sequence[:prefix]):
            solver.Add(context.assign[_job_index_of_op(instance, op_index)][position] == 1)
        detail["fixed_kind"] = "prefix of the seed sequence"

    if objective_cutoff:
        solver.Add(context.expression <= seed_value)
        detail["objective_cutoff"] = seed_value
        detail["cutoff_kind"] = "valid inequality obj <= seed objective"

    solver.Minimize(context.expression)
    build_time = time.perf_counter() - started
    call_started = time.perf_counter()
    status_code = solver.Solve()
    solve_time = time.perf_counter() - call_started
    detail["solver_status"] = _cbc_status(solver, status_code)
    detail["nodes"] = solver.nodes()
    detail["iterations"] = solver.iterations()
    detail["solver_wall_time"] = round(solver.WallTime(), 6)
    detail["termination_reason"] = (
        "proved optimal"
        if status_code == solver.OPTIMAL
        else f"solver returned {detail['solver_status']}"
    )

    if status_code not in (solver.OPTIMAL, solver.FEASIBLE):
        # 求解器没能给出解。如果本方法带了「上界割」，它的契约就是「不劣于初解」，
        # 此时退回初解并在 detail 里留痕，而不是把 UNKNOWN 当成结果。
        if objective_cutoff:
            detail["fallback"] = (
                f"solver returned {detail['solver_status']}; returned the seed schedule "
                "(contract: never worse than the seed)"
            )
            return _finish(
                instance,
                method,
                hint_schedule,
                objective,
                status="FEASIBLE",
                best_bound=None,
                solve_time=solve_time,
                build_time=build_time,
                iterations=solver.nodes(),
                detail=detail,
            )
        return SolveResult(
            method=method,
            status="INFEASIBLE" if status_code == solver.INFEASIBLE else "UNKNOWN",
            build_time=build_time,
            solve_time=solve_time,
            iterations=solver.nodes(),
            detail=detail,
        )

    schedule, residual = _schedule_from_milp(instance, context, solver)
    detail["max_time_round_residual"] = round(residual, 9)
    return _finish(
        instance,
        method,
        schedule,
        objective,
        status="OPTIMAL" if status_code == solver.OPTIMAL else "FEASIBLE",
        best_bound=solver.Objective().BestBound(),
        solve_time=solve_time,
        build_time=build_time,
        iterations=solver.nodes(),
        solver_objective=solver.Objective().Value(),
        detail=detail,
    )


def _cbc_status(solver: Any, status_code: int) -> str:
    return {
        solver.OPTIMAL: "OPTIMAL",
        solver.FEASIBLE: "FEASIBLE",
        solver.INFEASIBLE: "INFEASIBLE",
        solver.UNBOUNDED: "UNBOUNDED",
        solver.ABNORMAL: "ABNORMAL",
        solver.MODEL_INVALID: "MODEL_INVALID",
        solver.NOT_SOLVED: "NOT_SOLVED",
    }.get(status_code, f"code {status_code}")


def _job_index_of_op(instance: Instance, op_index: int) -> int:
    """工序下标 → job 下标（位置式 MILP 的变量按 job 编号索引）。"""
    job_id = instance.operations[op_index].job_id
    return [job.id for job in instance.jobs].index(job_id)


def _schedule_from_milp(
    instance: Instance, context: MilpModelContext, solver: Any
) -> tuple[Schedule, float]:
    """从 MILP 解里读出排程，并返回时间变量的取整残差。

    ``x[j][k]`` 给出位置 k 上是哪道 job，``S_k`` 给出该位置的开工时间。
    ``S_k`` 是**连续变量**，而 M1 的验证器要求 ``int``——取整前先记录残差，
    这是 Day 3 的 numerical scaling 检查点：残差不为 0 说明模型的时间语义和
    验证器要求的时间语义之间有缝。
    """
    n = len(context.jobs)
    machine_id = instance.machines[0].id
    layout: dict[int, int] = {}
    for j in range(n):
        for k in range(n):
            if context.assign[j][k].solution_value() > 0.5:
                layout[k] = j
    if len(layout) != n:
        raise RuntimeError(f"incomplete position assignment: {sorted(layout)}")
    residual = 0.0
    operations = []
    for k in range(n):
        job_id = context.jobs[layout[k]]
        operation = next(op for op in instance.operations if op.job_id == job_id)
        raw_start = context.start[k].solution_value()
        start_time = int(round(raw_start))
        residual = max(residual, abs(raw_start - start_time))
        operations.append(
            ScheduledOperation(
                operation_id=operation.id,
                machine_id=machine_id,
                start_time=start_time,
                end_time=start_time + operation.processing_time,
            )
        )
    return Schedule(tuple(operations)), residual


@register("milp_warmstart", "单机 MILP + M1 规则初解（MIP start）+ 目标上界割")
def milp_warmstart(instance: Instance, spec: dict[str, Any]) -> SolveResult:
    """用 M1 规则解给 CBC 一个 MIP start，并加 ``obj <= 初解值`` 的有效不等式。"""
    options = dict(spec)
    cutoff = bool(options.pop("objective_cutoff", True))
    hint = bool(options.pop("set_hint", True))
    return solve_single_machine(
        instance,
        options,
        set_hint=hint,
        objective_cutoff=cutoff,
        fixed_prefix=0,
        method="milp_warmstart",
    )


@register("milp_fixing", "单机 MILP 的 variable fixing 变体（固定初解前缀后重解）")
def milp_fixing(instance: Instance, spec: dict[str, Any]) -> SolveResult:
    """固定初解序列的前 ``fix_ratio`` 比例位置，只重解剩余部分。

    ``fix_ratio=1.0`` 时整个排列被固定，模型退化成「给定时序、求最早开工」，
    结果必须与初解**逐毫秒相同**——测试用这一点确证固定变量确实生效。
    """
    options = dict(spec)
    ratio = float(options.pop("fix_ratio", 0.5))
    if not 0.0 <= ratio <= 1.0:
        return SolveResult(
            method="milp_fixing",
            status="FAILED",
            detail={"failure_reason": f"fix_ratio out of range: {ratio}"},
        )
    cutoff = bool(options.pop("objective_cutoff", False))
    hint = bool(options.pop("set_hint", False))
    n = len(instance.jobs)
    prefix = 0 if ratio == 0 else max(1, int(math.ceil(ratio * n)))
    return solve_single_machine(
        instance,
        options,
        set_hint=hint,
        objective_cutoff=cutoff,
        fixed_prefix=prefix,
        method="milp_fixing",
    )
