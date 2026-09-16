"""Day 7 复盘：把 Week 1 的失效反例编码成可执行断言。

每个反例验证「该规则在其经典模型之外不是最优」，而不是只验证规则能运行。
"""

from itertools import permutations

from scheduling_core.models import Instance, Job, Machine, Operation
from scheduling_core.objective import (
    makespan,
    total_completion_time,
    total_tardiness,
)
from scheduling_core.solution import Candidate
from scheduling_algorithms.decoder import decode
from scheduling_algorithms.oracle import exhaustive_optimum
from scheduling_algorithms.rules import edd, lpt, parallel_lpt, spt


def single(p, r=None, d=None, m=1):
    """构造单工序实例：p 为加工时间列表，r/d 可选，m 为机器数。"""
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


def _best_single_machine(instance, objective):
    """单机上枚举所有工序顺序，用 decode 解码，返回目标最小值。

    decode 按给定顺序左移排程（含为 release time 的空转），因此枚举全序
    就能覆盖「故意空转」这类 non-delay 规则做不到的排程。
    """
    ops = [op.id for op in instance.operations]
    return min(
        objective(instance, decode(instance, Candidate(order, ("M0",) * len(order))))
        for order in permutations(ops)
    )


def test_ce01_release_time_breaks_spt_optimality():
    instance = single([100, 1], r=[0, 1])
    non_delay = total_completion_time(instance, spt(instance))
    optimum = _best_single_machine(instance, total_completion_time)
    # non-delay SPT: A(0-100), B(100-101) → 201；故意空转: B(1-2), A(2-102) → 104
    assert non_delay == 201
    assert optimum == 104
    assert non_delay > optimum


def test_ce02_edd_not_optimal_for_total_tardiness():
    instance = single([1, 1, 3], d=[1, 3, 2])
    edd_value = total_tardiness(instance, edd(instance))
    optimum = _best_single_machine(instance, total_tardiness)
    # EDD: J0,J2,J1 → C=[1,4,5] → ΣT=4；J0,J1,J2 → C=[1,2,5] → ΣT=3
    assert edd_value == 4
    assert optimum == 3
    assert edd_value > optimum


def test_ce03_parallel_lpt_not_optimal():
    instance = single([3, 3, 2, 2, 2], m=2)
    lpt_value = makespan(instance, parallel_lpt(instance))
    optimum, _, _ = exhaustive_optimum(instance)
    # LPT: M0=3+2+2=7, M1=3+2=5 → 7；最优 M0=3+3=6, M1=2+2+2=6 → 6
    assert lpt_value == 7
    assert optimum == 6
    assert lpt_value > optimum


def test_ce04_single_lpt_worse_than_spt_for_sum_c():
    instance = single([6, 4, 2])
    spt_value = total_completion_time(instance, spt(instance))
    lpt_value = total_completion_time(instance, lpt(instance))
    # SPT: 2,4,6 → C=[2,6,12] → 20；LPT: 6,4,2 → C=[6,10,12] → 28
    assert spt_value == 20
    assert lpt_value == 28
    assert spt_value < lpt_value
