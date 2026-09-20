"""Flow Shop 基线：Johnson 规则（精确，但只对两台机器）与 NEH（启发式，任意台数）。

三个必须分清的概念，混起来就会写出「NEH 最优」这种错话：

```text
F2||Cmax   两台机器的 flow shop  —— Johnson 规则给出**最优**排列，多项式时间
Fm||Cmax   m>=3 台机器的 flow shop —— NP-hard，没有多项式精确算法
NEH        m 台机器上的**启发式** —— 有很好的实测表现，但**没有最优性保证**
```

**Johnson 规则为什么只对两台机器成立？** 它的推导依赖「一台机器上的相邻两道工序
交换后，只有这两道工序的完工时间受影响」这个局部性argument —— 在第三台机器上，
交换还会把影响继续传播下去，局部性就没了。所以本模块的行为是：

* 机器数为 2：在整条工艺路线上直接应用 Johnson 规则，``status = OPTIMAL``
  （前提：所有订单释放时间为 0，否则按 FEASIBLE 处理并在 ``detail`` 说明）；
* 机器数 >= 3：**不假装 Johnson 还能用**，退化为「在工时负载最大的两台机器上
  应用 Johnson 规则」，把得到的排列解码到完整的 m 台机器上，状态记 FEASIBLE，
  并在 ``detail["applicability"]`` 里写清楚用的是哪一种；
* 不是 flow shop（各订单机器序列不同、或某道工序有多台合格机器、或路线有回流）：
  **直接返回 FAILED 并给出理由**，绝不静默地给一个坏答案。

本模块同时提供另外两个方法也要用的结果构造纪律（``failure_result`` /
``feasible_result`` / ``spec_float``）：四个方法说的是同一种话，这些细节只写一遍
比复制四遍更不容易走样。
"""
from __future__ import annotations

from typing import Any

from fjsp_core.models import FJSPInstance, Schedule, ScheduledOperation
from fjsp_core.objective import (
    objective_breakdown,
    parse_weights,
    evaluate as evaluate_objective,
)
from fjsp_core.result import ShopResult
from fjsp_shop.registry import register

DEFAULT_TIME_LIMIT = 15.0

#: 构造阶段固定使用的目标。``spec["objective"]`` 只决定**评价**口径。
CONSTRUCTION_OBJECTIVE = "makespan"


# ---------------------------------------------------------------------------
# 结果构造纪律（四个方法共用）
# ---------------------------------------------------------------------------


def spec_float(spec: dict[str, Any], key: str, default: float) -> float:
    """从 ``spec`` 里取一个浮点参数；缺省或缺 ``spec`` 时返回 ``default``。"""
    value = spec.get(key, default)
    if value is None:
        return float(default)
    return float(value)


def failure_result(method: str, reason: str, **detail: Any) -> ShopResult:
    """``FAILED`` 结果：说清楚**为什么不适用**，而不是给一个坏答案。

    ``best_bound`` 一律留 ``None`` —— 失败的运行连解都没有，更不该有界。
    """
    return ShopResult(method=method, status="FAILED", detail={"failure_reason": reason, **detail})


def feasible_result(
    method: str,
    instance: FJSPInstance,
    spec: dict[str, Any],
    schedule: Schedule,
    *,
    solve_time: float,
    detail: dict[str, Any],
) -> ShopResult:
    """把排程包成 ``ShopResult``：目标值由 ``fjsp_core.objective`` **独立重算**。

    三条纪律在这里一次写死：

    1. ``objective`` 来自 ``evaluate``，不来自算法内部累加的数；
    2. 启发式**没有下界**，``best_bound`` 恒为 ``None``（填成目标值会让 ``gap``
       恒为 0，看起来「已证明最优」——那是最严重的伪证据）；
    3. ``breakdown`` 一定带上三个分量原值，Week 3 的加权和才有得对账。
    """
    objective_name = spec.get("objective", "makespan")
    weights = parse_weights(spec)
    value = evaluate_objective(instance, schedule, objective_name, weights)
    detail = dict(detail)
    detail["objective_used_for_evaluation"] = objective_name
    detail["objective_used_for_construction"] = CONSTRUCTION_OBJECTIVE
    return ShopResult(
        method=method,
        status=detail.pop("status", "FEASIBLE"),
        schedule=schedule,
        objective=float(value),
        best_bound=None,
        solve_time=float(solve_time),
        breakdown=objective_breakdown(instance, schedule),
        detail=detail,
    )


# ---------------------------------------------------------------------------
# Flow Shop 的识别与解码
# ---------------------------------------------------------------------------


def flow_shop_route(instance: FJSPInstance) -> tuple[tuple[str, ...] | None, str]:
    """返回 ``(机器序列, 理由)``：适用时理由为空串，否则机器序列为 ``None``。

    适用条件（每一条都是定义的一部分，不是可选的严格性）：

    * 每道工序**恰好一台**合格机器（有柔性就不是经典 flow shop）；
    * 所有订单的机器序列**完全相同**（否则是 job shop）；
    * 序列里没有重复机器（有回流的是「可重入 flow shop」，NEH/Johnson 都不适用）；
    * 没有 ``locked_start``（锁定开工时刻会与排列解码冲突）。
    """
    route: tuple[str, ...] | None = None
    for job in instance.jobs:
        machines: list[str] = []
        for operation_id in job.operation_ids:
            operation = instance.operation(operation_id)
            eligible = operation.eligible_machine_ids
            if len(eligible) != 1:
                return None, (
                    f"工序 {operation.id!r} 有 {len(eligible)} 台合格机器；"
                    "经典 flow shop 要求每道工序固定在一台机器上"
                )
            if operation.locked_start is not None:
                return None, f"工序 {operation.id!r} 带 locked_start，无法用排列解码表达"
            if operation.locked_machine_id not in (None, eligible[0]):
                return None, (
                    f"工序 {operation.id!r} 锁定在 {operation.locked_machine_id!r}，"
                    f"但它唯一的合格机器是 {eligible[0]!r}"
                )
            machines.append(eligible[0])
        if route is None:
            route = tuple(machines)
            if len(set(route)) != len(route):
                return None, f"订单 {job.id!r} 的机器序列 {list(route)} 有重复机器（可重入 flow shop）"
        elif tuple(machines) != route:
            return None, (
                f"订单 {job.id!r} 的机器序列 {machines} 与首单 {list(route)} 不同；"
                "各订单路线不同是 job shop，不是 flow shop"
            )
    if route is None:
        return None, "实例里没有订单"
    return route, ""


def decode_permutation(
    instance: FJSPInstance, sequence: tuple[str, ...], route: tuple[str, ...]
) -> Schedule:
    """把订单排列解码成排程：**同一排列在每台机器上都按这个顺序加工**。

    这正是 permutation flow shop 的定义（``Fm|prmu|Cmax``），也是 NEH 与本模块
    Johnson 分支共同的解码口径。时间推进用两行：

    ```text
    start = max(该机器 ready, 本订单上一道工序的完工)
    end   = start + 该工序在该机器上的工时
    ```

    用的是「排列解码」而不是「每台机器各自最优排序」——后者会破坏排列性质，
    让「NEH 的排列」与「NEH 的排程」对不上号。
    """
    machine_ready = {machine_id: 0 for machine_id in instance.machine_ids}
    operations_of = {
        job.id: [instance.operation(oid) for oid in job.operation_ids] for job in instance.jobs
    }
    release_of = {job.id: job.release_time for job in instance.jobs}
    scheduled: list[ScheduledOperation] = []
    for job_id in sequence:
        ready = release_of[job_id]
        for index, operation in enumerate(operations_of[job_id]):
            machine_id = route[index]
            duration = operation.time_on(machine_id)
            if duration is None:  # pragma: no cover - 由 flow_shop_route 保证
                raise ValueError(f"工序 {operation.id!r} 在 {machine_id!r} 上没有工时")
            start = max(machine_ready[machine_id], ready)
            end = start + duration
            machine_ready[machine_id] = end
            ready = end
            scheduled.append(ScheduledOperation(operation.id, machine_id, start, end))
    return Schedule(tuple(scheduled))


def sequence_makespan(
    instance: FJSPInstance, sequence: tuple[str, ...], route: tuple[str, ...]
) -> int:
    """排列的 makespan。解码与评价走**同一条**代码路径，避免两套口径。"""
    schedule = decode_permutation(instance, sequence, route)
    ends = [item.end_time for item in schedule.operations]
    return max(ends, default=0)


def johnson_order(
    first_times: dict[str, int], second_times: dict[str, int], job_ids: tuple[str, ...]
) -> tuple[str, ...]:
    """Johnson 规则：按「第一台机器工时」与「第二台机器工时」的**分派**给出最优排列。

    ```text
    集合 A = { p1 <  p2 的订单}   按 p1 升序排在前面
    集合 B = { p1 >= p2 的订单}   按 p2 降序排在后面
    排列 = A + B
    ```

    平局按 ``job.id`` 升序决胜 —— 与 M1 的单机规则同一条纪律：结果与输入顺序、
    运行次数都无关。``p1 == p2`` 归入 B（判据用的是 ``>=``），这不是随意选择：
    等号时把订单放在后半段，可以让「长尾」集中在机器的后段，与 B 的单调性一致。
    """
    first = [job_id for job_id in job_ids if first_times[job_id] < second_times[job_id]]
    second = [job_id for job_id in job_ids if first_times[job_id] >= second_times[job_id]]
    first.sort(key=lambda job_id: (first_times[job_id], job_id))
    second.sort(key=lambda job_id: (-second_times[job_id], job_id))
    return tuple(first + second)


def neh_insertion_trace(instance: FJSPInstance) -> list[dict[str, Any]]:
    """NEH 的逐步记录：每一步插进了哪个位置、当时的 makespan、以及被比较的候选。

    返回的列表只用于**讲解与复核**（Day 1 的实验脚本打印它），求解路径不依赖它。
    """
    route, reason = flow_shop_route(instance)
    if route is None:
        raise ValueError(reason)
    job_ids = tuple(job.id for job in instance.jobs)
    totals = {
        job.id: sum(
            instance.operation(oid).time_on(route[index]) or 0
            for index, oid in enumerate(job.operation_ids)
        )
        for job in instance.jobs
    }
    # 总工时降序；平局按 job.id 升序
    ordered = sorted(job_ids, key=lambda job_id: (-totals[job_id], job_id))
    trace: list[dict[str, Any]] = []
    partial: tuple[str, ...] = ()
    for job_id in ordered:
        candidates: list[tuple[int, int, tuple[str, ...]]] = []
        for position in range(len(partial) + 1):
            trial = partial[:position] + (job_id,) + partial[position:]
            candidates.append((sequence_makespan(instance, trial, route), position, trial))
        # 位置升序在前：平局时保留**最早**的位置（确定性决胜）
        best = min(candidates, key=lambda item: (item[0], item[1]))
        partial = best[2]
        trace.append(
            {
                "job": job_id,
                "total_time": totals[job_id],
                "partial": list(partial),
                "position": best[1],
                "makespan": best[0],
                "candidates": [item[0] for item in candidates],
            }
        )
    return trace


def neh_sequence(instance: FJSPInstance) -> tuple[tuple[str, ...], int, tuple[str, ...]]:
    """NEH 排列：按总工时降序逐个插入到使当前 makespan 最小的位置。"""
    route, reason = flow_shop_route(instance)
    if route is None:
        raise ValueError(reason)
    trace = neh_insertion_trace(instance)
    if not trace:
        return (), 0, route
    sequence = tuple(trace[-1]["partial"])
    return sequence, int(trace[-1]["makespan"]), route


# ---------------------------------------------------------------------------
# 注册方法
# ---------------------------------------------------------------------------


def _machine_loads(instance: FJSPInstance, route: tuple[str, ...]) -> dict[str, int]:
    loads = {machine_id: 0 for machine_id in route}
    for job in instance.jobs:
        for index, operation_id in enumerate(job.operation_ids):
            loads[route[index]] += instance.operation(operation_id).time_on(route[index]) or 0
    return loads


def _times_on(instance: FJSPInstance, job_id: str, route: tuple[str, ...], machine_id: str):
    index = route.index(machine_id)
    operation = instance.operation(instance.job(job_id).operation_ids[index])
    return operation.time_on(machine_id) or 0


@register("flow_johnson", "Flow Shop 的 Johnson 规则：2 台机器精确，>=3 台退化为瓶颈机对")
def flow_johnson(instance: FJSPInstance, spec: dict[str, Any]) -> ShopResult:
    """Johnson 规则。**它只对两台机器精确**，>=3 台时本方法明确退化并如实记录。

    三条分支：

    ```text
    路线长度 == 1   单机，Cmax 与顺序无关，按 job.id 排（记为退化情形）
    路线长度 == 2   在两台机器上直接应用 Johnson 规则（F2||Cmax 的最优排列）
    路线长度 >= 3   在负载最大的两台机器上应用 Johnson 规则（启发式，无最优性保证）
    ```
    """
    import time

    started = time.perf_counter()
    route, reason = flow_shop_route(instance)
    if route is None:
        return failure_result("flow_johnson", reason, stage="applicability")

    job_ids = tuple(job.id for job in instance.jobs)
    loads = _machine_loads(instance, route)
    release_free = all(job.release_time == 0 for job in instance.jobs)

    if len(route) == 1:
        sequence = tuple(sorted(job_ids))
        applicability = "single_machine_degenerate"
        exact = False
        certificate = "单机 flow shop：Cmax = 总工时，与顺序无关"
        pair: tuple[str, ...] = (route[0],)
    elif len(route) == 2:
        first_times = {job_id: _times_on(instance, job_id, route, route[0]) for job_id in job_ids}
        second_times = {job_id: _times_on(instance, job_id, route, route[1]) for job_id in job_ids}
        sequence = johnson_order(first_times, second_times, job_ids)
        applicability = "johnson_f2"
        exact = release_free
        certificate = (
            "Johnson 定理：F2||Cmax 的最优排程一定是排列排程，且该排列由本规则给出"
        )
        pair = (route[0], route[1])
    else:
        # 两台瓶颈机：负载最大的两台；平局按路线位置（机器更靠前的先当「第一台」）
        ranked = sorted(
            route, key=lambda machine_id: (-loads[machine_id], route.index(machine_id))
        )
        pair = tuple(sorted(ranked[:2], key=lambda machine_id: route.index(machine_id)))
        first_times = {job_id: _times_on(instance, job_id, route, pair[0]) for job_id in job_ids}
        second_times = {job_id: _times_on(instance, job_id, route, pair[1]) for job_id in job_ids}
        sequence = johnson_order(first_times, second_times, job_ids)
        applicability = "johnson_on_bottleneck_pair"
        exact = False
        certificate = (
            "Johnson 只对 2 台机器精确；本结果是在瓶颈机对上的 Johnson 排列，"
            "解码到完整路线，**没有最优性保证**"
        )

    schedule = decode_permutation(instance, sequence, route)
    solve_time = time.perf_counter() - started
    status = "OPTIMAL" if exact else "FEASIBLE"
    if exact and len(route) == 2 and not release_free:
        status = "FEASIBLE"
    detail = {
        "status": status,
        "route": list(route),
        "job_sequence": list(sequence),
        "applicability": applicability,
        "applies_directly": applicability == "johnson_f2",
        "bottleneck_pair": list(pair),
        "machine_loads": loads,
        "release_times_all_zero": release_free,
        "optimality_certificate": certificate if status == "OPTIMAL" else "",
        "optimality_note": certificate if status != "OPTIMAL" else "",
        "has_bound": False,
    }
    return feasible_result(
        "flow_johnson", instance, spec, schedule, solve_time=solve_time, detail=detail
    )


@register("flow_neh", "NEH 启发式：按总工时降序逐个插入，任意台数 flow shop")
def flow_neh(instance: FJSPInstance, spec: dict[str, Any]) -> ShopResult:
    """NEH：**启发式**，任意台数可用，但没有任何最优性保证。

    算法三步（第三步是 NEH 的全部内容）：

    ```text
    1. 每个订单算总工时，按降序排（平局按 job.id 升序）
    2. 取第一个订单作为初始部分排列
    3. 其余订单逐个「试插到每个位置」，保留使当前 makespan 最小的那个排列
       —— 平局保留**最靠前**的位置
    ```
    """
    import time

    started = time.perf_counter()
    route, reason = flow_shop_route(instance)
    if route is None:
        return failure_result("flow_neh", reason, stage="applicability")

    trace = neh_insertion_trace(instance)
    if not trace:
        return failure_result("flow_neh", "实例里没有订单", stage="applicability")
    sequence = tuple(trace[-1]["partial"])
    schedule = decode_permutation(instance, sequence, route)
    solve_time = time.perf_counter() - started
    detail = {
        "route": list(route),
        "job_sequence": list(sequence),
        "insertion_order": [step["job"] for step in trace],
        "insertion_positions": [step["position"] for step in trace],
        "insertion_makespans": [step["makespan"] for step in trace],
        "evaluated_insertions": sum(len(step["candidates"]) for step in trace),
        "machine_loads": _machine_loads(instance, route),
        "optimality_certificate": "",
        "optimality_note": (
            "NEH 是启发式：m>=3 的 flow shop 是 NP-hard，NEH 没有最优性保证；"
            "平局时保留最靠前的插入位置"
        ),
        "has_bound": False,
    }
    return feasible_result(
        "flow_neh", instance, spec, schedule, solve_time=solve_time, detail=detail
    )
