"""Day 4：用 Cumulative 建有限容量资源小例子，对比 NoOverlap 语义。

手算实例：2 台机器、3 个 job、每个 p = 5。

```text
只有 NoOverlap（= cpsat_parallel）：两台机器并行 -> Cmax = 10
再加 AddCumulative(capacity=1, demand=1)：任意时刻至多一个工序在跑 -> Cmax = 15
再加 AddCumulative(capacity=2, demand=1)：容量约束冗余 -> Cmax 回到 10
capacity=1 但 demand=2：单个工序自己就超容量 -> INFEASIBLE
```

第二个实例：3 台机器、4 个 job、每个 p = 4，每工序占 2 单位、容量 3。
``2 + 2 = 4 > 3``，所以任意时刻同样只能有一个工序在跑 -> Cmax = 16（无容量时是 8）。

脚本用 ``cumulative_profile`` **独立重算**峰值占用。这件事必须单独做：
M1 的 ``validate_schedule`` 只覆盖机器互斥、机器资格、precedence 与释放时间，
**不覆盖** Cumulative 的容量语义。

只打印，不写盘。
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from opt_common.bridge import (
    Instance,
    Job,
    Machine,
    Operation,
    makespan,
    validate_schedule,
)
from opt_models.cpsat_models import cpsat_cumulative, cpsat_parallel, cumulative_profile


def one_op_instance(times: list[int], machines: int) -> Instance:
    eligible = tuple(f"M{i}" for i in range(machines))
    return Instance(
        tuple(Job(f"J{index}", (f"J{index}_O0",)) for index in range(len(times))),
        tuple(
            Operation(f"J{index}_O0", f"J{index}", value, eligible)
            for index, value in enumerate(times)
        ),
        tuple(Machine(f"M{i}", f"M{i}") for i in range(machines)),
    )


def run(instance: Instance, method: str, params: dict) -> None:
    result = method(instance, {"objective": "makespan", "time_limit": 5.0, **params})
    if result.schedule is None:
        print(
            f"  {params}: 状态 {result.status}, objective = {result.objective}, "
            f"best_bound = {result.best_bound}"
        )
        return
    validate_schedule(instance, result.schedule)
    demand = int(params.get("resource_demand", 1) or 1)
    peak, moment = cumulative_profile(instance, result.schedule, demand)
    print(
        f"  {params}: 状态 {result.status}, Cmax = {makespan(instance, result.schedule)}, "
        f"峰值占用 {peak}（demand={demand}），出现在 t = {moment}"
    )


def main() -> None:
    instance = one_op_instance([5, 5, 5], 2)
    print("=== 1. 2 台机器、3 个 p=5 的工序 ===")
    run(instance, cpsat_parallel, {"no_capacity": True})
    run(instance, cpsat_cumulative, {"resource_capacity": 1, "resource_demand": 1})
    run(instance, cpsat_cumulative, {"resource_capacity": 2, "resource_demand": 1})
    run(instance, cpsat_cumulative, {"resource_capacity": 1, "resource_demand": 2})

    tight = cpsat_cumulative(
        instance,
        {"objective": "makespan", "time_limit": 5.0, "resource_capacity": 1,
         "resource_demand": 1},
    )
    print("  容量 1 时的排程（三道工序被压成串行）：")
    for item in sorted(tight.schedule.operations, key=lambda r: r.start_time):
        print(f"    {item.operation_id} 在 {item.machine_id} 上 [{item.start_time},{item.end_time}]")

    print()
    print("=== 2. 3 台机器、4 个 p=4 的工序，demand=2、capacity=3 ===")
    big = one_op_instance([4, 4, 4, 4], 3)
    run(big, cpsat_parallel, {"no_capacity": True})
    run(big, cpsat_cumulative, {"resource_capacity": 3, "resource_demand": 2})
    run(big, cpsat_cumulative, {"resource_capacity": 4, "resource_demand": 2})

    print()
    print("=== 3. NoOverlap 与 Cumulative 的语义差别 ===")
    print("NoOverlap 是「容量 1 的排他约束」：一台机器同一时刻只能有一个工序。")
    print("Cumulative 是「容量 C 的可再生资源」：同一时刻所有在跑的工序需求之和 <= C。")
    print("  - NoOverlap 用区间之间的两两互斥表达，是一类特殊的 Cumulative；")
    print("  - Cumulative 允许「多个工序同时跑」，只要总需求不超过容量，")
    print("    所以它能表达机器互斥表达不了的东西（人力、模具、AGV 这类共享资源）。")
    print("  - 本脚本的独立复核函数 cumulative_profile 只认 M2 新增的语义：")
    print("    M1 的 validate_schedule 全过，也不代表容量约束被满足。")


if __name__ == "__main__":
    main()
