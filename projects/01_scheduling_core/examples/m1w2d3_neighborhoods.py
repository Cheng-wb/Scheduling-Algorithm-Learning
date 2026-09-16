"""swap / insert / reassign 邻域：示例、边界、去重与规模计数。

对应 Week 2 Day 3。脚本只打印，不写任何文件，输出确定。
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scheduling_algorithms.decoder import decode
from scheduling_algorithms.neighborhoods import insert, neighbors, reassign, swap
from scheduling_core.models import Instance, Job, Machine, Operation
from scheduling_core.objective import makespan, total_completion_time
from scheduling_core.schedule_validation import validate_schedule
from scheduling_core.solution import Candidate


def route_instance() -> Instance:
    """J0 = A(p=3, r=2) -> B(p=2)；J1 = C(p=1, r=0)。A 只能上 M0。"""
    return Instance(
        (Job("J0", ("A", "B"), 2), Job("J1", ("C",))),
        (
            Operation("A", "J0", 3, ("M0",)),
            Operation("B", "J0", 2, ("M0", "M1")),
            Operation("C", "J1", 1, ("M0", "M1")),
        ),
        (Machine("M0", "M0"), Machine("M1", "M1")),
    )


def permutation_instance(n: int) -> Instance:
    """n 个单工序作业、共用一台机器，用于只观察排列邻域。"""
    return Instance(
        tuple(Job(f"J{i}", (f"O{i}",)) for i in range(n)),
        tuple(Operation(f"O{i}", f"J{i}", 1, ("M0",)) for i in range(n)),
        (Machine("M0", "M0"),),
    )


def permutation_candidate(n: int) -> Candidate:
    order = tuple(chr(ord("A") + i) for i in range(n))
    return Candidate(order, ("M0",) * n)


def main() -> None:
    instance = route_instance()

    print("[1] ABCD 上的 swap 与 insert")
    base = permutation_candidate(4)
    print("  base order =", base.order)
    print("  swap(0,2)   =", swap(base, 0, 2).order, "（交换位置 0 与 2）")
    print("  insert(0,2) =", insert(base, 0, 2).order,
          "（把位置 0 的元素移到结果的第 2 位）")
    print("  insert(0,1) =", insert(base, 0, 1).order,
          "  swap(0,1) =", swap(base, 0, 1).order, "→ 相邻交换与 insert 重合")
    print("  swap 两次恢复 =", swap(swap(base, 0, 2), 0, 2) == base)
    print("  i == j 时返回等值候选解：",
          swap(base, 1, 1) == base, insert(base, 1, 1) == base)
    print("  机器指派不变：", swap(base, 0, 2).assignments == base.assignments,
          insert(base, 0, 2).assignments == base.assignments)

    print()
    print("[2] ABC 实例上的完整邻域（swap + insert + reassign）")
    candidate = Candidate(("A", "B", "C"), ("M0", "M1", "M0"))
    print("  当前解 order =", candidate.order,
          " assignments =", candidate.assignments)
    moved = list(neighbors(instance, candidate))
    print("  邻居数 =", len(moved), " 去重后 =", len(set(moved)),
          " 含自身 =", candidate in moved)
    for item in moved:
        validate_schedule(instance, decode(instance, item))
    print("  逐条邻居（扫描顺序）：")
    for item in moved:
        print(f"    order={','.join(item.order):<6}"
              f" assignments={','.join(item.assignments)}")
    order_only = [item for item in moved if item.assignments == candidate.assignments]
    print("  只改顺序的邻居 =", [",".join(item.order) for item in order_only],
          f"（{len(order_only)} 个）")
    reassigned = [item for item in moved if item.assignments != candidate.assignments]
    print("  只改指派的邻居 =",
          [",".join(item.assignments) for item in reassigned],
          f"（{len(reassigned)} 个，order 均为 A,B,C）")
    print("  每个邻居都能解码成可行排程。")

    print()
    print("[3] 边界与非法输入")
    attempts = (
        ("swap(-1, 0)", lambda: swap(candidate, -1, 0)),
        ("swap(0, 3)", lambda: swap(candidate, 0, 3)),
        ("insert(3, 0)", lambda: insert(candidate, 3, 0)),
        ("reassign(0, M1)", lambda: reassign(instance, candidate, 0, "M1")),
        ("reassign(3, M0)", lambda: reassign(instance, candidate, 3, "M0")),
        ("decode(order=A,A,C)",
         lambda: decode(instance, Candidate(("A", "A", "C"), ("M0", "M1", "M0")))),
    )
    for name, call in attempts:
        try:
            call()
        except (IndexError, ValueError) as error:
            print(f"  {name:<20} -> {type(error).__name__}: {error}")

    print()
    print("[4] 邻域规模：swap 与 insert 的数量关系")
    print("  n    swap   insert_raw  insert_uniq   union   naive_sum  overlap")
    formula = []
    for n in (3, 4, 5, 10, 20):
        base_n = permutation_candidate(n)
        swaps = {
            swap(base_n, i, j).order for i in range(n) for j in range(n)
        } - {base_n.order}
        inserts = {
            insert(base_n, i, j).order for i in range(n) for j in range(n)
        } - {base_n.order}
        union = swaps | inserts
        overlap = len(swaps) + len(inserts) - len(union)
        formula.append((n, len(swaps), len(inserts), len(union)))
        print(f"  {n:<4} {len(swaps):<7} {n * (n - 1):<12} {len(inserts):<13}"
              f"{len(union):<9}{n * (n - 1) // 2 + len(inserts):<11}{overlap}")
    for n, swap_count, insert_count, union_count in formula:
        assert swap_count == n * (n - 1) // 2
        assert insert_count == (n - 1) ** 2
        assert union_count == (n - 1) * (3 * n - 4) // 2
    print("  swap = n(n-1)/2；insert_raw = n(n-1) 个有向移动；")
    print("  insert_uniq = (n-1)^2；naive_sum 把两者直接相加，overlap = n-1；")
    print("  union = (n-1)(3n-4)/2，是 O(n^2) 而不是 n!-1。")
    for n, _, _, _ in formula[:2]:
        instance_n = permutation_instance(n)
        full = list(neighbors(instance_n, permutation_candidate(n)))
        print(f"  校验：neighbors() 在 n={n}、单机全资格实例上返回 {len(full)} 个邻居"
              f"（单机时 reassign 不产生新解）。")

    print()
    print("[5] 邻居的目标值与「选哪一个」")
    base_schedule = decode(instance, candidate)
    base_value = total_completion_time(instance, base_schedule)
    print("  当前解 ΣCj =", base_value,
          " Cmax =", makespan(instance, base_schedule))
    values = []
    for item in moved:
        value = total_completion_time(instance, decode(instance, item))
        values.append((item, value))
        mark = " <-- 严格改善" if value < base_value else ""
        print(f"    order={','.join(item.order):<6}"
              f" assignments={','.join(item.assignments)}  ΣCj={value}{mark}")
    best = min(value for _, value in values)
    improved = [(item, value) for item, value in values if value < base_value]
    winners = [item for item, value in values if value == best]
    print("  邻居中最小的 ΣCj =", best,
          f"，共 {len(improved)} 个邻居严格改善当前解。")
    print("  达到最小值的邻居 order =",
          [",".join(item.order) for item in winners])
    print(f"  best-improvement 与 first-improvement 在本例中都选 "
          f"{','.join(improved[0][0].order)}：")
    print("  它既是扫描中第一个严格改善的邻居，也是第一个达到最小值的邻居。")
    print("  但 CBA、BCA、CAB 的 ΣCj 相同，它们解码出的是同一个 Schedule")
    print("  —— 邻域里的「多个改善邻居」可能只是同一个时间表的重复表示。")

    print()
    print("[6] swap 与 insert 的确会重合")
    hits = []
    for i in range(4):
        for j in range(4):
            if i != j and insert(base, i, j).order == swap(base, i, j).order:
                hits.append((i, j))
    print("  ABCD 上 insert(i,j) == swap(i,j) 的位置对 =", hits)
    print("  这些正是相邻位置对 (0,1)、(1,2)、(2,3) 的两个方向，")
    print("  说明 swap 与 insert 的结果集合有交集，不能简单相加计数。")


if __name__ == "__main__":
    main()
