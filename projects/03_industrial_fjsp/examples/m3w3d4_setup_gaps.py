"""M3 Week 3 Day 4：sequence-dependent setup 怎么被建模成「间隔」。

换型时间不是工序的固有属性，它挂在**同一台机器上相邻两道工序**之间，
且依赖两者的 `family` 组合（`Setup(from_family, to_family, minutes)`）。
所以它既不是工时也不是等待，而是排程里一段**必须留出来的间隔**。

    python examples/m3w3d4_setup_gaps.py

三个实例，三件事：

1. `G1`（单机、两个族）：换型在时间线上就是一段间隔；同族相邻的间隔是 0。
   顺带验证单机恒等式 `Cmax = Σp + Σsetup`——它解释了为什么在单机上
   「换型最少」与「完工最早」永远选同一个顺序；
2. 「相邻对」与「任意前后对」的区别：把一个顺序下所有前后对都累加会**多算**，
   多算的量恰好是那些不相邻的组合。本节的 `naive_pairwise` 把这个多算量打出来；
3. `G2`（两台机器、`X` 可换机器）：`min Cmax` 与 `min setup` 选出**不同机器**，
   两条排程谁都不占优——这才是「换型要单独进目标」的硬证据。
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fjsp_core import (
    FJSPInstance,
    Job,
    Machine,
    Operation,
    Setup,
    objective_breakdown,
    total_setup_time,
)
from fjsp_shop.registry import get, load_week_modules

#: G1：单机、三工序、两个族。同族的 `B`/`C` 相邻时不需要换型。
#: 手算最优顺序 `A,B,C`：`A[0,2)` 空 3（F0->F1）`B[5,7)` 空 0（同族）`C[7,9)`。
G1 = FJSPInstance(
    jobs=(Job("J0", ("A",)), Job("J1", ("B",)), Job("J2", ("C",))),
    operations=(
        Operation("A", "J0", 0, (("M0", 2),), family="F0"),
        Operation("B", "J1", 0, (("M0", 2),), family="F1"),
        Operation("C", "J2", 0, (("M0", 2),), family="F1"),
    ),
    machines=(Machine("M0", "M0"),),
    setups=(Setup("F0", "F1", 3), Setup("F1", "F0", 4)),
)

#: G2：`X` 与 `A` 同族，插进 `M0` 不花换型，却会把 `Cmax` 顶高 1 分钟。
G2 = FJSPInstance(
    jobs=(Job("J0", ("A",)), Job("J1", ("B",)), Job("J2", ("X",))),
    operations=(
        Operation("A", "J0", 0, (("M0", 100),), family="F0"),
        Operation("B", "J1", 0, (("M1", 1),), family="F1"),
        Operation("X", "J2", 0, (("M0", 1), ("M1", 1)), family="F0"),
    ),
    machines=(Machine("M0", "M0"), Machine("M1", "M1")),
    setups=(Setup("F0", "F1", 5), Setup("F1", "F0", 5)),
)

SPEC_MAKESPAN = {"objective": "makespan", "time_limit": 5.0, "seed": 0}
SPEC_SETUP = {"objective": "total_setup_time", "time_limit": 5.0, "seed": 0}


def main() -> None:
    load_week_modules()

    print("== G1：单机、两族、换型 F0->F1 = 3、F1->F0 = 4 ==")
    result = get("fjsp_cpsat_setup")(G1, SPEC_SETUP)
    print(f"status={result.status}  objective(setup)={result.objective:g}  "
          f"breakdown={result.breakdown}")
    print(f"建模方式：{result.detail['setup_encoding']}")
    print()
    ordered = sorted(result.schedule.operations, key=lambda item: item.start_time)
    print("时间线（首字母 = 工序，'.' = 间隔）：")
    print("  M0 " + _bars(ordered))
    print()
    print(f"{'第几对':<8}{'前一道':<10}{'后一道':<10}{'族变化':<14}{'间隔':>6}")
    for index, (previous, current) in enumerate(zip(ordered, ordered[1:]), start=1):
        from_family = G1.operation(previous.operation_id).family
        to_family = G1.operation(current.operation_id).family
        gap_minutes = G1.setup_minutes(from_family, to_family)
        print(
            f"{index:<8}{previous.operation_id:<10}{current.operation_id:<10}"
            f"{from_family + ' -> ' + to_family:<14}{gap_minutes:>6}"
        )
    print(f"相邻对合计 = {total_setup_time(G1, result.schedule)}（求解器报的也是这个数）")

    print()
    print("== 为什么不能用「任意前后对」代替「相邻对」 ==")
    naive = _naive_pairwise(G1, ordered)
    adjacent = total_setup_time(G1, result.schedule)
    print(f"  同一顺序 {''.join(item.operation_id for item in ordered)}：")
    print(f"    相邻对累加（正确）   = {adjacent}")
    print(f"    任意前后对累加（错） = {naive}")
    print(f"    多算                 = {naive - adjacent}")
    print("    多出来的是不相邻的组合：")
    adjacent_pairs = {(i, i + 1) for i in range(len(ordered) - 1)}
    for i in range(len(ordered)):
        for j in range(i + 1, len(ordered)):
            if (i, j) in adjacent_pairs:
                continue
            left, right = ordered[i], ordered[j]
            from_family = G1.operation(left.operation_id).family
            to_family = G1.operation(right.operation_id).family
            minutes = G1.setup_minutes(from_family, to_family)
            if minutes:
                print(
                    f"      {left.operation_id}({from_family}) -> {right.operation_id}"
                    f"({to_family}) = {minutes}"
                    f"  —— 两者之间还隔着 {ordered[i + 1].operation_id}，不是相邻对"
                )
    print("  所以模型的换型项用**紧前工序**（circuit 弧）而不是成对的 before 变量：")
    print("  成对编码会让目标值大于 `objective_breakdown` 报的 `setup`，两套数就对不上了。")

    print()
    print("== 单机恒等式：Cmax = Σp + Σsetup ==")
    total_p = sum(G1.operation(item.operation_id).time_on("M0") for item in ordered)
    print(f"  Σp = {total_p}，Σsetup = {total_setup_time(G1, result.schedule)}，"
          f"和 = {total_p + total_setup_time(G1, result.schedule)}，"
          f"Cmax = {result.breakdown['cmax']:g}")
    print("  单机上工时总和是常数、换型只能往上加，所以「少换型」与「早完工」永远同向；")
    print("  想让换型真正改变决策，必须有多台机器可选（或别的会占用时间的约束）。")

    print()
    print("== G2：换型与完工时间真的打架 ==")
    by_cmax = get("fjsp_cpsat_setup")(G2, SPEC_MAKESPAN)
    by_setup = get("fjsp_cpsat_setup")(G2, SPEC_SETUP)
    print(f"{'目标':<18}{'Cmax':>7}{'ΣT':>6}{'setup':>7}   X 在哪台机器")
    for label, result in (("makespan", by_cmax), ("total_setup_time", by_setup)):
        parts = objective_breakdown(G2, result.schedule)
        machine = result.schedule.by_operation()["X"].machine_id
        print(
            f"{label:<18}{parts['cmax']:>7.0f}{parts['total_tardiness']:>6.0f}"
            f"{parts['setup']:>7.0f}   {machine}"
        )
    print()
    print("  手算两条排程：")
    print("    X 走 M1：B[0,1) 换型5 X[6,7)；M0 的 A[0,100) -> Cmax 100，setup 5")
    print("    X 走 M0：X[0,1) 同族不换型 A[1,101)；M1 的 B[0,1) -> Cmax 101，setup 0")
    print("  两条都不占优：`min Cmax` 拿 100 但要付 5 分钟换型，`min setup` 省下换型")
    print("  却要多等 1 分钟。**这就是 γ 必须由业务来定的原因**：")
    print("  加权和里 γ 取多少，等价于问「1 分钟换型值几分钟的完工时间」。")


def _bars(ordered: list) -> str:
    """把排程画成一行方框：工序用首字母，间隔用 `.`。"""
    end = max((item.end_time for item in ordered), default=0)
    cells = ["." for _ in range(end)]
    for item in ordered:
        for tick in range(item.start_time, item.end_time):
            cells[tick] = item.operation_id[0]
    return "".join(cells) + f"   (0 -> {end})"


def _naive_pairwise(instance: FJSPInstance, ordered: list) -> int:
    """**错误**做法：把同一台机器上所有「前后对」的换型都加起来。

    它把不相邻的组合也算进去了，所以一定 >= 相邻对之和。这里刻意把它实现出来，
    好让「多算了多少」变成一个能打印的数，而不是一句断言。
    """
    total = 0
    for i, left in enumerate(ordered):
        for right in ordered[i + 1 :]:
            total += instance.setup_minutes(
                instance.operation(left.operation_id).family,
                instance.operation(right.operation_id).family,
            )
    return total


if __name__ == "__main__":
    main()
