"""JSP 的两个方法：优先级派工（启发式）与 CP-SAT（精确模型）。

两者回答同一个问题，但证据等级完全不同 —— 这是本模块最需要记住的一句话：

```text
jsp_priority  非延迟列表调度（non-delay list scheduling）
              任取一条优先级规则，每步把「最早能开工」的工序里优先级最高的排进去。
              **启发式**：best_bound 恒为 None，绝没有最优性保证。

jsp_cpsat     CP-SAT 模型：每道工序一个区间变量，同机器 AddNoOverlap，
              同订单前后工序加 precedence。**精确**：求解器能给出下界与 gap，
              因此 best_bound 取自求解器，而不是目标值。
```

**非延迟（non-delay）是什么意思？** 只要某台机器空闲、且有工序能开工，就立刻开工。
它的好处是简单、确定、且结果一定是左移的（每道工序都在最早时刻开工），于是
Day 3 的析取图最长路径定理可以直接套上去复核。

**两条共同的纪律**（与 M1/M2 一脉相承）：

1. 求解器说可行不算数，返回的排程必须过 ``fjsp_core.schedule_validation``；
2. 目标值由 ``fjsp_core.objective`` 独立重算，不采信求解器的自报值。

**适用范围闸门**：本模块只表达 Week 1 的两条约束（工艺路线、机器互斥）。实例若带
日历、维护窗、次生资源或换型矩阵，方法会**返回 FAILED 并说明理由**，而不是给出一个
会被独立验证器拒绝的解。那些约束属于 Week 3 / Week 4。
"""
from __future__ import annotations

import time
from typing import Any

from ortools.sat.python import cp_model

from fjsp_core.models import FJSPInstance, Schedule, ScheduledOperation
from fjsp_core.objective import objective_breakdown, parse_weights
from fjsp_core.result import ShopResult
from fjsp_core.schedule_validation import schedule_errors
from fjsp_shop.flowshop import failure_result, feasible_result, spec_float
from fjsp_shop.graph import left_shift_schedule
from fjsp_shop.registry import register

DEFAULT_TIME_LIMIT = 15.0

#: 优先级规则。键越小优先级越高，平局一律按 ``operation.id`` 升序决胜。
PRIORITY_RULES = ("mwr", "mopnr", "spt", "lpt", "fifo")

#: 本模块能忠实表达的约束集合。之外的约束一律走 FAILED，不猜。
_UNSUPPORTED = (
    ("calendars", "机器日历"),
    ("maintenances", "计划维护窗"),
    ("workers", "次生资源"),
    ("setups", "sequence-dependent 换型矩阵"),
)


def unsupported_reasons(instance: FJSPInstance) -> list[str]:
    """列出实例里本模块不表达的约束（空列表 = 在能力范围内）。"""
    reasons: list[str] = []
    for attribute, label in _UNSUPPORTED:
        if getattr(instance, attribute):
            reasons.append(label)
    if any(machine.calendar_id is not None for machine in instance.machines):
        reasons.append("机器日历")
    return reasons


def _priority_key(
    rule: str,
    operation,
    *,
    remaining_work: dict[str, int],
    remaining_ops: dict[str, int],
    job_index: dict[str, int],
) -> int:
    if rule == "mwr":  # 剩余总工时最多的订单优先
        return -remaining_work[operation.job_id]
    if rule == "mopnr":  # 剩余工序数最多的订单优先
        return -remaining_ops[operation.job_id]
    if rule == "spt":
        return operation.min_time
    if rule == "lpt":
        return -operation.min_time
    if rule == "fifo":
        return job_index[operation.job_id]
    raise ValueError(f"unknown priority rule: {rule!r}")


def _non_delay_schedule(instance: FJSPInstance, rule: str) -> tuple[Schedule, dict[str, Any]]:
    """事件驱动的非延迟列表调度：每步只让「最早能开工」的工序参选。

    ```text
    state       machine_ready[m]（机器何时空）+ 已排工序（决定前驱是否完工）
    decision    在 est(op) 最小的那批工序里，按优先级规则挑一个，并在其合格机器里
                选完工最早的（平局按 machine.id）
    transition  把该机器推进到该工序完工；订单剩余工时相应减少
    ```
    """
    by_id = {operation.id: operation for operation in instance.operations}
    operations_of = {
        job.id: [by_id[oid] for oid in job.operation_ids] for job in instance.jobs
    }
    job_index = {job.id: index for index, job in enumerate(instance.jobs)}
    machine_ready = {machine_id: 0 for machine_id in instance.machine_ids}
    scheduled: dict[str, ScheduledOperation] = {}
    pending = set(by_id)
    remaining_work = {
        job.id: sum(operation.min_time for operation in operations_of[job.id])
        for job in instance.jobs
    }
    remaining_ops = {job.id: len(operations_of[job.id]) for job in instance.jobs}
    steps: list[dict[str, Any]] = []

    while pending:
        candidates: list[tuple[int, Any, str]] = []
        for operation_id in sorted(pending):
            operation = by_id[operation_id]
            route = operations_of[operation.job_id]
            if operation.position == 0:
                floor = instance.job(operation.job_id).release_time
            else:
                predecessor = route[operation.position - 1]
                if predecessor.id not in scheduled:
                    continue
                floor = scheduled[predecessor.id].end_time
            if operation.locked_start is not None:
                machine_id = operation.locked_machine_id or operation.eligible_machine_ids[0]
                if machine_ready[machine_id] > operation.locked_start:
                    raise ValueError(
                        f"工序 {operation.id!r} 锁定开工于 {operation.locked_start}，"
                        f"但机器 {machine_id!r} 到 {machine_ready[machine_id]} 才空"
                    )
                candidates.append((operation.locked_start, operation, machine_id))
                continue
            best: tuple[int, str] | None = None
            for machine_id, _ in operation.machine_times:
                if (
                    operation.locked_machine_id is not None
                    and machine_id != operation.locked_machine_id
                ):
                    continue
                start = max(machine_ready[machine_id], floor)
                if best is None or (start, machine_id) < best:
                    best = (start, machine_id)
            if best is None:  # pragma: no cover - 输入校验已保证至少一台合格机器
                raise ValueError(f"工序 {operation.id!r} 没有可用机器")
            candidates.append((best[0], operation, best[1]))

        if not candidates:  # pragma: no cover - 输入校验保证无环工艺路线
            raise ValueError("调度卡住：剩余工序的前驱永远无法完成")

        earliest = min(start for start, _, _ in candidates)
        now = [
            (operation, machine_id)
            for start, operation, machine_id in candidates
            if start == earliest
        ]
        operation, machine_id = min(
            now,
            key=lambda pair: (
                _priority_key(
                    rule,
                    pair[0],
                    remaining_work=remaining_work,
                    remaining_ops=remaining_ops,
                    job_index=job_index,
                ),
                pair[0].id,
            ),
        )
        duration = operation.time_on(machine_id)
        assert duration is not None  # 由 machine_times 保证
        end = earliest + duration
        scheduled[operation.id] = ScheduledOperation(
            operation.id, machine_id, earliest, end
        )
        machine_ready[machine_id] = end
        pending.discard(operation.id)
        remaining_work[operation.job_id] -= operation.min_time
        remaining_ops[operation.job_id] -= 1
        steps.append(
            {
                "operation": operation.id,
                "machine": machine_id,
                "start": earliest,
                "end": end,
                "candidates": len(now),
            }
        )

    schedule = Schedule(
        tuple(scheduled[operation.id] for operation in instance.operations)
    )
    return schedule, {"steps": steps, "priority_rule": rule}


@register("jsp_priority", "JSP 非延迟优先级派工（启发式；最优先剩余工时，平局按工序 id）")
def jsp_priority(instance: FJSPInstance, spec: dict[str, Any]) -> ShopResult:
    """非延迟列表调度。启发式，**不提供下界**。

    ``spec["priority"]`` 可选 ``mwr`` / ``mopnr`` / ``spt`` / ``lpt`` / ``fifo``，
    缺省 ``mwr``（剩余总工时最多者先做）。选机口径是「合格机器里完工最早的」，
    因此它同时处理了 FJSP 的机器选择 —— 但真实 FJSP 的建模是 Week 2 的内容。
    """
    started = time.perf_counter()
    reasons = unsupported_reasons(instance)
    if reasons:
        return failure_result(
            "jsp_priority",
            "实例带本方法不表达的约束：" + "、".join(sorted(set(reasons))),
            stage="applicability",
        )
    rule = str(spec.get("priority", "mwr"))
    if rule not in PRIORITY_RULES:
        return failure_result(
            "jsp_priority",
            f"unknown priority rule: {rule!r}（可选 {list(PRIORITY_RULES)}）",
            stage="spec",
        )
    try:
        schedule, extra = _non_delay_schedule(instance, rule)
    except ValueError as exc:
        return failure_result("jsp_priority", f"ValueError: {exc}", stage="schedule")

    solve_time = time.perf_counter() - started
    detail = {
        "priority_rule": rule,
        "priority_rules_available": list(PRIORITY_RULES),
        "non_delay": True,
        "scheduled_operations": len(schedule.operations),
        "decision_points": len(extra["steps"]),
        "optimality_certificate": "",
        "optimality_note": "列表调度是启发式：没有任何最优性保证，也不提供下界",
        "has_bound": False,
    }
    return feasible_result(
        "jsp_priority", instance, spec, schedule, solve_time=solve_time, detail=detail
    )


# ---------------------------------------------------------------------------
# CP-SAT 模型
# ---------------------------------------------------------------------------

_CP_STATUS = {
    cp_model.OPTIMAL: "OPTIMAL",
    cp_model.FEASIBLE: "FEASIBLE",
    cp_model.INFEASIBLE: "INFEASIBLE",
    cp_model.UNKNOWN: "UNKNOWN",
    cp_model.MODEL_INVALID: "MODEL_INVALID",
}


def _horizon(instance: FJSPInstance) -> int:
    """时间上界：最大释放时间 + 所有工序取最慢机器时的工时之和。够松但必然合法。"""
    release = max((job.release_time for job in instance.jobs), default=0)
    worst = sum(max(time for _, time in operation.machine_times)
                for operation in instance.operations if operation.machine_times)
    return max(1, release + worst)


def build_jsp_model(instance: FJSPInstance) -> tuple[cp_model.CpModel, dict[str, Any]]:
    """建 JSP 模型：区间 + ``AddNoOverlap`` + precedence。

    变量与约束一一对应三件事，没有隐藏的第四件：

    ```text
    每道工序   一个 start 变量 + 每台合格机器一个 end 变量（end = start + p_ij）
               单合格机器 -> 必选区间；多合格机器 -> 可选区间 + ExactlyOne
    每台机器   AddNoOverlap(该机器上的全部区间)         —— 机器同一时刻只做一件事
    每个订单   start(后道) >= end(前道)                 —— 工艺路线
    目标       makespan = max(所有工序的 end)，Minimize
    ```
    """
    horizon = _horizon(instance)
    model = cp_model.CpModel()
    intervals: dict[str, list[Any]] = {machine_id: [] for machine_id in instance.machine_ids}
    start_vars: dict[str, Any] = {}
    end_vars: dict[str, Any] = {}
    choices: dict[str, dict[str, Any]] = {}

    for operation in instance.operations:
        release = instance.job(operation.job_id).release_time
        lower = release
        if operation.locked_start is not None:
            lower = operation.locked_start
        start = model.NewIntVar(lower, horizon, f"start_{operation.id}")
        end_used = model.NewIntVar(lower, horizon, f"end_{operation.id}")
        if operation.locked_start is not None:
            model.Add(start == operation.locked_start)

        eligible = [
            (machine_id, duration)
            for machine_id, duration in operation.machine_times
            if operation.locked_machine_id in (None, machine_id)
        ]
        if not eligible:  # pragma: no cover - 输入校验保证锁定机器必须合格
            raise ValueError(f"工序 {operation.id!r} 在锁定机器上没有工时")
        operation_choices: dict[str, Any] = {}
        literals = []
        for machine_id, duration in eligible:
            end = model.NewIntVar(0, horizon, f"end_{operation.id}_{machine_id}")
            model.Add(end == start + duration)
            if len(eligible) == 1:
                interval = model.NewIntervalVar(
                    start, duration, end, f"iv_{operation.id}_{machine_id}"
                )
                model.Add(end_used == end)
                literal = None
            else:
                literal = model.NewBoolVar(f"use_{operation.id}_{machine_id}")
                interval = model.NewOptionalIntervalVar(
                    start, duration, end, literal, f"iv_{operation.id}_{machine_id}"
                )
                model.Add(end_used == end).OnlyEnforceIf(literal)
                literals.append(literal)
            intervals[machine_id].append(interval)
            operation_choices[machine_id] = {"end": end, "literal": literal, "duration": duration}
        if literals:
            model.AddExactlyOne(literals)
        start_vars[operation.id] = start
        end_vars[operation.id] = end_used
        choices[operation.id] = operation_choices

    for job in instance.jobs:
        for before, after in zip(job.operation_ids, job.operation_ids[1:]):
            model.Add(start_vars[after] >= end_vars[before])

    for machine_id, machine_intervals in intervals.items():
        if machine_intervals:
            model.AddNoOverlap(machine_intervals)

    makespan = model.NewIntVar(0, horizon, "makespan")
    model.AddMaxEquality(makespan, list(end_vars.values()))
    model.Minimize(makespan)

    built = {
        "horizon": horizon,
        "interval_count": sum(len(value) for value in intervals.values()),
        "start_vars": start_vars,
        "end_vars": end_vars,
        "choices": choices,
        "makespan_var": makespan,
        "model": model,
    }
    return model, built


@register("jsp_cpsat", "CP-SAT 精确 JSP：区间 + 每机器 NoOverlap + 工艺路线 precedence")
def jsp_cpsat(instance: FJSPInstance, spec: dict[str, Any]) -> ShopResult:
    """CP-SAT 建模求解。**精确**：界来自求解器，不由目标值冒充。

    返回前会做两件独立复核：

    1. 排程过 ``fjsp_core.schedule_validation``（求解器说可行不算数）；
    2. 能做左移归一化时做一次，让 Day 3 的析取图最长路径定理能直接套用；
       规范化后**再验证一次**，不通过就退回原解并把诊断写进 ``detail``。
    """
    started = time.perf_counter()
    objective_name = spec.get("objective", "makespan")
    if objective_name not in (
        "makespan",
        "total_tardiness",
        "weighted_tardiness",
        "total_setup_time",
        "weighted_sum",
    ):
        return failure_result(
            "jsp_cpsat", f"unknown objective: {objective_name!r}", stage="spec"
        )
    reasons = unsupported_reasons(instance)
    if reasons:
        return failure_result(
            "jsp_cpsat",
            "实例带本模型不表达的约束：" + "、".join(sorted(set(reasons))),
            stage="applicability",
        )

    try:
        model, built = build_jsp_model(instance)
    except ValueError as exc:
        return failure_result("jsp_cpsat", f"ValueError: {exc}", stage="build")
    build_time = time.perf_counter() - started

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = spec_float(spec, "time_limit", DEFAULT_TIME_LIMIT)
    solver.parameters.num_search_workers = 1  # 单线程：让随机种子真的可复现
    solver.parameters.random_seed = int(spec.get("seed", 0) or 0)
    solved_at = time.perf_counter()
    status = solver.Solve(model)
    solve_time = time.perf_counter() - solved_at

    detail: dict[str, Any] = {
        "cp_status": {
            cp_model.OPTIMAL: "OPTIMAL",
            cp_model.FEASIBLE: "FEASIBLE",
            cp_model.INFEASIBLE: "INFEASIBLE",
            cp_model.UNKNOWN: "UNKNOWN",
            cp_model.MODEL_INVALID: "MODEL_INVALID",
        }[status],
        "horizon": built["horizon"],
        "interval_count": built["interval_count"],
        "time_limit": solver.parameters.max_time_in_seconds,
        "num_search_workers": 1,
        "random_seed": solver.parameters.random_seed,
        "conflicts": int(solver.NumConflicts()),
        "branches": int(solver.NumBranches()),
        "booleans": int(solver.NumBooleans()),
        "cp_wall_time": float(solver.WallTime()),
        "model_objective": "makespan",
        "bound_kind": "solver_objective_bound",
    }

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        detail["raw_best_bound"] = float(solver.BestObjectiveBound())
        detail["failure_reason"] = f"CP-SAT status {detail['cp_status']}"
        return ShopResult(
            method="jsp_cpsat",
            status=_CP_STATUS[status],
            build_time=build_time,
            solve_time=solve_time,
            iterations=int(solver.NumBranches()),
            detail=detail,
        )

    schedule = _read_schedule(solver, instance, built)
    diagnostics = schedule_errors(instance, schedule)
    if diagnostics:
        detail["failure_reason"] = (
            f"independent validator rejected the schedule: {diagnostics[:3]}"
        )
        return ShopResult(
            method="jsp_cpsat",
            status="FAILED",
            build_time=build_time,
            solve_time=solve_time,
            iterations=int(solver.NumBranches()),
            detail=detail,
        )

    detail["validator_diagnostics"] = []
    detail["left_shifted"] = False
    try:
        shifted = left_shift_schedule(instance, schedule)
    except ValueError as exc:
        detail["left_shift_skipped"] = str(exc)
    else:
        shifted_diagnostics = schedule_errors(instance, shifted)
        if shifted_diagnostics:  # pragma: no cover - 左移的可行性由弧的语义保证
            detail["left_shift_reverted"] = shifted_diagnostics[:3]
        else:
            detail["left_shifted"] = True
            schedule = shifted

    weights = parse_weights(spec)
    from fjsp_core.objective import evaluate

    objective = float(evaluate(instance, schedule, objective_name, weights))
    detail["cp_objective"] = float(solver.ObjectiveValue())
    detail["cp_objective_matches"] = abs(detail["cp_objective"] - objective) < 1e-6

    best_bound: float | None = None
    raw_bound = float(solver.BestObjectiveBound())
    detail["raw_best_bound"] = raw_bound
    if objective_name != "makespan":
        # 求解器给的是 makespan 的界，不能冒充别的目标的界
        detail["bound_kind"] = "not_reported_for_this_objective"
    elif raw_bound <= objective + 1e-6:
        best_bound = min(raw_bound, objective)
    else:  # pragma: no cover - 数学上不可能（界不会高于可行解）
        detail["bound_anomaly"] = raw_bound

    return ShopResult(
        method="jsp_cpsat",
        status=_CP_STATUS[status],
        schedule=schedule,
        objective=objective,
        best_bound=best_bound,
        build_time=build_time,
        solve_time=solve_time,
        iterations=int(solver.NumBranches()),
        breakdown=objective_breakdown(instance, schedule),
        detail=detail,
    )


def _read_schedule(solver: cp_model.CpSolver, instance: FJSPInstance, built: dict) -> Schedule:
    """从求解器读数里还原排程。机器选择由「哪个可选区间被选中」决定。"""
    scheduled: list[ScheduledOperation] = []
    for operation in instance.operations:
        machine_choices = built["choices"][operation.id]
        if len(machine_choices) == 1:
            machine_id = next(iter(machine_choices))
        else:
            machine_id = next(
                candidate
                for candidate, entry in machine_choices.items()
                if solver.Value(entry["literal"]) == 1
            )
        entry = machine_choices[machine_id]
        start = int(solver.Value(built["start_vars"][operation.id]))
        end = int(solver.Value(entry["end"]))
        scheduled.append(ScheduledOperation(operation.id, machine_id, start, end))
    return Schedule(tuple(scheduled))
