"""Week 2 的三个 MILP formulation：tight / loose Big-M 与 time-indexed 替代模型。

本模块只做一件事：**把调度问题写成 MILP**，交给 CBC 求解，再把解翻译回
M1 的 ``Schedule``。计时、记录与跨方法比较属于 ``opt_experiments``；这里只
保证「模型正确」+「返回的排程能被 M1 的独立验证器接受」。

三个注册方法（名字由 ``configs/month2.json`` 引用）：

===============  ==============================================================
``milp_tight``   单机 sequence（disjunctive）模型，逐对 Big-M ``M_jk = H - r_k``
``milp_loose``   同一个模型，换成全局常量 ``M = n * H``（Big-M 单因子对照）
``milp_alt``     time-indexed 模型：``y[o][m][t] = 1`` 表示工序 o 于 t 时刻在 m 开工
===============  ==============================================================

**为什么 tight / loose 只支持单机？** 它们的 Big-M 论证依赖一条单机性质：
存在一个最优排程，其所有完工时间都不超过 ``H = max r + Σp``。这条论证在
并行机上还要叠加「选机」维度、逐对界要按机器拆分，属于 Week 3 的范围。
Week 2 故意把这两种模型锁定在单机，让 Big-M 成为**唯一**变量；并行机的通用性
交给 time-indexed 的 ``milp_alt`` —— 它的离散化天然覆盖选机。

**统一纪律**（承接 ``opt_solvers/result.py``）：

1. ``best_bound`` 只在求解器给出可比下界时填写，其余一律 ``None``；
2. ``build_time``（建模）与 ``solve_time``（求解）分开计时；
3. 求解器说 ``OPTIMAL`` 不等于解可行 —— 返回前先过 M1 的 ``schedule_errors``。
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any

from ortools.linear_solver import pywraplp

from opt_common.bridge import (
    M2_OBJECTIVES,
    Instance,
    Schedule,
    ScheduledOperation,
    schedule_errors,
    validate_instance,
)
from opt_solvers.registry import register
from opt_solvers.result import SolveResult

SOLVER_ID = "CBC_MIXED_INTEGER_PROGRAMMING"

#: 本模块注册的三个方法名，供实验脚本按固定顺序引用。
FORMULATIONS = ("milp_tight", "milp_loose", "milp_alt")

#: ``pywraplp`` 原生状态 → M2 状态词表。``UNBOUNDED`` / ``ABNORMAL`` 在调度
#: 模型里都意味着「模型或输入有问题」，映射到 ``FAILED`` 并保留求解器原始
#: 状态名，比硬塞进 ``UNKNOWN`` 更容易定位。
_STATUS_NAMES: dict[int, str] = {
    pywraplp.Solver.OPTIMAL: "OPTIMAL",
    pywraplp.Solver.FEASIBLE: "FEASIBLE",
    pywraplp.Solver.INFEASIBLE: "INFEASIBLE",
    pywraplp.Solver.UNBOUNDED: "UNBOUNDED",
    pywraplp.Solver.ABNORMAL: "ABNORMAL",
    pywraplp.Solver.NOT_SOLVED: "NOT_SOLVED",
    pywraplp.Solver.MODEL_INVALID: "MODEL_INVALID",
}

_M2_STATUS: dict[str, str] = {
    "OPTIMAL": "OPTIMAL",
    "FEASIBLE": "FEASIBLE",
    "INFEASIBLE": "INFEASIBLE",
    "UNBOUNDED": "FAILED",
    "ABNORMAL": "FAILED",
    "NOT_SOLVED": "NOT_SOLVED",
    "MODEL_INVALID": "MODEL_INVALID",
}

#: time-indexed 模型规模上限：超过就如实记 FAILED，而不是让整批卡在一个巨型模型上。
MAX_TIME_INDEXED_VARS = 400_000


class InfeasibleModelError(ValueError):
    """在**建模阶段**就能证明不可行：某道工序 ``r + p`` 超过硬截止 ``deadline``。

    这不是「求解器没找到解」，而是一个可复核的不可能性证明，所以它不该和其它
    建模错误（例如实例形状不支持）混在同一个出口。``_run`` 会把它映射成
    ``INFEASIBLE`` 而不是 ``FAILED``。
    """


# --------------------------------------------------------------------------
# 有效时间界：所有 Big-M 与变量域的共同来源
# --------------------------------------------------------------------------
def time_horizon(instance: Instance) -> int:
    """``H = max_j r_j + Σ p``：存在一个所有完工时间都不超过 H 的最优排程。

    论证：若某时刻机器空闲而仍有工序可加工，把该工序（及其同 job 的后继）
    整体提前，只会让完工时间不变或变小。因此对 ``Cmax`` / ``ΣCj`` / ``ΣwjCj``
    / ``ΣTj`` / ``Lmax`` 这些**关于完工时间单调不减**的目标，总存在一个
    「非延迟」最优排程。非延迟排程的机器空闲只会发生在「等最后一批释放」
    上，空转总量不超过 ``max_j r_j``，于是 ``C_j <= max_j r_j + Σ p = H``。

    这条界是 tight 与 loose 两种 Big-M **共同的**合法性根据。
    """
    release_max = max((job.release_time for job in instance.jobs), default=0)
    return release_max + sum(op.processing_time for op in instance.operations)


def pair_big_m(instance: Instance, horizon: int) -> dict[tuple[str, str], int]:
    """逐对 Big-M ``M_jk = H - r_k``（tight）。

    合法性：约束 ``s_k >= s_j + p_j - M_jk`` 只在 ``x_jk = 0``（即 k 先于 j）
    时被「打开」，此时它必须不切掉任何可行解，即要求
    ``M_jk >= max(s_j + p_j - s_k)``。由 ``s_j + p_j = C_j <= H`` 与
    ``s_k >= r_k`` 得 ``s_j + p_j - s_k <= H - r_k``，故 ``M_jk = H - r_k`` 合法。

    释放时间越大，这个逐对界越小 —— 这正是 tight 优于一个全局常量的来源。
    """
    release = {job.id: job.release_time for job in instance.jobs}
    return {
        (a.id, b.id): horizon - release[b.id]
        for a in instance.jobs
        for b in instance.jobs
        if a.id != b.id
    }


def loose_big_m(instance: Instance, horizon: int) -> int:
    """全局常量 ``M = n * H``（loose）：合法，但比逐对界松一个数量级。

    合法性：``n * H >= H >= H - r_k = M_jk``，即它是 tight 逐对界的上界。

    常见的 ``M = 10^6`` 这种「拍脑袋大数」**不可证明合法**：当 ``Σp`` 超过
    10^6 时它会直接切掉最优解，而且不会报错 —— 只会给一个偏高的目标值。
    本模块用一个「可证明的松」，而不是一个「不可证明的大」。
    """
    return len(instance.jobs) * horizon


# --------------------------------------------------------------------------
# 建好的模型 + 把解翻译回 Schedule 所需的信息
# --------------------------------------------------------------------------
@dataclass
class _BuiltModel:
    """一个建好但尚未求解的模型。"""

    solver: Any
    instance: Instance
    formulation: str
    objective_name: str
    relax: bool
    #: 工序 → 完工时间的线性表达式（目标函数与解码都要用）
    end_expr: dict[str, Any] = field(default_factory=dict)
    #: 工序 → [(机器 id, 指示表达式)]，解码时取指示值最大的那台
    selectors: dict[str, list[tuple[str, Any]]] = field(default_factory=dict)
    #: 建模期诊断：变量数、约束数、非零元、Big-M 取值、时间界……
    meta: dict[str, Any] = field(default_factory=dict)


def _binary(solver: Any, name: str, relax: bool) -> Any:
    """二元变量的「松紧开关」：松弛时退化成连续 ``[0, 1]``。

    这是读 root LP bound 的唯一手段 —— 变量域与约束结构都不动，只摘掉
    integrality，得到的才是**同一个模型**的 LP relaxation。
    """
    return solver.NumVar(0.0, 1.0, name) if relax else solver.BoolVar(name)


def _integer(solver: Any, lb: int, ub: int, name: str, relax: bool) -> Any:
    """整数变量的「松紧开关」：松弛时退化成连续区间。"""
    if relax:
        return solver.NumVar(float(lb), float(ub), name)
    return solver.IntVar(lb, ub, name)


# --------------------------------------------------------------------------
# 目标函数：两个 formulation 共用（只有「完工表达式」的构造不同）
# --------------------------------------------------------------------------
def _build_objective(
    built: _BuiltModel,
    completion: dict[str, Any],
    completion_terms: dict[str, int],
    *,
    upper: int,
) -> tuple[Any, int]:
    """按 M1 六个 objective 的语义拼出求解器目标（最小化），并数清非零元。

    ``completion[job_id]`` 是该 job 完工时间的线性表达式，``completion_terms``
    是它的项数（sequence 模型恒为 1，time-indexed 模型是该工序时间窗的大小）。
    ``upper`` 是完工时间的有效上界（``H`` 或更紧的 ``deadline``），用于给辅助
    变量定域。返回 ``(目标表达式, 目标相关的非零元个数)``。
    """
    solver, instance = built.solver, built.instance
    name = built.objective_name
    horizon = upper
    nonzero = 0

    if name == "makespan":
        cmax = _integer(solver, 0, horizon, "cmax", built.relax)
        for job in instance.jobs:
            solver.Add(cmax >= completion[job.id])
            nonzero += 1 + completion_terms[job.id]
        return cmax, nonzero + 1

    if name == "total_completion_time":
        return (
            solver.Sum([completion[job.id] for job in instance.jobs]),
            sum(completion_terms.values()),
        )

    if name == "total_flow_time":
        # M1 的 Σ(Cj - rj) 与 ΣCj 只差一个常数，但结果行里记录的必须是 M1 的值，
        # 所以照实把 -rj 写进求解器目标，避免「求解器目标 != 记录目标」。
        return (
            solver.Sum([completion[job.id] - job.release_time for job in instance.jobs]),
            sum(completion_terms.values()),
        )

    if name == "weighted_completion_time":
        return (
            solver.Sum([float(job.weight) * completion[job.id] for job in instance.jobs]),
            sum(completion_terms.values()),
        )

    if name == "total_tardiness":
        terms = []
        for job in instance.jobs:
            if job.due_date is None:
                continue  # 与 M1 一致：无交期 job 不参与 tardiness 目标
            late = _integer(solver, 0, horizon, f"T_{job.id}", built.relax)
            solver.Add(late >= completion[job.id] - job.due_date)
            nonzero += 1 + completion_terms[job.id]
            terms.append(late)
        if not terms:
            return 0, nonzero
        return solver.Sum(terms), nonzero + len(terms)

    if name == "max_lateness":
        due_jobs = [job for job in instance.jobs if job.due_date is not None]
        if not due_jobs:
            # M1 的 max_lateness 在「没有任何交期」时返回 0（max(..., default=0)）。
            return _integer(solver, 0, 0, "Lmax_empty", built.relax), nonzero
        lmax = _integer(solver, -horizon, horizon, "Lmax", built.relax)
        for job in due_jobs:
            solver.Add(lmax >= completion[job.id] - job.due_date)
            nonzero += 1 + completion_terms[job.id]
        return lmax, nonzero + 1

    raise ValueError(f"unsupported objective: {name}")


# --------------------------------------------------------------------------
# sequence（disjunctive）模型：单机
# --------------------------------------------------------------------------
def _require_sequence_scope(instance: Instance) -> str:
    """sequence 模型的前置检查：单机 + 每 job 一道工序。"""
    if len(instance.machines) != 1:
        raise ValueError(
            "sequence 模型只支持单机实例（并行机请用 milp_alt / cpsat 系列）"
        )
    if any(len(job.operation_ids) != 1 for job in instance.jobs):
        raise ValueError("sequence 模型只支持每 job 恰好一道工序的实例")
    return instance.machines[0].id


def build_sequence_model(
    instance: Instance,
    objective_name: str,
    *,
    tight: bool,
    relax: bool = False,
    deadline: int | None = None,
) -> _BuiltModel:
    """建单机 sequence 模型。

    变量：``s_j``（开工时间，域为 ``[r_j, H - p_j]``）与 ``x_jk``（j 是否先于 k）。
    约束：释放时间（写进变量下界）、逐对 disjunctive 约束、目标对应的时间定义。

    ``deadline`` 不为空时，额外要求**每道工序都在它之前完工**（把交期当硬约束
    而不是迟交代价）。此时变量上界由 ``H`` 与 ``deadline`` 同时收紧；一旦某个
    job 满足 ``r_j + p_j > deadline``，模型在建模阶段就已经不可能 —— 抛
    :class:`InfeasibleModelError`，由调用方映射成 ``INFEASIBLE``。
    """
    machine_id = _require_sequence_scope(instance)
    horizon = time_horizon(instance)
    latest = horizon if deadline is None else min(horizon, deadline)
    solver = pywraplp.Solver.CreateSolver(SOLVER_ID)
    if solver is None:  # pragma: no cover - 只有 OR-Tools 装配失败才会发生
        raise RuntimeError(f"cannot create solver: {SOLVER_ID}")

    op_by_job = {job.id: job.operation_ids[0] for job in instance.jobs}
    op_by_id = {op.id: op for op in instance.operations}
    pairs_m = pair_big_m(instance, horizon)
    m_loose = loose_big_m(instance, horizon)

    built = _BuiltModel(
        solver=solver,
        instance=instance,
        formulation="sequence_tight" if tight else "sequence_loose",
        objective_name=objective_name,
        relax=relax,
    )

    start: dict[str, Any] = {}
    for job in instance.jobs:
        op = op_by_id[op_by_job[job.id]]
        # 变量域同样来自有效时间界：开工不早于释放时间、完工不晚于 H 与 deadline。
        upper = latest - op.processing_time
        if upper < job.release_time:
            raise InfeasibleModelError(
                f"job {job.id} 不可能在 {latest} 前完工："
                f"r={job.release_time}, p={op.processing_time}"
            )
        start[job.id] = _integer(solver, job.release_time, upper, f"s_{job.id}", relax)
        built.end_expr[op.id] = start[job.id] + op.processing_time
        built.selectors[op.id] = [(machine_id, 1.0)]

    nonzero = 0
    pairs = 0
    for index, first in enumerate(instance.jobs):
        for second in instance.jobs[index + 1 :]:
            x = _binary(solver, f"x_{first.id}_{second.id}", relax)
            m_fs = pairs_m[(first.id, second.id)] if tight else m_loose
            m_sf = pairs_m[(second.id, first.id)] if tight else m_loose
            p_first = op_by_id[op_by_job[first.id]].processing_time
            p_second = op_by_id[op_by_job[second.id]].processing_time
            # x = 1 → second 在 first 之后；x = 0 → first 在 second 之后。
            # 两条约束的 M 各自独立：同一对 (j, k) 两个方向的释放时间不同。
            solver.Add(start[second.id] >= start[first.id] + p_first - m_fs * (1 - x))
            solver.Add(start[first.id] >= start[second.id] + p_second - m_sf * x)
            pairs += 1
            nonzero += 6  # 每条约束 3 项：两个时间变量 + 一个 M*x 项

    completion = {job.id: built.end_expr[op_by_job[job.id]] for job in instance.jobs}
    objective, objective_nonzero = _build_objective(
        built, completion, {job.id: 1 for job in instance.jobs}, upper=latest
    )
    solver.Minimize(objective)

    built.meta = {
        "machine": machine_id,
        "jobs": len(instance.jobs),
        "ordering_pairs": pairs,
        "horizon": horizon,
        "deadline": deadline,
        "big_m_mode": "pairwise_tight" if tight else "global_loose",
        "big_m_min": min(pairs_m.values()) if tight else m_loose,
        "big_m_max": max(pairs_m.values()) if tight else m_loose,
        "big_m_sum": sum(pairs_m.values()) if tight else 2 * pairs * m_loose,
        "variables": int(solver.NumVariables()),
        "constraints": int(solver.NumConstraints()),
        "binaries": 0 if relax else pairs,
        "nonzeros": nonzero + objective_nonzero,
    }
    return built


# --------------------------------------------------------------------------
# time-indexed 模型：单机与同质并行机通用
# --------------------------------------------------------------------------
def earliest_start_bounds(instance: Instance) -> dict[str, int]:
    """每道工序的最早开工：``r_job + 同 job 前置工序的总加工时间``。

    这是「有效时间界」在 time-indexed 模型里的用法：把每道工序的时间窗从
    ``[r_job, H - p]`` 收窄到 ``[r_job + 前置总加工, H - p]``，直接减少二元
    变量个数（同 job 的后道工序少掉一整段不可能的时间格点）。
    """
    op_by_id = {op.id: op for op in instance.operations}
    earliest: dict[str, int] = {}
    for job in instance.jobs:
        head = job.release_time
        for oid in job.operation_ids:
            earliest[oid] = head
            head += op_by_id[oid].processing_time
    return earliest


def build_time_indexed_model(
    instance: Instance,
    objective_name: str,
    *,
    relax: bool = False,
    deadline: int | None = None,
) -> _BuiltModel:
    """建 time-indexed 模型：``y[o][m][t] = 1`` 表示工序 o 在 t 时刻于 m 开工。

    这个模型与 sequence 模型的**变量定义完全不同**：它不显式表达「谁先谁后」，
    而是把时间切成整数格点，用「每台机器每个时刻正在加工的工序数 ≤ 1」这条
    **容量约束**隐式排除重叠。因此它天然支持并行机的选机决策（``m`` 就是第二个
    下标），也是本模块用来对照「松弛强弱」的替代 formulation。

    代价同样明显：变量数与时间界 ``H`` 成正比，``H`` 一大就爆炸。
    ``deadline`` 在这里是「时间窗上界」：它直接把不可能的时间格点剪掉，
    如果剪到某道工序的窗口为空，就抛出 :class:`InfeasibleModelError`。
    """
    horizon = time_horizon(instance)
    latest = horizon if deadline is None else min(horizon, deadline)
    earliest = earliest_start_bounds(instance)
    solver = pywraplp.Solver.CreateSolver(SOLVER_ID)
    if solver is None:  # pragma: no cover
        raise RuntimeError(f"cannot create solver: {SOLVER_ID}")

    machine_ids = [machine.id for machine in instance.machines]
    built = _BuiltModel(
        solver=solver,
        instance=instance,
        formulation="time_indexed",
        objective_name=objective_name,
        relax=relax,
    )

    for op in instance.operations:
        if latest - op.processing_time < earliest[op.id]:
            raise InfeasibleModelError(
                f"工序 {op.id} 的时间窗为空：最早开工 {earliest[op.id]}、"
                f"p={op.processing_time}，无法在 {latest} 前完工"
            )
    var_estimate = sum(
        (latest - earliest[op.id] - op.processing_time + 1)
        * len(op.eligible_machine_ids)
        for op in instance.operations
    )
    if var_estimate > MAX_TIME_INDEXED_VARS:
        raise ValueError(
            f"time-indexed 变量数估算 {var_estimate} 超过上限 "
            f"{MAX_TIME_INDEXED_VARS}（H={horizon}），请缩小子实例"
        )

    y: dict[tuple[str, str, int], Any] = {}
    start_expr: dict[str, Any] = {}
    completion_terms: dict[str, int] = {}
    nonzero = 0
    for op in instance.operations:
        window: list[tuple[str, str, int]] = []
        per_machine: dict[str, list[Any]] = {}
        for machine_id in op.eligible_machine_ids:
            per_machine[machine_id] = []
            for t in range(earliest[op.id], latest - op.processing_time + 1):
                key = (op.id, machine_id, t)
                var = _binary(solver, f"y_{op.id}_{machine_id}_{t}", relax)
                y[key] = var
                per_machine[machine_id].append(var)
                window.append(key)
        # 每道工序恰好选一个 (机器, 开工时刻)。
        solver.Add(solver.Sum([y[key] for key in window]) == 1)
        nonzero += len(window)
        start_expr[op.id] = solver.Sum([key[2] * y[key] for key in window])
        built.selectors[op.id] = [
            (machine_id, solver.Sum(per_machine[machine_id]))
            for machine_id in op.eligible_machine_ids
        ]
        built.end_expr[op.id] = start_expr[op.id] + op.processing_time

    # 容量约束：对每台机器每个时刻 tau，正在加工（含恰在 tau 开工）的工序 ≤ 1。
    for machine_id in machine_ids:
        for tau in range(latest):
            covering = [
                var
                for op in instance.operations
                if machine_id in op.eligible_machine_ids
                for t in range(max(earliest[op.id], tau - op.processing_time + 1), tau + 1)
                if (var := y.get((op.id, machine_id, t))) is not None
            ]
            if covering:
                solver.Add(solver.Sum(covering) <= 1)
                nonzero += len(covering)

    # 同一 job 内相邻工序的 precedence：后道开工 ≥ 前道完工。
    for job in instance.jobs:
        for before, after in zip(job.operation_ids, job.operation_ids[1:]):
            solver.Add(start_expr[after] >= built.end_expr[before])
            nonzero += 2 * len(
                [1 for (oid, _m, _t) in y if oid in (before, after)]
            )

    completion = {job.id: built.end_expr[job.operation_ids[-1]] for job in instance.jobs}
    for job in instance.jobs:
        last = job.operation_ids[-1]
        completion_terms[job.id] = len(
            [1 for (oid, _m, _t) in y if oid == last]
        )
    objective, objective_nonzero = _build_objective(
        built, completion, completion_terms, upper=latest
    )
    solver.Minimize(objective)

    built.meta = {
        "machines": len(instance.machines),
        "horizon": horizon,
        "deadline": deadline,
        "time_indexed_vars": var_estimate,
        "variables": int(solver.NumVariables()),
        "constraints": int(solver.NumConstraints()),
        "binaries": 0 if relax else var_estimate,
        "nonzeros": nonzero + objective_nonzero,
    }
    return built


def build_model(instance: Instance, spec: dict[str, Any]) -> _BuiltModel:
    """按 ``spec["method"]`` 分派到对应 formulation（示例脚本与测试使用）。"""
    objective_name = spec.get("objective", "makespan")
    relax = bool(spec.get("root_lp", False))
    deadline = spec.get("deadline")
    deadline = None if deadline is None else int(deadline)
    method = spec.get("method", "milp_tight")
    if method not in FORMULATIONS:
        raise ValueError(f"unknown method: {method}")
    if method == "milp_alt":
        return build_time_indexed_model(
            instance, objective_name, relax=relax, deadline=deadline
        )
    return build_sequence_model(
        instance,
        objective_name,
        tight=(method == "milp_tight"),
        relax=relax,
        deadline=deadline,
    )


# --------------------------------------------------------------------------
# 求解 → 解码 → 统一结果
# --------------------------------------------------------------------------
def _indicator_value(expr: Any) -> float:
    """指示表达式的取值：sequence 模型里是常量 1.0，time-indexed 里是变量之和。"""
    return float(expr.solution_value()) if hasattr(expr, "solution_value") else float(expr)


def _decode(built: _BuiltModel) -> Schedule:
    """把求解器返回的变量值翻译成 M1 的 ``Schedule``（只含结果字段）。"""
    operations = []
    for op in built.instance.operations:
        end = int(round(built.end_expr[op.id].solution_value()))
        machine_id = max(
            built.selectors[op.id],
            key=lambda item: (_indicator_value(item[1]), item[0]),
        )[0]
        operations.append(
            ScheduledOperation(op.id, machine_id, end - op.processing_time, end)
        )
    operations.sort(key=lambda item: (item.machine_id, item.start_time, item.operation_id))
    return Schedule(tuple(operations))


def _no_solution(
    built: _BuiltModel,
    status: str,
    build_time: float,
    solve_time: float,
    detail: dict[str, Any],
) -> SolveResult:
    """没有可用的可行解时的统一出口（``objective`` 与 ``best_bound`` 都留空）。"""
    return SolveResult(
        method=built.formulation,
        status=status,
        objective=None,
        best_bound=None,
        schedule=None,
        build_time=build_time,
        solve_time=solve_time,
        iterations=None,
        detail=detail,
    )


def _integral_schedule_if_any(built: _BuiltModel, lp_value: float) -> Schedule | None:
    """LP 最优解若本身就是整数排程、且目标值等于 LP 值，就把它作为最优性证明。"""
    if not all(
        abs(built.end_expr[op.id].solution_value() - round(built.end_expr[op.id].solution_value()))
        < 1e-6
        for op in built.instance.operations
    ):
        return None
    try:
        schedule = _decode(built)
    except (ValueError, TypeError):  # pragma: no cover - 防御性
        return None
    if schedule_errors(built.instance, schedule):
        return None
    recomputed = float(M2_OBJECTIVES[built.objective_name](built.instance, schedule))
    return schedule if abs(recomputed - lp_value) <= 1e-6 else None


def _finish(
    built: _BuiltModel, raw_status: int, build_time: float, solve_time: float
) -> SolveResult:
    """把 ``solver.Solve()`` 的原始返回包装成 ``SolveResult``。"""
    solver, instance = built.solver, built.instance
    solver_status = _STATUS_NAMES.get(raw_status, f"UNKNOWN({raw_status})")
    status = _M2_STATUS.get(solver_status, "FAILED")
    detail: dict[str, Any] = {
        "formulation": built.formulation,
        "relaxed": built.relax,
        "solver_status": solver_status,
        "solver_id": SOLVER_ID,
        **built.meta,
    }
    if status not in ("OPTIMAL", "FEASIBLE"):
        return _no_solution(built, status, build_time, solve_time, detail)

    # --- LP relaxation 诊断路径：只回答「松弛值是多少」 ---------------------
    if built.relax:
        lp_value = float(solver.Objective().Value())
        detail["lp_relaxation"] = "optimal"
        detail["simplex_iterations"] = int(solver.iterations())
        detail["iterations_kind"] = "simplex"
        integral = _integral_schedule_if_any(built, lp_value)
        if integral is not None:
            # LP 的最优解恰好是整数排程，且其目标值等于 LP 值 —— 这份 LP bound
            # 被一个真实排程达到，于是它同时是最优性证明。
            detail["lp_relaxation_integral"] = True
            return SolveResult(
                method=built.formulation,
                status="OPTIMAL",
                objective=lp_value,
                best_bound=lp_value,
                schedule=integral,
                build_time=build_time,
                solve_time=solve_time,
                iterations=None,
                detail=detail,
            )
        # 没有可行排程可交，但 LP 值是一个**有效下界**（LP 的可行域包含 MIP 的，
        # 故 LP 最优值 <= MIP 最优值）。状态记 UNKNOWN：既没找到可行解，也没
        # 证明不可行。objective 留 None —— 下界不许冒充可行解。
        detail["lp_relaxation_integral"] = False
        detail["bound_kind"] = "lp_relaxation"
        return SolveResult(
            method=built.formulation,
            status="UNKNOWN",
            objective=None,
            best_bound=lp_value,
            schedule=None,
            build_time=build_time,
            solve_time=solve_time,
            iterations=None,
            detail=detail,
        )

    # --- 正常 MIP 路径 -----------------------------------------------------
    schedule = _decode(built)
    diagnostics = schedule_errors(instance, schedule)
    if diagnostics:
        # 求解器自称有解，独立验证器却不认账：这是比 FAILED 更严重的建模错误，
        # 必须暴露，不能把不可行排程当结果交出去。
        detail["validation_errors"] = diagnostics[:5]
        detail["failure_reason"] = "returned schedule failed validate_schedule"
        return _no_solution(built, "FAILED", build_time, solve_time, detail)

    recomputed = float(M2_OBJECTIVES[built.objective_name](instance, schedule))
    solver_objective = float(solver.Objective().Value())
    best_bound = float(solver.Objective().BestBound())
    detail["solver_objective"] = solver_objective
    detail["iterations_kind"] = "branch_and_bound"

    if abs(solver_objective - recomputed) > 1e-6:
        detail["solver_objective_delta"] = round(solver_objective - recomputed, 9)
    if best_bound > recomputed + 1e-6:
        # 模型是精确的：下界不可能高于「已由独立验证器复核过的可行解目标值」。
        detail["failure_reason"] = (
            f"best_bound {best_bound} > verified objective {recomputed}"
        )
        return _no_solution(built, "FAILED", build_time, solve_time, detail)
    if best_bound > recomputed:
        # 浮点噪声级别（< 1e-6）的越界：夹到可行解目标值，避免 SolveResult 的
        # 「下界不得高于可行解」断言被一个 ULP 触发。
        best_bound = recomputed
        detail["bound_clamped"] = True

    return SolveResult(
        method=built.formulation,
        status=status,
        objective=recomputed,
        best_bound=best_bound,
        schedule=schedule,
        build_time=build_time,
        solve_time=solve_time,
        iterations=int(solver.nodes()),
        detail=detail,
    )


def _solve_built(built: _BuiltModel, time_limit: float | None, build_time: float) -> SolveResult:
    if time_limit is not None and time_limit > 0:
        built.solver.SetTimeLimit(int(time_limit * 1000))
    started = time.perf_counter()
    raw_status = built.solver.Solve()
    solve_time = time.perf_counter() - started
    return _finish(built, raw_status, build_time, solve_time)


def _failed(method: str, reason: str, **extra: Any) -> SolveResult:
    return SolveResult(method=method, status="FAILED", detail={"failure_reason": reason, **extra})


def _spec_parts(spec: dict[str, Any]) -> tuple[str, float | None, int, bool]:
    """从 ``spec`` 取出 objective / time_limit / seed / 是否只解 LP relaxation。"""
    objective_name = spec.get("objective", "makespan")
    raw_limit = spec.get("time_limit")
    time_limit = None if raw_limit is None else float(raw_limit)
    seed = int(spec.get("seed", 0) or 0)
    relax = bool(spec.get("root_lp", False))
    return objective_name, time_limit, seed, relax


def _run(instance: Instance, spec: dict[str, Any], method: str) -> SolveResult:
    """三个注册方法的公共外壳：校验 → 建模 → 求解 → 统一结果。"""
    objective_name, time_limit, seed, relax = _spec_parts(spec)
    if objective_name not in M2_OBJECTIVES:
        return _failed(method, f"unknown objective: {objective_name}")
    try:
        validate_instance(instance)
    except Exception as exc:  # noqa: BLE001 - 输入校验失败如实记录，不抛给批次
        return _failed(method, f"invalid instance: {exc}")

    started = time.perf_counter()
    try:
        built = build_model(instance, {**spec, "method": method})
    except InfeasibleModelError as exc:
        # 建模阶段的不可能性证明：这不是 FAILED，而是 INFEASIBLE。
        return SolveResult(
            method=method,
            status="INFEASIBLE",
            build_time=time.perf_counter() - started,
            detail={
                "objective": objective_name,
                "infeasibility_certificate": str(exc),
                "deadline": spec.get("deadline"),
            },
        )
    except ValueError as exc:
        return _failed(method, str(exc), objective=objective_name)
    build_time = time.perf_counter() - started
    # CBC 通过 pywraplp 不暴露随机种子（SetSolverSpecificParametersAsString 在
    # CBC 2.10 上是 no-op），如实记录 seed、并注明它对搜索**没有**影响。
    built.meta["seed"] = seed
    built.meta["seed_effective"] = False
    built.meta["time_limit"] = time_limit
    built.meta["deadline"] = spec.get("deadline")

    result = _solve_built(built, time_limit, build_time)
    return SolveResult(
        method=method,
        status=result.status,
        objective=result.objective,
        best_bound=result.best_bound,
        schedule=result.schedule,
        build_time=build_time,
        solve_time=result.solve_time,
        iterations=result.iterations,
        detail=result.detail,
    )


@register("milp_tight", "单机 sequence MILP，逐对 tight Big-M（M_jk = H - r_k）")
def milp_tight(instance: Instance, spec: dict[str, Any]) -> SolveResult:
    """tight Big-M 的单机 sequence 模型。``spec["root_lp"]=True`` 时只解 LP relaxation。"""
    return _run(instance, spec, "milp_tight")


@register("milp_loose", "单机 sequence MILP，全局 loose Big-M（M = n * H）")
def milp_loose(instance: Instance, spec: dict[str, Any]) -> SolveResult:
    """loose Big-M 的单机 sequence 模型，只有 Big-M 取法与 ``milp_tight`` 不同。"""
    return _run(instance, spec, "milp_loose")


@register("milp_alt", "time-indexed MILP，单机与同质并行机通用")
def milp_alt(instance: Instance, spec: dict[str, Any]) -> SolveResult:
    """time-indexed 替代 formulation（``y[o][m][t]``），支持并行机选机与 precedence。"""
    return _run(instance, spec, "milp_alt")


# --------------------------------------------------------------------------
# 只读工具：给实验脚本解释「模型大小」与「下界不可能低于什么」
# --------------------------------------------------------------------------
def model_stats(instance: Instance, spec: dict[str, Any]) -> dict[str, Any]:
    """构建（不求解）模型并报出规模：变量数、二元变量数、约束数、非零元数。"""
    built = build_model(instance, spec)
    stats: dict[str, Any] = {
        "method": spec.get("method", "milp_tight"),
        "formulation": built.formulation,
        "objective": spec.get("objective", "makespan"),
        "relaxed": built.relax,
    }
    stats.update(built.meta)
    return stats


def trivial_lower_bound(instance: Instance, objective_name: str) -> float | None:
    """与求解器无关的平凡下界，用于交叉检查「bound 不低于已知下界」。

    - ``makespan``：``max(max_j p_j, ceil(Σp / m))``（与 M1 的并行机下界同源）；
    - ``total_tardiness`` / ``max_lateness``：``0``；
    - 其余目标不在此函数覆盖范围内，返回 ``None`` —— 不自造下界。
    """
    if objective_name == "makespan":
        processing = [op.processing_time for op in instance.operations]
        if not processing:
            return 0.0
        return float(
            max(max(processing), math.ceil(sum(processing) / len(instance.machines)))
        )
    if objective_name in ("total_tardiness", "max_lateness"):
        return 0.0
    return None
