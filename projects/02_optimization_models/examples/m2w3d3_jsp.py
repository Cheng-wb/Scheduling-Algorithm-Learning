"""Day 3：用 precedence 与 NoOverlap 建立小型 JSP，并用独立验证器核对结果。

实例（2 job x 2 工序，固定路由）：

```text
J0：J0_O0 在 M0 上 3 个时间单位 -> J0_O1 在 M1 上 2 个时间单位
J1：J1_O0 在 M1 上 2 个时间单位 -> J1_O1 在 M0 上 4 个时间单位
```

手算最优 Cmax = 7：M0 上必须加工 3 + 4 = 7，所以 Cmax >= 7；下面这条时间线达到 7。

```text
M0: J0_O0 [0,3]  J1_O1 [3,7]
M1: J1_O0 [0,2]  J0_O1 [3,5]
```

脚本还打印一个「一个 job 做完再做下一个」的朴素排程（Cmax = 11）作为对照，
并对两个排程都跑一遍 M1 的独立验证器。

只打印，不写盘。
"""

import sys
from collections import Counter
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from opt_common.bridge import (
    Instance,
    Job,
    Machine,
    Operation,
    Schedule,
    ScheduledOperation,
    generate_instance,
    makespan,
    validate_schedule,
)
from opt_models.cpsat_models import build_cpsat_model, cpsat_jsp

PROTO_KINDS = (
    "all_diff", "at_most_one", "automaton", "bool_and", "bool_or", "bool_xor",
    "circuit", "cumulative", "dummy_constraint", "element", "exactly_one",
    "int_div", "int_mod", "int_prod", "interval", "inverse", "lin_max", "linear",
    "no_overlap", "no_overlap_2d", "reservoir", "routes", "table",
)


def jsp_instance() -> Instance:
    return Instance(
        (Job("J0", ("J0_O0", "J0_O1")), Job("J1", ("J1_O0", "J1_O1"))),
        (
            Operation("J0_O0", "J0", 3, ("M0",)),
            Operation("J0_O1", "J0", 2, ("M1",)),
            Operation("J1_O0", "J1", 2, ("M1",)),
            Operation("J1_O1", "J1", 4, ("M0",)),
        ),
        (Machine("M0", "M0"), Machine("M1", "M1")),
    )


def print_timeline(instance: Instance, schedule: Schedule) -> None:
    for machine in sorted({item.machine_id for item in schedule.operations}):
        rows = sorted(
            (item for item in schedule.operations if item.machine_id == machine),
            key=lambda item: item.start_time,
        )
        print(f"    {machine}: " + ", ".join(f"{r.operation_id}[{r.start_time},{r.end_time}]" for r in rows))


def main() -> None:
    instance = jsp_instance()

    print("=== 1. 固定路由：每道工序只有一个合格机器 ===")
    built = build_cpsat_model(instance, "makespan", prefer_fixed_route=True)
    proto = built.model.Proto()
    kinds = Counter(
        next(name for name in PROTO_KINDS if getattr(item, "has_" + name)())
        for item in proto.constraints
    )
    print(f"  presence 变量个数 = {len(built.presence)}（固定路由下不需要选机，一工序一区间）")
    print(f"  整数变量 {len(proto.variables)} 个 = 4 个 start + 4 个 end + 1 个 makespan")
    print(f"  约束 {len(proto.constraints)} 条：{dict(kinds)}")
    print("  即 4 条 interval（区间定义）+ 2 条 no_overlap（每台机器一条）")
    print("    + 2 条 linear（每个 job 一条 precedence）+ 1 条 lin_max（makespan 取各 end 的最大值）")

    print()
    print("=== 2. cpsat_jsp 求最优 ===")
    result = cpsat_jsp(instance, {"objective": "makespan", "time_limit": 5.0})
    validate_schedule(instance, result.schedule)
    print(f"  状态 {result.status}, Cmax = {makespan(instance, result.schedule)}, "
          f"bound = {result.best_bound}")
    print(f"  建模 {result.build_time:.4f} s / 求解 {result.solve_time:.4f} s / "
          f"分支 {result.iterations} / 冲突 {result.detail['conflicts']}")
    print_timeline(instance, result.schedule)
    print("  手算下界：M0 必须加工 3 + 4 = 7，所以 Cmax >= 7；上面的排程达到 7，证明最优。")

    print()
    print("=== 3. 对照：不用机器交替的朴素排程 ===")
    naive = Schedule(
        (
            ScheduledOperation("J0_O0", "M0", 0, 3),
            ScheduledOperation("J0_O1", "M1", 3, 5),
            ScheduledOperation("J1_O0", "M1", 5, 7),
            ScheduledOperation("J1_O1", "M0", 7, 11),
        )
    )
    validate_schedule(instance, naive)
    print("  先做完 J0 再做 J1：M1 在 [3,5] 做完 J0_O1 后空等到 5，才能开工 J1_O0。")
    print_timeline(instance, naive)
    print(f"  Cmax = {makespan(instance, naive)}（可行但不是最优，M1 上白白空等了 2 个单位时间）")

    print()
    print("=== 4. 多工序实例上的独立校验 ===")
    routes = generate_instance(54, jobs=6, machines=3, operations_per_job=2)
    routes_result = cpsat_jsp(routes, {"objective": "makespan", "time_limit": 5.0})
    validate_schedule(routes, routes_result.schedule)
    print(f"  generate_instance(seed=54, jobs=6, machines=3, operations_per_job=2)")
    print(f"  工序数 {len(routes.operations)}，状态 {routes_result.status}, "
          f"Cmax = {makespan(routes, routes_result.schedule)}, 分支 {routes_result.iterations}")
    print(f"  独立验证器通过：{len(routes_result.schedule.operations)} 道工序全部合法")
    for machine in sorted({item.machine_id for item in routes_result.schedule.operations}):
        load = sum(
            item.end_time - item.start_time
            for item in routes_result.schedule.operations
            if item.machine_id == machine
        )
        print(f"    {machine}: 负载 {load}")
    print("  该实例每道工序的合格机器是全部 3 台，所以 presence 变量非空：")
    built_routes = build_cpsat_model(routes, "makespan", prefer_fixed_route=True)
    print(f"    柔性路由下 presence 变量个数 = {len(built_routes.presence)}"
          f"（= 工序数 x 合格机器数 = {len(routes.operations)} x 3）")


if __name__ == "__main__":
    main()
