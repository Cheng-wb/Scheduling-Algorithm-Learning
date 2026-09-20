"""M3 Week 2 Day 3：三种机器指派策略 —— 随机 / 最短工时 / 负载均衡。

脚本做五件事：

```text
1. assign_2x3：三个策略各给一个指派，逐个手算对照 + 各自的 makespan
2. 逐步展开 assign_load_balance 的决策过程（每步的预计负载表）
3. 换到生成实例 fjsp_6x4_f2（18 道工序）：三个策略拉开多少
4. 随机策略的种子敏感性：seed 0~9 的目标值分布
5. 纪律复核：启发式的 best_bound 必须是 None、gap 必须是 None、排程必须合法
```

**控制变量**：三个策略共用同一个派工规则（非延迟 ECT），所以目标值的差异**只能**
来自「选机」这一步。

运行：``python examples/m3w2d3_assignments.py``
"""

import sys
from collections import Counter
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fjsp_core.models import FJSPInstance
from fjsp_core.schedule_validation import validate_schedule
from fjsp_io.generator import generate_instance
from fjsp_shop.fjsp import (
    assign_load_balance,
    assign_random,
    assign_shortest,
    dispatch,
    fjsp_loadbalance,
    fjsp_random,
    fjsp_shortest,
)
from fjsp_shop.toy_instances import TOY_INSTANCES

SPEC = {"objective": "makespan", "time_limit": 5.0, "seed": 0}


def makespan(schedule) -> int:
    return max(item.end_time for item in schedule.operations)


def nonzero_breakdown(result) -> dict[str, float]:
    """目标值分解里只保留非零分量：零分量对目标值没有贡献，打印出来只是噪声。"""
    return {key: value for key, value in result.breakdown.items() if value}


def machine_loads(instance: FJSPInstance, schedule) -> dict[str, int]:
    by_id = {op.id: op for op in instance.operations}
    loads = {machine.id: 0 for machine in instance.machines}
    for item in schedule.operations:
        loads[item.machine_id] += by_id[item.operation_id].time_on(item.machine_id)
    return loads


def line(instance: FJSPInstance, label: str, assignment: dict[str, str]) -> None:
    schedule = dispatch(instance, assignment)
    validate_schedule(instance, schedule)
    loads = machine_loads(instance, schedule)
    print(f"  {label:<16} makespan = {makespan(schedule):>2}   负载 = {loads}")
    print(f"    assignment = {dict(sorted(assignment.items()))}")


def main() -> None:
    three = TOY_INSTANCES["assign_2x3"]()

    print("=== 三种机器指派策略 ===")
    print()

    # ---------------------------------------------------------------- 1
    print("== 1. assign_2x3：同一个派工规则，只换指派 ==")
    printed = {
        "assign_shortest": assign_shortest(three),
        "assign_load_balance": assign_load_balance(three),
        "assign_random(0)": assign_random(three, 0),
    }
    for label, assignment in printed.items():
        line(three, label, assignment)
    print("  快速机器不等于好排程：shortest 把三道工序的最快选择都指向 M0/M1，")
    print("  结果 11；load_balance 反而更差（13）；随机一次就 14。")
    print("  更要紧的是负载栏：shortest 的总工时 = 6 + 8 = 14，")
    print("  load_balance 的总工时 = 9 + 4 + 9 = 22 —— 它为了「均衡」多花了 8 分钟的加工时间。")
    print("  makespan 是「最慢的那台机器做完」的时刻，不是总工时；两者不是一回事。")
    print()

    # ---------------------------------------------------------------- 2
    print("== 2. assign_load_balance 的逐步决策 ==")
    print("  顺序按 (-min_time, id)：长工序先放，短工序填空。")
    print("  每步比较「当前负载 + 在这台机器上的工时」，取最小者。")
    load = {machine.id: 0 for machine in three.machines}
    for op in sorted(three.operations, key=lambda item: (-item.min_time, item.id)):
        rows = sorted(
            (load[mid] + minutes, load[mid], mid, minutes) for mid, minutes in op.machine_times
        )
        table = "  ".join(
            f"{mid}:{current}+{minutes}={projected}"
            for projected, current, mid, minutes in rows
        )
        picked = rows[0][2]
        print(f"  {op.id}：{table}  -> 选 {picked}")
        load[picked] += op.time_on(picked)
    print(f"  最终负载 = {load}")
    print("  第 3 步是关键：O00 在 M0 上只要 3 分钟（比 M2 的 9 分钟快得多），")
    print("  但 M0 已经背了 6 分钟负载，所以「加进去之后 9 < 10」把 O00 推给了 M2。")
    print("  这是「局部最快」与「全局均衡」第一次分道扬镳。")
    print()

    # ---------------------------------------------------------------- 3
    print("== 3. 生成实例 fjsp_6x4_f2（seed 104，6 订单 x 3 工序，4 机器，flexibility=2）==")
    generated = generate_instance(
        seed=104, jobs=6, machines=4, operations_per_job=3, flexibility=2
    )
    print(f"  工序数 = {len(generated.operations)}，机器数 = {len(generated.machines)}，"
          f"每道工序的合格机器数 = {sorted(Counter(len(op.machine_times) for op in generated.operations).items())}")
    results = {}
    for name, solve in (
        ("fjsp_random", fjsp_random),
        ("fjsp_shortest", fjsp_shortest),
        ("fjsp_loadbalance", fjsp_loadbalance),
    ):
        result = solve(generated, SPEC)
        validate_schedule(generated, result.schedule)
        results[name] = result
        print(f"  {name:<16} objective = {result.objective:>3.0f}   "
              f"status = {result.status:<9} best_bound = {result.best_bound}")
        print(f"    build_time = {result.build_time:.6f}s   "
              f"solve_time = {result.solve_time:.6f}s   "
              f"breakdown（只列非零分量）= {nonzero_breakdown(result)}")
    best = min(result.objective for result in results.values())
    worst = max(result.objective for result in results.values())
    print(f"  三个启发式：最好 {best:.0f}，最差 {worst:.0f}，相差 {worst - best:.0f} 分钟"
          f"（{worst / best:.2f} 倍）。")
    print()

    # ---------------------------------------------------------------- 4
    print("== 4. 随机策略的种子敏感性（assign_2x3 与 fjsp_6x4_f2）==")
    for label, instance in (("assign_2x3", three), ("fjsp_6x4_f2", generated)):
        values = []
        for seed in range(10):
            result = fjsp_random(instance, {**SPEC, "seed": seed})
            validate_schedule(instance, result.schedule)
            values.append(int(result.objective))
        distinct = len(set(values))
        print(f"  {label:<12} seed 0~9 的目标值 = {values}")
        print(f"  {'':<12} 最好 {min(values)}，最差 {max(values)}，不同的取值有 {distinct} 个")
    print("  随机策略不是「随便」：同种子必须完全复现，这正是它作为基线的前提。")
    print()

    # ---------------------------------------------------------------- 5
    print("== 5. 纪律复核 ==")
    for name, result in results.items():
        assert result.best_bound is None, name
        assert result.gap is None, name
    print("  三个启发式的 best_bound 全是 None、gap 全是 None：")
    print("  没有下界就没有 gap，把目标值填进 best_bound 会让 gap 恒为 0，")
    print("  看上去像「已证明最优」—— 那是最严重的伪证据。")
    print("  所有排程的 validate_schedule 报错数 = 0（上面每个结果都验过一次）。")


if __name__ == "__main__":
    main()
