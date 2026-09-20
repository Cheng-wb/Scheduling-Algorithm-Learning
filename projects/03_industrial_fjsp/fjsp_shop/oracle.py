"""Week 2 Day 5：小实例的穷举 oracle —— 与解码器、CP-SAT 都独立的第三条计算路径。

**为什么必须有它。** Day 2 的解码器和 Day 4 的 CP-SAT 都可能有 bug；如果拿它们互相
对拍，两个都错也能「对得上」。oracle 换一条完全独立的实现路径：自己枚举机器指派、
自己枚举工序顺序、自己维护机器占用区间，**不 import 解码器，也不 import CP-SAT**，
所以它给出的最优值可以作为基准。

```text
搜索空间 = Π_o |合格机器_o|  ×  (拓扑序个数)
           └─ 指派枚举 ─┘      └─ 顺序枚举 ─┘
```

**顺序为什么只能枚举拓扑序。** 每个订单的工艺路线是一条链（``O0 -> O1 -> ...``），
解码器按给定顺序逐个放置工序时，用「该订单已排完工时刻」当作下界。若顺序**不是**
拓扑序（后道工序排在前道之前），后道就会被放到前道之前，产出的是**非法排程**。

写这段备注的直接原因是实测：本模块的第一版枚举的是全部 ``n!`` 个排列。在一个
2 订单 x 2 工序、两道工序都在两台机器上可做的实例上（工时
``O00: M0=1, M1=9``；``O01: M0=4, M1=1``；``O10: M0=2, M1=7``；``O11: M0=7, M1=2``，
指派 ``O00->M0, O01->M1, O10->M0, O11->M1``），它给出 ``4``，而只枚举拓扑序得到 ``5``。
那个 ``4`` 来自顺序 ``(O00, O11, O01, O10)``：后道工序 ``O11`` 被排在前道工序 ``O10``
之前，绕过工艺路线给的先后约束；独立验证器对这个排程报 ``precedence: O10 -> O11``。
修法就是只枚举拓扑序，并在每个改进点上调用验证器复核。可复现的完整演示见
``examples/m3w2d5_oracle.py`` 第 4 节。

拓扑序个数 = ``n! / Π_j (k_j!)``（``k_j`` 是订单 ``j`` 的工序数，即多项式系数）。

**它能证明什么、不能证明什么**（这是本模块最重要的一段）：

| 情形 | 行为 |
|---|---|
| ``objective = "makespan"``，纯 FJSP + 释放时间 | 给出**最优值证书**（定理：主动排程族含最优 makespan 排程） |
| 目标不是 makespan | **拒绝**。本模块只为 makespan 搭建并核对了证书，别的目标名一律在枚举之前拒绝（这是保守的模块边界，不是「数学上不可证」的断言） |
| 有日历 / 维护 / 换型 / 资源 / 资质 / 锁定工序 | **拒绝**。``_build`` 不建模它们，算出来的「最优」是另一个更松问题的最优 |
| 空间 ``> limit`` | **拒绝**。不能算完再说，也不能抽样后仍叫它 ``optimum`` |

拒绝一律抛 ``ValueError``，并且**绝不返回一个「受限枚举的最好值」冒充最优**。调用方
（如 ``fjsp_experiments.benchmark`` 的参考值分档）必须把拒绝当作「这一档不适用」。

**独立性是刻意设计的结果，不是巧合**：连「拒绝不支持的约束」这段判断都与
``fjsp_shop/fjsp.py`` 各写一份，为的是让 oracle 不依赖被它对拍的对象。唯一共用的
是 ``fjsp_core`` 的目标函数与独立验证器——它们不是被对拍的对象。
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Iterator, Sequence

from fjsp_core.models import FJSPInstance, Schedule, ScheduledOperation
from fjsp_core.objective import evaluate
from fjsp_core.schedule_validation import validate_schedule
from fjsp_core.validation import validate_instance

#: 默认空间上限。超过就拒绝——这个默认值下只有很小很小的实例能被证明。
DEFAULT_LIMIT = 200_000

#: 本枚举**只**证明这一个目标。
CERTIFIABLE_OBJECTIVES = ("makespan",)


def topological_order_count(instance: FJSPInstance) -> int:
    """拓扑序个数 ``n! / Π_j k_j!``（订单的工艺路线都是链，线性扩展数就是这个）。"""
    total = math.factorial(len(instance.operations))
    for job in instance.jobs:
        total //= math.factorial(len(job.operation_ids))
    return total


def enumeration_space(instance: FJSPInstance) -> int:
    """搜索空间大小 ``Π_o |合格机器_o| × (拓扑序个数)``。

    顺序一侧**不能**用 ``n!``：那会同时高估空间（把非法的顺序算进来）并把上限闸门
    设得过紧——一个 2 订单 × 3 工序的实例真实空间是 ``720 / (3!·3!) = 20`` 个拓扑序，
    不是 720。
    """
    assignments = 1
    for op in instance.operations:
        assignments *= len(op.machine_times)
    return assignments * topological_order_count(instance)


def _topological_orders(instance: FJSPInstance) -> Iterator[tuple[str, ...]]:
    """按订单游标 DFS 生成全部拓扑序（每个订单的工序必须按工艺路线先后出现）。"""
    routes = [list(job.operation_ids) for job in instance.jobs]
    cursor = [0] * len(routes)
    order: list[str] = []
    total = sum(len(route) for route in routes)

    def walk() -> Iterator[tuple[str, ...]]:
        if len(order) == total:
            yield tuple(order)
            return
        for index, route in enumerate(routes):
            position = cursor[index]
            if position >= len(route):
                continue
            order.append(route[position])
            cursor[index] = position + 1
            yield from walk()
            cursor[index] = position
            order.pop()

    yield from walk()


def _reject_unsupported(instance: FJSPInstance) -> None:
    """拒绝本枚举不建模的约束。

    这段判断与 ``fjsp.py`` 的同名闸门**刻意重复**：oracle 的独立性要求它不 import
    被对拍的模块。两处一旦不一致，测试会先发现。
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
            "exhaustive enumeration only certifies plain FJSP with release times; "
            "unsupported constraints: " + ", ".join(reasons)
        )


def _earliest_fit(intervals: Sequence[tuple[int, int]], earliest: int, minutes: int) -> int:
    """在 ``[start, end)`` 列表的空隙里找最早的可行起点。

    这是 oracle 自己的机器占用跟踪——不调用 ``fjsp.py`` 里的任何函数。
    """
    start = earliest
    for begin, end in intervals:
        if end <= start:
            continue
        if begin - start >= minutes:
            return start
        start = max(start, end)
    return start


def _build(
    instance: FJSPInstance, assignment: dict[str, str], order: Sequence[str]
) -> Schedule:
    """用**自己的**机器可用区间跟踪，把 (指派, 顺序) 变成一个排程。

    插入式（active）解码：工序落在该机器第一个放得下的空隙。释放时间与工艺路线都
    在推导里（``earliest = max(前道完工, 订单释放)``），所以产出的排程天然满足这两条。
    """
    operations = {op.id: op for op in instance.operations}
    job_ready = {job.id: job.release_time for job in instance.jobs}
    busy: dict[str, list[tuple[int, int]]] = {m.id: [] for m in instance.machines}
    placed: list[ScheduledOperation] = []
    for operation_id in order:
        op = operations[operation_id]
        machine_id = assignment[operation_id]
        minutes = op.time_on(machine_id)
        assert minutes is not None  # assignment 只在合格机器里取值
        start = _earliest_fit(busy[machine_id], job_ready[op.job_id], minutes)
        end = start + minutes
        busy[machine_id].append((start, end))
        busy[machine_id].sort()
        job_ready[op.job_id] = end
        placed.append(ScheduledOperation(op.id, machine_id, start, end))
    return Schedule(tuple(sorted(placed, key=lambda item: (item.start_time, item.machine_id, item.operation_id))))


def exhaustive_optimum(
    instance: FJSPInstance,
    objective: str = "makespan",
    limit: int = DEFAULT_LIMIT,
) -> tuple[float, Schedule]:
    """穷举 ``Π_o |合格机器_o| × (拓扑序个数)`` 个组合，返回 ``(最优值, 一个达到它的排程)``。

    抛 ``ValueError`` 的三种情形：目标不可证明、实例含不支持的约束、空间超过 ``limit``。
    """
    validate_instance(instance)
    if not instance.operations:
        raise ValueError("instance has no operations")
    if objective not in CERTIFIABLE_OBJECTIVES:
        raise ValueError(
            f"exhaustive_optimum only certifies {CERTIFIABLE_OBJECTIVES} (got {objective!r}); "
            "this module builds and checks the certificate for makespan only, so other "
            "objectives are refused before the enumeration starts"
        )
    _reject_unsupported(instance)

    space = enumeration_space(instance)
    if space > limit:
        raise ValueError(
            f"enumeration space {space} exceeds limit {limit}; "
            "a restricted enumeration must never be reported as the optimum"
        )

    operation_ids = [op.id for op in instance.operations]
    machine_choices = [op.eligible_machine_ids for op in instance.operations]
    orders = list(_topological_orders(instance))

    best_value: float | None = None
    best_schedule: Schedule | None = None
    for machines in itertools.product(*machine_choices):
        assignment = dict(zip(operation_ids, machines))
        for order in orders:
            schedule = _build(instance, assignment, order)
            value = float(evaluate(instance, schedule, objective))
            if best_value is None or value < best_value:
                # 只在「有改进」时用独立验证器复核：代价可忽略，且保证**最终返回的
                # 那个排程**一定是合法的。若构造有错，这里会立刻抛而不是返回错值。
                validate_schedule(instance, schedule)
                best_value = value
                best_schedule = schedule
    assert best_value is not None and best_schedule is not None  # 空间非空时必有解
    return best_value, best_schedule
