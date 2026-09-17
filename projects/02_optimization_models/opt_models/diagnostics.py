"""Week 4 Day 3：数值缩放体检与不可行性诊断。

本模块只做两件事，两件事都属于「求解器不替你做的事」：

1. **数值缩放体检**（:func:`scaling_report`、:func:`rescale_instance`）：
   模型里的系数量级差异有多大？用了多少 Big-M？把同一实例整体放大或缩小
   之后，最优值是否严格按比例缩放？缩放体检不求解，只读数据。
2. **不可行性诊断**（:func:`diagnose_infeasibility`）：当「所有工序都准时」
   这组 ``assumption`` 不可满足时，把 CP-SAT 给出的**充分冲突集**用删除过滤
   收缩成一个 **IIS**（不可约不可行子集），并逐条重解验证这个 IIS 真的不可行、
   而它去掉任意一个元素后都可解。

诊断能说什么、不能说什么（写在这里，也写进返回值的 ``notes``）：

* **能**：给出一组「同时成立会导致不可行」的约束，并给出该组的一个极小化版本；
* **能**：给出反例——IIS 去掉任意一条就可解，所以这组约束确实是冲突的来源；
* **不能**：``SufficientAssumptionsForInfeasibility()`` 返回的是**充分**冲突集，
  不是最小集，也不是唯一原因。它依赖求解器内部的传播痕迹，换个 ``seed`` 或
  换台机器可能给出不同的超集。所以本模块一律再做一遍删除过滤。
* **不能**：不可行可能来自**建模错误**而不是数据。求解器只会说「这组假设互斥」，
  不会说「你的模型漏了机器约束」。诊断报告必须写清假设集合的含义。
* **不能**：minimal 是「关于这组假设集合的极小」，不是「全实例的最小冲突」；
  不在假设集合里的约束（例如加工时间本身）不参与最小化。

模块复用 :mod:`opt_models.strengthening` 的 CP-SAT 模型骨架，保证「一套模型、
一种语义」，不给诊断单独造第二套变量。
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field, replace
from typing import Any

from opt_common.bridge import Instance, Schedule, schedule_errors
from opt_models.strengthening import build_parallel_model

__all__ = [
    "ConflictReport",
    "ScalingReport",
    "deadlines_with_slack",
    "diagnose_infeasibility",
    "rescale_instance",
    "scaling_report",
]

_MAX_CONTEXT = 5


# --------------------------------------------------------------------------
# 数值缩放体检
# --------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class ScalingReport:
    """系数量级体检的结论（纯数据，不涉及求解器）。"""

    jobs: int
    operations: int
    machines: int
    horizon: int
    coefficient_max: int
    coefficient_min: int
    span: float
    big_m: dict[str, float]
    tight_model_span: float
    big_m_span: float
    notes: tuple[str, ...] = ()


def rescale_instance(instance: Instance, factor: float) -> Instance:
    """把实例的时间数据整体乘 ``factor``，保持整数。

    只缩放 ``release_time`` / ``processing_time`` / ``due_date``；机器、工序、
    资格集合原样保留。``factor`` 必须让所有乘积保持整数（含浮点容差），否则抛
    ``ValueError``——CP-SAT 与 CBC 都只接受整数时间，缩放不能引入小数。
    """
    if factor <= 0:
        raise ValueError(f"factor must be positive: {factor}")

    def apply(value: int) -> int:
        product = value * factor
        rounded = round(product)
        if abs(product - rounded) > 1e-9:
            raise ValueError(f"factor {factor} turns integer data into {product}")
        return int(rounded)

    # 先整体检查一遍再构造，避免「缩放到一半才抛错」，留下半个实例。
    for job in instance.jobs:
        apply(job.release_time)
        if job.due_date is not None:
            apply(job.due_date)
    for op in instance.operations:
        apply(op.processing_time)

    new_jobs = tuple(
        replace(
            job,
            release_time=apply(job.release_time),
            due_date=None if job.due_date is None else apply(job.due_date),
        )
        for job in instance.jobs
    )
    new_operations = tuple(
        replace(op, processing_time=apply(op.processing_time)) for op in instance.operations
    )
    return Instance(new_jobs, new_operations, instance.machines)


def scaling_report(instance: Instance) -> ScalingReport:
    """体检系数量级：紧模型（无 Big-M）与 Week 2 松模型（有 Big-M）的跨度对比。

    ``span`` 定义为「模型中最大系数 / 最小非零系数」。它不直接决定求解难易，
    但跨度越大，单纯形里的比与松弛误差越容易吃掉有效数字；这也是为什么
    「上界越紧越好」在数值上不只是技巧问题。

    Week 2 的 Big-M 数值直接调用它的公开函数取得（只读，不改），如果那一周的
    模块不存在，就诚实地把该项留空，而不是编一个数。
    """
    from opt_models.strengthening import makespan_lower_bound

    horizon = _horizon(instance)
    coefficients = [op.processing_time for op in instance.operations]
    coefficients += [job.release_time for job in instance.jobs]
    coefficients += [job.due_date for job in instance.jobs if job.due_date is not None]
    coefficients.append(horizon)
    positive = [abs(value) for value in coefficients if value]
    coefficient_max = max(positive) if positive else 0
    coefficient_min = min(positive) if positive else 0
    span = float(coefficient_max) / float(coefficient_min) if coefficient_min else math.inf

    big_m: dict[str, float] = {}
    notes: list[str] = []
    try:
        from opt_models.milp_scheduling import loose_big_m, pair_big_m, time_horizon

        week2_horizon = time_horizon(instance)
        big_m["loose"] = float(loose_big_m(instance, week2_horizon))
        per_pair = pair_big_m(instance, week2_horizon)
        if per_pair:
            big_m["pair_max"] = float(max(per_pair.values()))
            big_m["pair_min"] = float(min(per_pair.values()))
        notes.append(
            "Big-M 取值来自 Week 2 的 loose_big_m / pair_big_m（只读调用），"
            "本模块自己的模型不使用 Big-M。"
        )
    except Exception as exc:  # pragma: no cover - 依赖其它周模块是否存在
        notes.append(f"未取到 Week 2 的 Big-M 数值：{type(exc).__name__}: {exc}")

    big_m_span = (
        float(max(big_m.values())) / float(coefficient_min)
        if big_m and coefficient_min
        else math.inf
    )
    notes.append(
        "紧模型的最大系数是 horizon，因此 span = horizon / min p；"
        "松模型的最大系数是 Big-M，量级通常高出一到两个数量级。"
    )
    notes.append(
        f"解析下界（makespan）为 {makespan_lower_bound(instance)}，"
        "把上界收紧到接近最优值可以同时改善数值与传播。"
    )
    return ScalingReport(
        jobs=len(instance.jobs),
        operations=len(instance.operations),
        machines=len(instance.machines),
        horizon=horizon,
        coefficient_max=coefficient_max,
        coefficient_min=coefficient_min,
        span=span,
        big_m=big_m,
        tight_model_span=span,
        big_m_span=big_m_span,
        notes=tuple(notes),
    )


def _horizon(instance: Instance) -> int:
    """与 CP-SAT 骨架一致的合法上界：最晚释放时间 + 全部加工时间之和。"""
    total = sum(op.processing_time for op in instance.operations)
    latest = max((job.release_time for job in instance.jobs), default=0)
    return latest + total


# --------------------------------------------------------------------------
# 不可行性诊断
# --------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class ConflictReport:
    """不可行诊断报告：可序列化，不含任何求解器对象。"""

    feasible: bool
    status: str
    objective_name: str
    deadlines: dict[str, int]
    assumed_jobs: tuple[str, ...]
    reported_conflict: tuple[str, ...]
    minimal_conflict: tuple[str, ...]
    reduction_steps: int
    verification: dict[str, Any]
    solves: int
    time_limit: float
    seed: int
    solver_wall_time: float
    schedule: Schedule | None = None
    notes: tuple[str, ...] = ()
    detail: dict[str, Any] = field(default_factory=dict)

    def summary(self) -> str:
        """一行结论，方便示例脚本直接打印。"""
        if self.feasible:
            return f"FEASIBLE: 所有工序都可准时 ({len(self.assumed_jobs)} 个假设同时成立)"
        return (
            f"INFEASIBLE: 充分冲突集 {len(self.reported_conflict)} 个 → "
            f"极小冲突集 {len(self.minimal_conflict)} 个 {list(self.minimal_conflict)}"
        )


def deadlines_with_slack(instance: Instance, slack: float) -> dict[str, int]:
    """按 ``d_j = r_j + ceil(slack * p_j)`` 造一组交期；``slack < 1`` 必然很紧。

    这是诊断实验的「可控旋钮」：``slack`` 越小越容易不可行，但不可行的**原因**
    仍需由求解器诊断给出，不由调用方假定。
    """
    if slack <= 0:
        raise ValueError(f"slack must be positive: {slack}")
    deadlines: dict[str, int] = {}
    for job in instance.jobs:
        processing = sum(
            op.processing_time for op in instance.operations if op.job_id == job.id
        )
        deadlines[job.id] = job.release_time + int(math.ceil(slack * processing))
    return deadlines


def diagnose_infeasibility(
    instance: Instance,
    deadlines: dict[str, int] | None = None,
    *,
    time_limit: float = 5.0,
    seed: int = 0,
    reduce_conflict: bool = True,
) -> ConflictReport:
    """诊断「所有工序都在交期前完工」这组 ``assumption`` 的可行性。

    流程：

    1. 每个作业一个布尔 ``on_time_j``，并用 ``AddAssumption(on_time_j)`` 强制
       它在本次求解中为真；``on_time_j`` 为真时 ``C_j <= d_j``。
    2. 求解。可行 → 返回排程（并过独立验证器）；不可行 → 进入第 3 步。
    3. 取 ``SufficientAssumptionsForInfeasibility()`` 作为**充分**冲突集。
    4. ``reduce_conflict=True`` 时做删除过滤：从冲突集里逐个尝试去掉一个作业，
       若去掉后仍不可行，说明该作业不必要，永久移除。得到一个 IIS。
    5. 验证：IIS 单独求解必须不可行；IIS 去掉任一元素必须可解。
    """
    from ortools.sat.python import cp_model

    if deadlines is None:
        if any(job.due_date is None for job in instance.jobs):
            raise ValueError("instance has jobs without due_date; pass deadlines explicitly")
        deadlines = {job.id: int(job.due_date) for job in instance.jobs}

    assumed = tuple(job.id for job in instance.jobs if job.id in deadlines)
    base_notes = (
        "SufficientAssumptionsForInfeasibility() 只保证「充分」，不保证最小、"
        "也不保证唯一；换 seed 或换设备可能给出不同的超集。",
        "不可行可能来自建模错误而不是数据；求解器不会替你区分这两者。",
        "IIS 是「关于这组假设集合的极小」，不在假设集合里的约束不参与最小化。",
    )

    for job in instance.jobs:
        if job.id not in deadlines:
            return ConflictReport(
                feasible=False,
                status="FAILED",
                objective_name="makespan",
                deadlines=dict(deadlines),
                assumed_jobs=assumed,
                reported_conflict=(),
                minimal_conflict=(),
                reduction_steps=0,
                verification={},
                solves=0,
                time_limit=time_limit,
                seed=seed,
                solver_wall_time=0.0,
                notes=base_notes,
                detail={"failure_reason": f"job {job.id} has no deadline in the assumption set"},
            )

    solves = 0
    wall = 0.0

    def solve_with(job_ids: tuple[str, ...]) -> tuple[str, list[str], float, Any]:
        """在假设集合 ``job_ids`` 上求解，返回 (状态名, 充分冲突集的作业名, 用时, 排程)。"""
        nonlocal solves, wall
        context = build_parallel_model(instance, "makespan")
        model = context.model
        literals = {}
        for job_id in job_ids:
            literal = model.NewBoolVar(f"on_time_{job_id}")
            for op in instance.operations:
                if op.job_id != job_id:
                    continue
                model.Add(context.end_of_operation[op.id] <= int(deadlines[job_id])).OnlyEnforceIf(
                    literal
                )
            literals[job_id] = literal
            model.AddAssumption(literal)
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = max(0.001, time_limit)
        solver.parameters.random_seed = seed
        solver.parameters.num_search_workers = 1
        started = time.perf_counter()
        status_code = solver.Solve(model)
        elapsed = time.perf_counter() - started
        solves += 1
        wall += elapsed
        status_name = solver.StatusName(status_code)
        conflict: list[str] = []
        if status_name == "INFEASIBLE":
            index_to_job = {literal.Index(): job_id for job_id, literal in literals.items()}
            for literal_index in solver.SufficientAssumptionsForInfeasibility():
                job_id = index_to_job.get(literal_index)
                if job_id is None:
                    conflict.append(f"unknown_literal_{literal_index}")
                elif job_id not in conflict:
                    conflict.append(job_id)
        schedule = None
        if status_name in ("OPTIMAL", "FEASIBLE"):
            from opt_common.bridge import ScheduledOperation

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
        return status_name, conflict, elapsed, schedule

    status_name, reported, first_elapsed, schedule = solve_with(assumed)
    detail: dict[str, Any] = {
        "assumption_kind": "on_time_j 为真时 C_j <= d_j",
        "assumed_count": len(assumed),
    }

    if status_name in ("OPTIMAL", "FEASIBLE"):
        if schedule is not None:
            errors = schedule_errors(instance, schedule)
            if errors:
                detail["validation_errors"] = errors[:_MAX_CONTEXT]
                return ConflictReport(
                    feasible=False,
                    status="FAILED",
                    objective_name="makespan",
                    deadlines=dict(deadlines),
                    assumed_jobs=assumed,
                    reported_conflict=(),
                    minimal_conflict=(),
                    reduction_steps=0,
                    verification={},
                    solves=solves,
                    time_limit=time_limit,
                    seed=seed,
                    solver_wall_time=wall,
                    notes=base_notes,
                    detail={**detail, "failure_reason": "independent validator rejected schedule"},
                )
        detail["on_time_all"] = True
        return ConflictReport(
            feasible=True,
            status="FEASIBLE",
            objective_name="makespan",
            deadlines=dict(deadlines),
            assumed_jobs=assumed,
            reported_conflict=(),
            minimal_conflict=(),
            reduction_steps=0,
            verification={},
            solves=solves,
            time_limit=time_limit,
            seed=seed,
            solver_wall_time=wall,
            schedule=schedule,
            notes=base_notes,
            detail=detail,
        )

    if status_name != "INFEASIBLE":
        return ConflictReport(
            feasible=False,
            status="UNKNOWN",
            objective_name="makespan",
            deadlines=dict(deadlines),
            assumed_jobs=assumed,
            reported_conflict=tuple(reported),
            minimal_conflict=(),
            reduction_steps=0,
            verification={},
            solves=solves,
            time_limit=time_limit,
            seed=seed,
            solver_wall_time=wall,
            notes=base_notes,
            detail={
                **detail,
                "failure_reason": f"solver returned {status_name}: 连「哪组约束冲突」都还不能断言",
            },
        )

    reported = tuple(job_id for job_id in reported if job_id in assumed)
    if not reported:
        # 冲突集为空说明不可行并非来自这批假设（例如模型自身就不可行）。
        return ConflictReport(
            feasible=False,
            status="INFEASIBLE",
            objective_name="makespan",
            deadlines=dict(deadlines),
            assumed_jobs=assumed,
            reported_conflict=(),
            minimal_conflict=(),
            reduction_steps=0,
            verification={"assumptions_blamed": False},
            solves=solves,
            time_limit=time_limit,
            seed=seed,
            solver_wall_time=wall,
            notes=base_notes,
            detail={
                **detail,
                "failure_reason": (
                    "solver returned INFEASIBLE but blamed no assumption: "
                    "不可行与这批假设无关，先检查模型本身"
                ),
            },
        )

    detail["reported_conflict_size"] = len(reported)
    detail["first_solve_seconds"] = round(first_elapsed, 6)

    minimal = list(reported)
    steps = 0
    if reduce_conflict:
        cursor = 0
        while cursor < len(minimal):
            trial = tuple(job_id for job_id in minimal if job_id != minimal[cursor])
            trial_status, _, _, _ = solve_with(trial)
            steps += 1
            if trial_status == "INFEASIBLE":
                # 去掉它仍然不可行 → 它在冲突中不必要，永久移除。
                minimal = [job_id for job_id in minimal if job_id != minimal[cursor]]
            else:
                cursor += 1

    verification: dict[str, Any] = {}
    if minimal:
        iis_status, _, _, _ = solve_with(tuple(minimal))
        verification["minimal_conflict_status"] = iis_status
        drop_one: dict[str, str] = {}
        for job_id in minimal:
            subset = tuple(other for other in minimal if other != job_id)
            subset_status, _, _, _ = solve_with(subset)
            drop_one[job_id] = subset_status
        verification["drop_one_status"] = drop_one
        verification["irreducible"] = all(
            value in ("OPTIMAL", "FEASIBLE") for value in drop_one.values()
        )
        verification["still_infeasible"] = iis_status == "INFEASIBLE"
    else:
        verification["irreducible"] = False
        verification["still_infeasible"] = False

    detail["verification_solves"] = solves
    detail["reduction_steps"] = steps
    notes = base_notes + (
        "验证结果里 irreducible 为真表示：IIS 去掉任意一个作业后都变得可解，"
        "所以这组作业确实是冲突的来源。",
    )
    return ConflictReport(
        feasible=False,
        status="INFEASIBLE",
        objective_name="makespan",
        deadlines=dict(deadlines),
        assumed_jobs=assumed,
        reported_conflict=reported,
        minimal_conflict=tuple(minimal),
        reduction_steps=steps,
        verification=verification,
        solves=solves,
        time_limit=time_limit,
        seed=seed,
        solver_wall_time=wall,
        notes=notes,
        detail=detail,
    )
