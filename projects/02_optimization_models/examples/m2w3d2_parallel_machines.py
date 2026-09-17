"""Day 2：用可选区间 + ExactlyOne + NoOverlap 表达并行机选择与互斥。

两个实例都来自 M1：

* ``p = [3,3,2,2,2]``、2 台机器：LPT 得 7，最优是 6（LPT 非最优的最小反例）；
* ``p = [8,7,6,5]``、2 台机器：下界 13，LPT 恰好达到下界。

脚本同时打印模型规模（布尔变量数、可选区间数），说明「选机」这件事在 CP-SAT
里就是一组布尔 ``presence``，机器互斥只需要每台机器一条 ``AddNoOverlap``。

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
    parallel_lpt,
    validate_schedule,
)
from opt_models.cpsat_models import build_cpsat_model, cpsat_parallel
from scheduling_algorithms.rules import parallel_makespan_lower_bound


def parallel_instance(times: list[int], machines: int) -> Instance:
    eligible = tuple(f"M{i}" for i in range(machines))
    return Instance(
        tuple(Job(f"J{index}", (f"J{index}_O0",)) for index in range(len(times))),
        tuple(
            Operation(f"J{index}_O0", f"J{index}", value, eligible)
            for index, value in enumerate(times)
        ),
        tuple(Machine(f"M{i}", f"M{i}") for i in range(machines)),
    )


def show(times: list[int], machines: int) -> None:
    instance = parallel_instance(times, machines)
    lower = parallel_makespan_lower_bound(instance)
    lpt_schedule = parallel_lpt(instance)
    lpt_value = makespan(instance, lpt_schedule)

    built = build_cpsat_model(instance, "makespan")
    constraint_count = len(built.model.Proto().constraints)

    result = cpsat_parallel(instance, {"objective": "makespan", "time_limit": 5.0})
    validate_schedule(instance, result.schedule)
    value = makespan(instance, result.schedule)

    print(f"实例 p={times}, {machines} 台机器")
    print(f"  模型规模：布尔 presence {len(built.presence)} 个，"
          f"CP-SAT 约束 {constraint_count} 条")
    print(f"  M1 下界 LB = {lower}（max(最长工序, ceil(总工时 / 机器数))）")
    print(f"  M1 parallel_lpt  -> Cmax = {lpt_value}"
          f"{'  （= LB，该实例上 LPT 已最优）' if lpt_value == lower else '  （> LB）'}")
    print(f"  cpsat_parallel   -> Cmax = {value}, 状态 {result.status}, "
          f"bound = {result.best_bound}, 分支 {result.iterations}, "
          f"冲突 {result.detail['conflicts']}")
    print(f"  建模 {result.build_time:.4f} s / 求解 {result.solve_time:.4f} s")
    for machine in sorted({item.machine_id for item in result.schedule.operations}):
        timeline = sorted(
            (item.operation_id, item.start_time, item.end_time)
            for item in result.schedule.operations
            if item.machine_id == machine
        )
        load = sum(end - start for _, start, end in timeline)
        print(f"    {machine}: " + ", ".join(f"{oid}[{s},{e}]" for oid, s, e in timeline)
              + f"  负载 {load}")
    print(f"  独立验证器：通过（{len(result.schedule.operations)} 道工序）")
    print()


def main() -> None:
    print("=== 1. LPT 非最优的最小反例 ===")
    show([3, 3, 2, 2, 2], 2)

    print("=== 2. 下界紧的实例 ===")
    show([8, 7, 6, 5], 2)

    print("=== 3. 选机是一次「恰好一个」的决策 ===")
    print("每道工序在每台合格机器上各有一个 OptionalIntervalVar，")
    print("AddExactlyOne 保证其中恰好一个 presence 成立，AddNoOverlap 保证")
    print("同一台机器上的区间不重叠。LPT 用「长任务先放」的贪心做同一个决策，")
    print("CP-SAT 则在同一组布尔变量上搜索并给出最优性证明。")


if __name__ == "__main__":
    main()
