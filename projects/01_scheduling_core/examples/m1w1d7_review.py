"""M1W1D7 复盘：打印规则最优性表并验证四个失效反例。"""

import sys
from itertools import permutations
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scheduling_core.models import Instance, Job, Machine, Operation
from scheduling_core.objective import makespan, total_completion_time, total_tardiness
from scheduling_core.solution import Candidate
from scheduling_algorithms.decoder import decode
from scheduling_algorithms.oracle import exhaustive_optimum
from scheduling_algorithms.rules import edd, lpt, parallel_lpt, spt


def single(p, r=None, d=None, m=1):
    n = len(p)
    r = r or [0] * n
    d = d or [None] * n
    machine_ids = tuple(f"M{i}" for i in range(m))
    return Instance(
        tuple(Job(f"J{i}", (f"O{i}",), r[i], d[i], 1.0) for i in range(n)),
        tuple(
            Operation(f"O{i}", f"J{i}", value, machine_ids) for i, value in enumerate(p)
        ),
        tuple(Machine(mid, mid) for mid in machine_ids),
    )


def best_single_machine(instance, objective):
    ops = [op.id for op in instance.operations]
    return min(
        objective(instance, decode(instance, Candidate(order, ("M0",) * len(order))))
        for order in permutations(ops)
    )


def main() -> None:
    print("== Week 1 规则最优性表 ==")
    for rule, key, problem, status in [
        ("SPT", "p 升序", "1||ΣCj", "最优"),
        ("EDD", "d 升序", "1||Lmax", "最优"),
        ("WSPT", "p/w 升序", "1||ΣwjCj", "最优"),
        ("LPT(并行)", "p 降序 + 选最小负载机器", "P||Cmax", "启发式/近似"),
    ]:
        print(f"  {rule:10} {key:24} {problem:12} {status}")

    print("\n== 失效反例 ==")

    ce01 = single([100, 1], r=[0, 1])
    spt_c = total_completion_time(ce01, spt(ce01))
    opt_c = best_single_machine(ce01, total_completion_time)
    assert spt_c == 201 and opt_c == 104
    print(f"  CE-01 release-time SPT: non-delay ΣCj={spt_c} > 最优 {opt_c}")

    ce02 = single([1, 1, 3], d=[1, 3, 2])
    edd_t = total_tardiness(ce02, edd(ce02))
    opt_t = best_single_machine(ce02, total_tardiness)
    assert edd_t == 4 and opt_t == 3
    print(f"  CE-02 EDD vs ΣTj:      EDD ΣTj={edd_t} > 最优 {opt_t}")

    ce03 = single([3, 3, 2, 2, 2], m=2)
    lpt_m = makespan(ce03, parallel_lpt(ce03))
    opt_m, _, _ = exhaustive_optimum(ce03)
    assert lpt_m == 7 and opt_m == 6
    print(f"  CE-03 parallel LPT:    LPT Cmax={lpt_m} > 最优 {opt_m}")

    ce04 = single([6, 4, 2])
    spt_sum = total_completion_time(ce04, spt(ce04))
    lpt_sum = total_completion_time(ce04, lpt(ce04))
    assert spt_sum == 20 and lpt_sum == 28
    print(f"  CE-04 单机 LPT vs ΣCj:  SPT ΣCj={spt_sum} < LPT ΣCj={lpt_sum}")

    print("\n== 确定性契约 ==")
    print("  job 平局 -> job.id 升序；machine 平局 -> machine.id 升序")

    print("\n全部反例断言通过。")


if __name__ == "__main__":
    main()
