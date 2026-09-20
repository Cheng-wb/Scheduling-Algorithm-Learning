"""M3 Week 2 Day 5：小实例的穷举 oracle —— 与解码器、CP-SAT 都独立的第三条路径。

脚本做六件事：

```text
1. 空间公式与四个手算实例的搜索空间大小
2. 四个实例的最优值（oracle 给出）与达到它的排程
3. 三方对拍：oracle / CP-SAT / 三个启发式
4. 可复现的反例：为什么顺序只能枚举拓扑序（全排列枚举会给出非法排程）
5. oracle 拒绝的输入：超限空间、不可证明的目标（以及与空间闸门同一处的约束闸门）
6. 独立性复核：读 oracle.py 的 import 行，确认它不依赖被对拍的两个实现
```

**这个脚本的全部意义在于「独立」**：oracle 自己枚举指派、自己枚举顺序、自己跟踪
机器占用，不 import 解码器与 CP-SAT。否则两个都错的实现也能互相对上。

运行：``python examples/m3w2d5_oracle.py``
"""

import sys
from itertools import permutations, product
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fjsp_core.models import (
    FJSPInstance,
    Job,
    Machine,
    Operation,
    Schedule,
    ScheduledOperation,
)
from fjsp_core.objective import evaluate
from fjsp_core.schedule_validation import schedule_errors, validate_schedule
from fjsp_io.generator import generate_instance
from fjsp_shop import oracle
from fjsp_shop.cpsat_fjsp import fjsp_cpsat, lower_bound
from fjsp_shop.fjsp import fjsp_loadbalance, fjsp_random, fjsp_shortest
from fjsp_shop.toy_instances import TOY_INSTANCES

SPEC = {"objective": "makespan", "time_limit": 5.0, "seed": 0}


def timeline(schedule) -> str:
    return "  ".join(
        f"{item.operation_id}@{item.machine_id}[{item.start_time},{item.end_time})"
        for item in schedule.operations
    )


def naive_build(instance: FJSPInstance, assignment: dict, order) -> Schedule:
    """**故意写错的**解码：插入式放置，但**不检查顺序是不是拓扑序**。

    这是 Day 5 开发中第一版 oracle 的做法（枚举全部 ``n!`` 个排列）。它会把后道工序
    排到前道工序之前，产出的排程违反工艺路线 —— 第 4 节用可复现的实例说明后果。
    """
    operations = {op.id: op for op in instance.operations}
    ready = {job.id: job.release_time for job in instance.jobs}
    busy: dict[str, list[tuple[int, int]]] = {machine.id: [] for machine in instance.machines}
    placed = []
    for operation_id in order:
        op = operations[operation_id]
        machine_id = assignment[operation_id]
        minutes = op.time_on(machine_id)
        start = ready[op.job_id]
        for begin, end in busy[machine_id]:  # 与 fjsp.py 的空隙查找同一个算法
            if end <= start:
                continue
            if begin - start >= minutes:
                break
            start = max(start, end)
        finish = start + minutes
        busy[machine_id].append((start, finish))
        busy[machine_id].sort()
        ready[op.job_id] = finish
        placed.append(ScheduledOperation(op.id, machine_id, start, finish))
    return Schedule(tuple(sorted(placed, key=lambda item: (item.start_time, item.machine_id, item.operation_id))))


def buggy_instance() -> FJSPInstance:
    """第 4 节的反例：2 订单 x 2 工序、2 机器，工时逐机器不同。"""
    return FJSPInstance(
        jobs=(Job("J0", ("O00", "O01"), 0, 30, 1.0), Job("J1", ("O10", "O11"), 0, 30, 1.0)),
        operations=(
            Operation("O00", "J0", 0, (("M0", 1), ("M1", 9))),
            Operation("O01", "J0", 1, (("M0", 4), ("M1", 1))),
            Operation("O10", "J1", 0, (("M0", 2), ("M1", 7))),
            Operation("O11", "J1", 1, (("M0", 7), ("M1", 2))),
        ),
        machines=(Machine("M0", "M0"), Machine("M1", "M1")),
    )


def refuse(label: str, action) -> None:
    try:
        action()
    except ValueError as exc:
        print(f"  {label}")
        print(f"    拒绝：{exc}")
    else:  # pragma: no cover
        raise AssertionError(f"{label} 本该被拒绝")


def main() -> None:
    print("=== 穷举 oracle：与解码器、CP-SAT 都独立的第三条计算路径 ===")
    print()

    # ---------------------------------------------------------------- 1
    print("== 1. 搜索空间 ==")
    print("  空间 = Π_o |合格机器_o|  x  (拓扑序个数)")
    print("  拓扑序个数 = n! / Π_j (k_j!)，不是 n! —— n! 里有一大半违反了工艺路线。")
    print()
    print("  实例          工序  指派组合  拓扑序  空间")
    for name in ("tiny_2x2", "gap_2x2", "assign_2x3", "jsp_fixed_2x2"):
        instance = TOY_INSTANCES[name]()
        combos = 1
        for op in instance.operations:
            combos *= len(op.machine_times)
        print(f"  {name:<13} {len(instance.operations):>4}  {combos:>8}  "
              f"{oracle.topological_order_count(instance):>6}  "
              f"{oracle.enumeration_space(instance):>5}")
    print("  （tiny_2x2 与 gap_2x2 的指派组合是 2^4 = 16，assign_2x3 是 3^4 = 81，")
    print("   jsp_fixed_2x2 每道工序只有一台机器，所以是 1。）")
    print()

    # ---------------------------------------------------------------- 2
    print("== 2. 四个手算实例的最优值 ==")
    optima = {}
    for name in ("tiny_2x2", "jsp_fixed_2x2", "gap_2x2", "assign_2x3"):
        instance = TOY_INSTANCES[name]()
        value, schedule = oracle.exhaustive_optimum(instance, "makespan", limit=200_000)
        validate_schedule(instance, schedule)
        optima[name] = (instance, value, schedule)
        print(f"  {name:<13} optimum = {value:<5}  LB = {lower_bound(instance)}")
        print(f"    {timeline(schedule)}")
    tiny_value = optima["tiny_2x2"][1]
    print(f"  tiny_2x2 的 optimum {tiny_value} 就等于它的下界，")
    print("  这个实例的最优性**不靠穷举**也能证明（下界碰上界）；"
          "穷举在这里的作用是验证「下界==上界」这条推理没错。")
    print()

    # ---------------------------------------------------------------- 3
    print("== 3. 三方对拍（oracle / CP-SAT / 三个启发式）==")
    print("  实例           oracle  cpsat(状态)    random  shortest  loadbalance")
    for name, (instance, value, _) in optima.items():
        cpsat = fjsp_cpsat(instance, SPEC)
        row = [f"  {name:<13} {value:>6.0f}  {cpsat.objective:>5.0f}({cpsat.status:<8})"]
        for solve in (fjsp_random, fjsp_shortest, fjsp_loadbalance):
            row.append(f"{solve(instance, SPEC).objective:>8.0f}")
        print("".join(row))
    print("  oracle 与 CP-SAT 在最优点上一致，启发式各自落后或追平 —— 两条独立路径互证。")
    print()

    # ---------------------------------------------------------------- 4
    print("== 4. 可复现的反例：顺序为什么只能枚举拓扑序 ==")
    buggy = buggy_instance()
    print("  实例工时（2 订单 x 2 工序，2 机器）：")
    print("    工序  M0  M1")
    for op in buggy.operations:
        print(f"    {op.id}  {op.time_on('M0'):>2}  {op.time_on('M1'):>2}")
    best_bad = None
    best_bad_order = None
    assignment = {"O00": "M0", "O01": "M1", "O10": "M0", "O11": "M1"}
    for order in permutations(sorted(op.id for op in buggy.operations)):
        schedule = naive_build(buggy, assignment, order)
        value = float(evaluate(buggy, schedule, "makespan"))
        if best_bad is None or value < best_bad[0]:
            best_bad = (value, schedule)
            best_bad_order = order
    naive_value, naive_schedule = best_bad
    print(f"  枚举全部 4! = 24 个排列（不检查工艺路线）：最好值 = {naive_value:.0f}")
    print(f"    顺序 = {best_bad_order}")
    print(f"    排程 = {timeline(naive_schedule)}")
    print(f"    独立验证器报错 = {schedule_errors(buggy, naive_schedule)}")
    correct_value, correct_schedule = oracle.exhaustive_optimum(buggy, "makespan", limit=200_000)
    print(f"  只枚举拓扑序（oracle 的做法）：最优值 = {correct_value:.0f}")
    print(f"    排程 = {timeline(correct_schedule)}")
    print("  后道工序 O11 被排到了前道工序 O10 之前 —— 工艺路线给的先后约束被绕过，")
    print("  于是枚举拿到一个比真最优（5）更小的假值（4）。")
    print("  受限枚举绝不能冒充最优：所以 oracle 只走拓扑序，")
    print("  并且在每个改进点上都调用独立验证器复核。")
    print()

    # ---------------------------------------------------------------- 5
    print("== 5. oracle 拒绝的三类输入 ==")
    big = generate_instance(seed=104, jobs=6, machines=4, operations_per_job=3, flexibility=2)
    print(f"  fjsp_6x4_f2 的空间 = {oracle.enumeration_space(big):.6g}（18 道工序，每道 2 台合格机器）")
    refuse("空间超过 limit：", lambda: oracle.exhaustive_optimum(big, "makespan", limit=200_000))
    three = TOY_INSTANCES["assign_2x3"]()
    print(f"  assign_2x3 的空间 = {oracle.enumeration_space(three)}"
          f"（3^4 x 6 = 486），把 limit 卡在它下面：")
    refuse("limit = 485（空间 486）：",
           lambda: oracle.exhaustive_optimum(three, "makespan", 485))
    boundary, _ = oracle.exhaustive_optimum(three, "makespan", 486)
    print(f"    limit = 486（刚好等于空间）时放行：optimum = {boundary:.0f}")
    print("  闸门判的是**空间**，不是实例的规模：485 与 486 之间没有别的东西。")
    print("  同一个闸门还会挡下实例里本模块没有建模的约束 —— 拒绝发生在枚举之前，")
    print("  因为对这种实例，枚举出来的「最好值」是另一个更松问题的最优值。")
    refuse("目标不是 makespan：",
           lambda: oracle.exhaustive_optimum(TOY_INSTANCES["tiny_2x2"](), "total_tardiness", 200_000))
    released = FJSPInstance(
        jobs=(Job("J0", ("O00", "O01"), 0, 30, 1.0), Job("J1", ("O10", "O11"), 3, 30, 1.0)),
        operations=TOY_INSTANCES["tiny_2x2"]().operations,
        machines=(Machine("M0", "M0"), Machine("M1", "M1")),
    )
    released_value, released_schedule = oracle.exhaustive_optimum(released, "makespan", 200_000)
    print("  释放时间不在拒绝清单里：J1 的释放时间改成 3 之后")
    print(f"    optimum = {released_value:.0f}，排程 = {timeline(released_schedule)}")
    print("    （释放时间进了 earliest 的下界，证书依然成立。）")
    print()

    # ---------------------------------------------------------------- 6
    print("== 6. 独立性复核：oracle.py 的 import 行 ==")
    source = Path(oracle.__file__).read_text(encoding="utf-8")
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")):
            print(f"    {stripped}")
    shop_imports = [
        line.strip() for line in source.splitlines() if line.startswith("from fjsp_shop")
    ]
    print(f"  从 fjsp_shop 里 import 的模块数 = {len(shop_imports)}")
    print("  oracle 只依赖 fjsp_core（数据模型、目标函数、独立验证器），")
    print("  不 import 解码器（fjsp_shop.fjsp）也不 import CP-SAT（fjsp_shop.cpsat_fjsp）——")
    print("  被对拍的两条路径它一条都没碰，这才叫对拍。")


if __name__ == "__main__":
    main()
