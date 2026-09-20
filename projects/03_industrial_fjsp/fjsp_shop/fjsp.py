"""Week 2：FJSP 的解码器、三种启发式指派与三个注册方法。

FJSP 的决策是**二元组**：给每道工序选一台合格机器（``assignment``），再决定
機器上的加工顺序（``sequencing``）。本模块把这两件事分成两层：

```text
assignment 层   assign_shortest / assign_load_balance / assign_random    ← 决策一：选机
decoder  层     decode（静态顺序） / dispatch（动态 ECT 派工）             ← 决策二：排序
```

注册的三个方法名（``configs/month3.json`` 直接引用）**只差指派这一步**，派工规则
完全相同（非延迟 ECT 派工）。这是刻意的控制变量设计：Day 6 要回答「机器指派值多少
分」，就不能让派工规则同时变。

| 方法名 | 指派策略 | 派工 |
|---|---|---|
| ``fjsp_random`` | 在合格机器里均匀随机（局部 ``Random(seed)``） | 非延迟 ECT 派工 |
| ``fjsp_shortest`` | 每道工序各自最快的机器 | 同上 |
| ``fjsp_loadbalance`` | 预计负载最小的机器（长工序先放） | 同上 |

三条纪律（与 M1/M2 一致，不是可选项）：

1. **启发式没有下界。** ``best_bound`` 一律留 ``None``；填成目标值会让 ``gap`` 恒为
   0，看起来「已证明最优」——这是最严重的伪证据。
2. **返回前用独立验证器复核。** ``validate_schedule`` 由 ``fjsp_core`` 提供，不经过
   本模块的任何代码。
3. **``build_time`` 与 ``solve_time`` 分开记。** 本模块里 ``build_time`` 是「算指派」
   的时间、``solve_time`` 是「派工」的时间，对应 M2 的「建模 vs 求解」。

**本模块只覆盖纯 FJSP + 释放时间。** 带换型、日历、维护、次生资源、资质或锁定工序的
实例会被 :func:`require_plain_fjsp` 明确拒绝（抛 ``ValueError``），而不是产出一个过不了
验证器的排程。这些约束属于 Week 3 / Week 4 的专门方法。
"""

from __future__ import annotations

import random
import time
from collections.abc import Mapping, Sequence
from typing import Any

from fjsp_core.models import FJSPInstance, Schedule, ScheduledOperation
from fjsp_core.objective import evaluate, objective_breakdown, parse_weights
from fjsp_core.result import ShopResult
from fjsp_core.schedule_validation import validate_schedule
from fjsp_core.validation import validate_instance
from fjsp_shop.registry import register

#: 派工规则。``ect`` 是本模块的默认规则，三种启发式共用它。
DISPATCH_RULES = ("ect", "est", "spt", "mwkr")


# ---------------------------------------------------------------------------
# 范围闸门：本周模型不覆盖的工业约束
# ---------------------------------------------------------------------------


def require_plain_fjsp(instance: FJSPInstance) -> None:
    """拒绝本周算法不建模的约束，**在算之前**而不是在验证器那里才发现。

    为什么必须在这里拒绝：解码器只要丢掉换型/日历/维护/锁定，产出的排程一定过不了
    独立验证器。与其让 benchmark 记一条 ``INVALID_SOLUTION``（比 ``FAILED`` 更严重，
    因为「求解器给出了一个不合法解」），不如在这里带着可读的原因拒绝。

    资质与次生资源也在拒绝清单里：前者会改变「哪些机器真的可选」，后者要给工序分配
    资源，两者都会改变可行域。**拒绝是本周的诚实选择，不是永久结论**——Week 3/4 的
    专门方法会分别覆盖它们。
    """
    reasons: list[str] = []
    if instance.calendars:
        reasons.append("calendars")
    if instance.maintenances:
        reasons.append("maintenances")
    if instance.setups:
        reasons.append("setups")
    if instance.workers:
        reasons.append("workers")
    if instance.qualifications:
        reasons.append("qualifications")
    locked = [
        op.id
        for op in instance.operations
        if op.locked_machine_id is not None or op.locked_start is not None
    ]
    if locked:
        reasons.append(f"locked operations {locked[:3]}")
    if reasons:
        raise ValueError(
            "plain FJSP only (release times are supported); unsupported constraints: "
            + ", ".join(reasons)
        )


# ---------------------------------------------------------------------------
# 解码器：assignment + order -> Schedule
# ---------------------------------------------------------------------------


def _earliest_fit(
    intervals: Sequence[tuple[int, int]], earliest: int, minutes: int
) -> int:
    """在 ``intervals`` 的空隙里找 ``>= earliest`` 且能放下 ``minutes`` 的最早起点。

    ``intervals`` 是半开区间 ``[start, end)`` 的列表。返回时刻一定满足
    「与所有已有区间不重叠」，因此调用方不需要再检查一次。
    """
    start = earliest
    for begin, end in intervals:
        if end <= start:
            continue  # 这个区间整体在候选起点之前，跳过
        if begin - start >= minutes:
            return start  # 候选起点与 busy 段之间放得下
        start = max(start, end)  # 否则被这个区间挡住，往后推
    return start


def decode(
    instance: FJSPInstance,
    assignment: Mapping[str, str],
    order: Sequence[str],
    *,
    insert: bool = True,
) -> Schedule:
    """把「机器指派 + 工序顺序」解码成排程。

    ``insert=True`` 是**插入式解码**（active / gap-filling）：工序放进该机器上第一个
    放得下的空隙。``insert=False`` 是**附加式解码**（append）：机器只在末尾往后接着排。

    两者都是合法解的构造器（本函数产出的排程一定过 ``validate_schedule``），区别只在
    质量：插入式解码能生成**主动排程**族，其中含最优 makespan 排程；附加式只能生成
    机器上「后到者的开始不早于先到者的结束」这一更窄的族。Day 2 的实验会实测这条差距。

    解码顺序对结果有影响——同一个 ``assignment`` 换一个 ``order`` 就是另一个排程，这
    正是「FJSP 的决策比 JSP 多一维」在代码里的样子。

    ``order`` 必须是**拓扑序**：每个订单的工序按工艺路线先后出现。这不是装饰性要求，
    而是解码逻辑的前提（工序放置时只把「该订单已排完工时刻」当下界）。给一个非拓扑序
    会被显式拒绝，而不是悄悄产出一个违反 precedence 的排程。
    """
    validate_instance(instance)
    require_plain_fjsp(instance)
    operations = {op.id: op for op in instance.operations}
    if len(order) != len(operations) or set(order) != set(operations):
        raise ValueError("order must list every operation exactly once")
    _require_topological(instance, order)

    job_ready = {job.id: job.release_time for job in instance.jobs}
    busy: dict[str, list[tuple[int, int]]] = {m.id: [] for m in instance.machines}
    free_from: dict[str, int] = {m.id: 0 for m in instance.machines}
    placed: list[ScheduledOperation] = []

    for operation_id in order:
        op = operations[operation_id]
        machine_id = assignment.get(operation_id)
        if machine_id is None:
            raise ValueError(f"assignment is missing operation {operation_id!r}")
        minutes = op.time_on(machine_id)
        if minutes is None:
            raise ValueError(f"{operation_id!r} cannot run on {machine_id!r}")
        earliest = job_ready[op.job_id]
        if insert:
            start = _earliest_fit(busy[machine_id], earliest, minutes)
            busy[machine_id].append((start, start + minutes))
            busy[machine_id].sort()
        else:
            start = max(earliest, free_from[machine_id])
        end = start + minutes
        free_from[machine_id] = max(free_from[machine_id], end)
        job_ready[op.job_id] = end
        placed.append(ScheduledOperation(op.id, machine_id, start, end))

    schedule = Schedule(tuple(sorted(placed, key=_placement_key)))
    validate_schedule(instance, schedule)
    return schedule


def _placement_key(item: ScheduledOperation) -> tuple[int, str, str]:
    """输出顺序的确定性键：先按开工时刻，再按机器 id、工序 id。"""
    return (item.start_time, item.machine_id, item.operation_id)


def _require_topological(instance: FJSPInstance, order: Sequence[str]) -> None:
    """顺序里每道工序都必须排在它同订单前道工序之后。"""
    position = {operation_id: index for index, operation_id in enumerate(order)}
    for job in instance.jobs:
        for before, after in zip(job.operation_ids, job.operation_ids[1:]):
            if position[before] > position[after]:
                raise ValueError(
                    f"order must respect the process route: {before!r} must come "
                    f"before {after!r} (job {job.id!r})"
                )


# ---------------------------------------------------------------------------
# 非延迟派工：assignment -> Schedule（顺序动态决定）
# ---------------------------------------------------------------------------


def dispatch(
    instance: FJSPInstance,
    assignment: Mapping[str, str],
    *,
    rule: str = "ect",
) -> Schedule:
    """非延迟（non-delay）派工：机器只要有活就不空等。

    每一步的候选集合是「每个订单工艺路线上的下一个待排工序」，按 ``rule`` 排序取最优
    的一个，放到它被指派机器的当前空闲时刻。

    | ``rule`` | 排序键（越小越优先） | 直觉 |
    |---|---|---|
    | ``ect`` | 预计完工时刻 | 让机器尽快空出来 |
    | ``est`` | 最早可开工时刻 | 先消化能立刻开工的工序 |
    | ``spt`` | 在该机器上的工时 | 短工序先做 |
    | ``mwkr`` | 剩余工作量（越大越优先） | 剩余活多的订单先推 |

    平局一律按 ``(job.id, operation.id)`` 升序决胜，保证与输入顺序、运行次数无关。

    **非延迟不等于最优。** 机器空等一道马上要来的短工序有时更好（M1 Day 4 第 6 节的
    空等反例在这里同样成立），所以本函数只是「简单、确定、可复现」的基线。
    """
    validate_instance(instance)
    require_plain_fjsp(instance)
    if rule not in DISPATCH_RULES:
        raise ValueError(f"unknown dispatch rule: {rule!r}")

    operations = {op.id: op for op in instance.operations}
    remaining = {job.id: list(job.operation_ids) for job in instance.jobs}
    cursor = {job.id: 0 for job in instance.jobs}
    work_left = {
        job.id: sum(operations[op_id].min_time for op_id in job.operation_ids)
        for job in instance.jobs
    }
    job_ready = {job.id: job.release_time for job in instance.jobs}
    machine_free: dict[str, int] = {m.id: 0 for m in instance.machines}
    placed: list[ScheduledOperation] = []
    pending = sum(len(ids) for ids in remaining.values())

    while pending:
        # 候选 = 每个订单工艺路线上的下一个待排工序；键 = (规则值..., 平局决胜)
        candidates: list[tuple[tuple[Any, ...], str, str, str, int, int]] = []
        for job in instance.jobs:
            index = cursor[job.id]
            if index >= len(job.operation_ids):
                continue
            op = operations[job.operation_ids[index]]
            machine_id = assignment.get(op.id)
            if machine_id is None:
                raise ValueError(f"assignment is missing operation {op.id!r}")
            minutes = op.time_on(machine_id)
            if minutes is None:
                raise ValueError(f"{op.id!r} cannot run on {machine_id!r}")
            start = max(job_ready[job.id], machine_free[machine_id])
            end = start + minutes
            if rule == "ect":
                key: tuple[Any, ...] = (end, start, minutes)
            elif rule == "est":
                key = (start, minutes, end)
            elif rule == "spt":
                key = (minutes, start, end)
            else:  # mwkr
                key = (-work_left[job.id], start, minutes)
            candidates.append((key, job.id, op.id, machine_id, start, end))
        _, job_id, op_id, machine_id, start, end = min(
            candidates, key=lambda item: (item[0], item[1], item[2])
        )
        placed.append(ScheduledOperation(op_id, machine_id, start, end))
        cursor[job_id] += 1
        job_ready[job_id] = end
        machine_free[machine_id] = end
        work_left[job_id] -= operations[op_id].min_time
        pending -= 1

    schedule = Schedule(tuple(sorted(placed, key=_placement_key)))
    validate_schedule(instance, schedule)
    return schedule


# ---------------------------------------------------------------------------
# 三种指派策略
# ---------------------------------------------------------------------------


def assign_shortest(instance: FJSPInstance) -> dict[str, str]:
    """每道工序各自选最快的机器（平局按机器 id 升序）。

    完全**不看机器争用**：所有工序可以同时认为「M0 最快」。这正是它作为基线的价值
    ——它测的是「局部最优能不能拼成全局好解」。
    """
    return {
        op.id: min(op.machine_times, key=lambda pair: (pair[1], pair[0]))[0]
        for op in instance.operations
    }


def assign_load_balance(instance: FJSPInstance) -> dict[str, str]:
    """长工序先放，每次选「放进去之后预计负载最小」的机器。

    与 M1 Day 5 的并行机 LPT 同一个直觉：长任务先放、短任务填空，负载自然趋近平衡。
    顺序取 ``(-min_time, op.id)``，保证确定性。

    与 ``assign_shortest`` 的差别是**它记得机器已经被占了多少**：预计负载 =
    ``当前负载 + 在这台机器上的工时``，比较的是加进去之后的结果，不是单道工序的工时。
    平局按 ``(预计负载, 当前负载, 机器 id)`` 决胜。
    """
    load: dict[str, int] = {m.id: 0 for m in instance.machines}
    assignment: dict[str, str] = {}
    for op in sorted(instance.operations, key=lambda item: (-item.min_time, item.id)):
        options = [(load[mid] + minutes, load[mid], mid) for mid, minutes in op.machine_times]
        _, _, machine_id = min(options)
        assignment[op.id] = machine_id
        load[machine_id] += op.time_on(machine_id) or 0
    return assignment


def assign_random(instance: FJSPInstance, seed: int = 0) -> dict[str, str]:
    """在合格机器里均匀随机（平局不需要决胜——随机本身就是策略）。

    用**局部** ``random.Random(seed)``：不碰全局随机状态，因此同种子永远给同一个指派，
    且不会污染调用方的随机流（与 ``fjsp_io.generator`` 同一条纪律）。
    """
    rng = random.Random(seed)
    return {
        op.id: rng.choice(op.eligible_machine_ids)
        for op in sorted(instance.operations, key=lambda item: item.id)
    }


ASSIGNMENTS = {
    "shortest": assign_shortest,
    "loadbalance": assign_load_balance,
    "random": assign_random,
}


# ---------------------------------------------------------------------------
# 三个注册方法
# ---------------------------------------------------------------------------


def _run_heuristic(
    instance: FJSPInstance,
    spec: dict[str, Any],
    *,
    method: str,
    assignment: dict[str, str],
    build_time: float,
) -> ShopResult:
    """三个启发式共用的收尾：派工 → 独立验证 → 目标评估 → 组装 ``ShopResult``。"""
    rule = str(spec.get("rule", "ect"))
    objective_name = str(spec.get("objective", "makespan"))
    solve_start = time.perf_counter()
    schedule = dispatch(instance, assignment, rule=rule)
    solve_time = time.perf_counter() - solve_start

    value = float(
        evaluate(instance, schedule, objective_name, parse_weights(spec))
    )
    return ShopResult(
        method=method,
        status="FEASIBLE",
        schedule=schedule,
        objective=value,
        best_bound=None,  # 启发式没有下界：不填 0，更不填目标值
        build_time=build_time,
        solve_time=solve_time,
        iterations=None,
        breakdown=objective_breakdown(instance, schedule),
        detail={
            "objective_name": objective_name,
            "dispatch_rule": rule,
            "assignment": dict(sorted(assignment.items())),
            "bound_kind": "none (heuristic)",
        },
    )


def _prepare(instance: FJSPInstance) -> None:
    validate_instance(instance)
    require_plain_fjsp(instance)


@register("fjsp_random", "随机机器指派 + 非延迟 ECT 派工")
def fjsp_random(instance: FJSPInstance, spec: dict[str, Any]) -> ShopResult:
    """随机指派基线：``seed`` 决定指派，同一 seed 结果完全一致。"""
    _prepare(instance)
    seed = int(spec.get("seed", 0))
    start = time.perf_counter()
    assignment = assign_random(instance, seed)
    build_time = time.perf_counter() - start
    return _run_heuristic(
        instance, spec, method="fjsp_random", assignment=assignment, build_time=build_time
    )


@register("fjsp_shortest", "每道工序选用最快机器 + 非延迟 ECT 派工")
def fjsp_shortest(instance: FJSPInstance, spec: dict[str, Any]) -> ShopResult:
    """最快机器基线：忽略机器争用，只让每道工序自身耗时最短。"""
    _prepare(instance)
    start = time.perf_counter()
    assignment = assign_shortest(instance)
    build_time = time.perf_counter() - start
    return _run_heuristic(
        instance, spec, method="fjsp_shortest", assignment=assignment, build_time=build_time
    )


@register("fjsp_loadbalance", "预计负载最小的机器 + 非延迟 ECT 派工")
def fjsp_loadbalance(instance: FJSPInstance, spec: dict[str, Any]) -> ShopResult:
    """负载均衡基线：长工序先放、每次选加进去之后预计负载最小的机器。"""
    _prepare(instance)
    start = time.perf_counter()
    assignment = assign_load_balance(instance)
    build_time = time.perf_counter() - start
    return _run_heuristic(
        instance, spec, method="fjsp_loadbalance", assignment=assignment, build_time=build_time
    )
