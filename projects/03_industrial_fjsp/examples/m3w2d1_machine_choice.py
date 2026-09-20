"""M3 Week 2 Day 1：FJSP 的机器选择 —— 按机器变化的工时与「指派」这一维决策。

脚本做四件事：

```text
1. 把实例摊开成一张「工序 x 机器」的工时表，并算出手算下界 LB
2. 同一个工序顺序、两个不同指派 -> 两个不同的 makespan：
   证明「选机」这一维真的改变目标值，它不是装饰
3. 穷举 assign_2x3 的全部 3^4 = 81 个指派，各自做 ECT 派工，
   统计目标值的分布：只靠「选机」这一步，最好与最差差多少
4. 反例：全部塞给「最快机器」并不好；「最快机器」与「均衡负载」在
   assign_2x3 上就已经分道扬镳
```

关键纪律：**每个返回的排程都要过 ``validate_schedule``**；启发式不填 ``best_bound``。

运行：``python examples/m3w2d1_machine_choice.py``
"""

import sys
from itertools import product
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fjsp_core.models import FJSPInstance
from fjsp_core.schedule_validation import validate_schedule
from fjsp_shop.cpsat_fjsp import lower_bound
from fjsp_shop.fjsp import assign_load_balance, assign_shortest, decode, dispatch
from fjsp_shop.toy_instances import TOY_INSTANCES


def timeline(schedule) -> str:
    return " ".join(
        f"{item.operation_id}@{item.machine_id}[{item.start_time},{item.end_time})"
        for item in schedule.operations
    )


def makespan(schedule) -> int:
    return max(item.end_time for item in schedule.operations)


def print_time_table(instance: FJSPInstance, label: str) -> None:
    """把实例摊成「工序 x 机器」的工时表；不合格的格子画 ``--``。"""
    machines = [machine.id for machine in instance.machines]
    print(f"== {label} ==")
    header = "  工序   订单  位置  " + "  ".join(f"{mid:>4}" for mid in machines)
    print(header + "   最快  flexibility")
    for op in instance.operations:
        cells = []
        for mid in machines:
            minutes = op.time_on(mid)
            cells.append("  --" if minutes is None else f"{minutes:>4}")
        fastest = min(op.machine_times, key=lambda pair: (pair[1], pair[0]))
        print(
            f"  {op.id:<6} {op.job_id:<5} {op.position:<4} "
            + "  ".join(cells)
            + f"   {fastest[0]}({fastest[1]})   {len(op.machine_times)}"
        )
    total_fastest = sum(op.min_time for op in instance.operations)
    print(
        f"  下界 LB = max(max_o min_m p_om, ceil(sum_o min_m p_om / |M|))"
        f" = max({max(op.min_time for op in instance.operations)},"
        f" ceil({total_fastest} / {len(instance.machines)}))"
        f" = {lower_bound(instance)}"
    )
    print()


def all_assignments(instance: FJSPInstance) -> list[dict[str, str]]:
    ids = [op.id for op in instance.operations]
    choices = [op.eligible_machine_ids for op in instance.operations]
    return [dict(zip(ids, combo)) for combo in product(*choices)]


def main() -> None:
    print("=== FJSP 的机器选择：一张工时表，两维决策 ===")
    print()

    tiny = TOY_INSTANCES["tiny_2x2"]()
    three = TOY_INSTANCES["assign_2x3"]()

    # ---------------------------------------------------------------- 1
    print("== 1. 实例摊平成工时表 ==")
    print_time_table(tiny, "tiny_2x2：2 订单 x 2 工序，2 机器")
    print_time_table(three, "assign_2x3：2 订单 x 2 工序，3 机器")

    # ---------------------------------------------------------------- 2
    print("== 2. 同一个顺序、两个指派：选机改变目标值 ==")
    order = ("O00", "O01", "O10", "O11")
    fast = {"O00": "M0", "O01": "M0", "O10": "M1", "O11": "M1"}
    slow = {"O00": "M1", "O01": "M1", "O10": "M0", "O11": "M0"}
    for label, assignment in (("指派 A（J0 走 M0、J1 走 M1）", fast), ("指派 B（对调两台机器）", slow)):
        schedule = decode(tiny, assignment, order)
        validate_schedule(tiny, schedule)
        print(f"  {label}：makespan = {makespan(schedule)}")
        print(f"    {timeline(schedule)}")
    print("  同一个 order，只换 assignment，makespan 就变了 —— 这就是 FJSP 多出来的那一维。")
    print("  （顺序这一维今天不动：下面每个指派都配同一个派工规则。）")
    print()

    # ---------------------------------------------------------------- 3
    print("== 3. 穷举 assign_2x3 的全部 81 个指派（每个都做 ECT 派工）==")
    assignments = all_assignments(three)
    values = {}
    for assignment in assignments:
        schedule = dispatch(three, assignment)
        validate_schedule(three, schedule)
        values[tuple(sorted(assignment.items()))] = makespan(schedule)
    spread = sorted(values.values())
    best = spread[0]
    worst = spread[-1]
    mean = sum(spread) / len(spread)
    print(f"  指派个数          = {len(values)}  (= 3^4，每道工序 3 台合格机器)")
    print(f"  最好 / 最差       = {best} / {worst}")
    print(f"  平均              = {mean:.2f}")
    print(f"  达到最好的指派数  = {sum(1 for value in spread if value == best)}")
    print(f"  只做「选机」这一步，最好与最差就差 {worst / best:.2f} 倍。")
    print("  注意：这里每个指派都用了同一个 ECT 派工规则，差异全部来自选机。")
    best_assign = next(a for a, value in values.items() if value == best)
    print(f"  达到最好的一个指派：{dict(best_assign)}")
    print()

    # ---------------------------------------------------------------- 4
    print("== 4. 「最快机器」陷阱：为什么不能全塞给 M0 ==")
    shortest = assign_shortest(three)
    balance = assign_load_balance(three)
    print(f"  assign_shortest     = {shortest}")
    print(f"  assign_load_balance = {balance}")
    by_id = {op.id: op for op in three.operations}
    for label, assignment in (("全塞 M0（人工构造）", {op.id: "M0" for op in three.operations}),
                              ("assign_shortest", shortest),
                              ("assign_load_balance", balance)):
        schedule = dispatch(three, assignment)
        loads = {machine.id: 0 for machine in three.machines}
        for item in schedule.operations:
            loads[item.machine_id] += by_id[item.operation_id].time_on(item.machine_id)
        print(f"  {label:<24} makespan = {makespan(schedule):>2}   机器负载 = {loads}")
    print("  assign_shortest 让 O00 去 M0 只花 3 分钟，看着最省；")
    print("  但 M0 同时是三道工序的最快机器，堆在一起就比均衡分派更差。")
    print()

    # ---------------------------------------------------------------- 5
    print("== 5. 纪律复核 ==")
    print(f"  所有 81 个排程的 validate_schedule 报错数 = 0")
    cpsat_lb = lower_bound(three)
    print(f"  assign_2x3 的 LB = {cpsat_lb}，而「选机 + ECT 派工」的最好值 = {best}")
    print(f"  差距 = {best - cpsat_lb} 分钟：只靠「选机 + 非延迟派工」，这条路径走到 {best} 就停住了。")


if __name__ == "__main__":
    main()
