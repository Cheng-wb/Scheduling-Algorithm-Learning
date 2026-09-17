"""Day 7：把「模型快慢」拆成可以测量的三件事。

1. **规模**：变量/约束/非零元数怎么随时间界长大，建模要花多少时间；
2. **松弛强度**：root LP bound 离最优值有多远（这才是「松弛强弱」的定义）；
3. **约束表达方式**：换一种写法（补上 disjunction 等式、把 M 换成逐对最小可行值）
   能不能把松弛救回来 —— 这一条要真去测，不能靠想。

三张表用的是同一族实例（单机、total_tardiness、种子 50），
这样「差异」只来自模型与实例规模，不来自目标或数据分布。
"""

import sys
import time
from itertools import permutations
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ortools.linear_solver import pywraplp

from opt_common.bridge import Instance, generate_instance
from opt_models.milp_scheduling import (
    MAX_TIME_INDEXED_VARS,
    loose_big_m,
    model_stats,
    pair_big_m,
    time_horizon,
)
from opt_solvers.registry import available, get, load_week_modules

OBJECTIVE = "total_tardiness"
SIZES = (8, 12, 16, 20, 40)
SOLVE_SIZES = (8, 12, 16, 20)
BUDGET = 4.0


def print_scaling() -> None:
    print("== 表 A：模型规模随时间界的增长（只建模、不求解）==")
    print("  jobs    H     seq 变量  alt 变量   alt/seq   seq 约束  alt 约束   seq 建模(s)  alt 建模(s)")
    for jobs in SIZES:
        instance = generate_instance(seed=50, jobs=jobs, machines=1)
        horizon = time_horizon(instance)
        started = time.perf_counter()
        sequence = model_stats(instance, {"method": "milp_tight", "objective": OBJECTIVE})
        seq_build = time.perf_counter() - started
        started = time.perf_counter()
        alternative = model_stats(instance, {"method": "milp_alt", "objective": OBJECTIVE})
        alt_build = time.perf_counter() - started
        ratio = alternative["variables"] / sequence["variables"]
        print(f"  {jobs:4d} {horizon:5d} {sequence['variables']:9d} {alternative['variables']:9d} "
              f"{ratio:8.1f}  {sequence['constraints']:9d} {alternative['constraints']:9d} "
              f"{seq_build:11.4f} {alt_build:11.4f}")
    print(f"  alt 的变量数 ≈ Σ_工序 (时间窗长度)，随时间界 H 线性增长；")
    print(f"  模块里的规模闸门 MAX_TIME_INDEXED_VARS = {MAX_TIME_INDEXED_VARS}，超过就直接拒绝建模。")
    print()


def print_strength() -> None:
    print("== 表 B：root LP bound（松弛强度）与最优值的距离 ==")
    print("  jobs   seq root bound   alt root bound   最优值(来源)        alt bound / 最优   alt 状态")
    for jobs in SOLVE_SIZES:
        instance = generate_instance(seed=50, jobs=jobs, machines=1)
        sequence = get("milp_tight")(
            instance, {"objective": OBJECTIVE, "time_limit": 60.0, "seed": 0, "root_lp": True}
        )
        alternative = get("milp_alt")(
            instance, {"objective": OBJECTIVE, "time_limit": 60.0, "seed": 0, "root_lp": True}
        )
        solved = get("milp_alt")(
            instance, {"objective": OBJECTIVE, "time_limit": BUDGET, "seed": 0}
        )
        kind = "alt 证明" if solved.status == "OPTIMAL" else "alt 最好可行值"
        best = solved.objective
        ratio = "-" if not best else f"{alternative.best_bound / best * 100:.2f}%"
        print(f"  {jobs:4d} {sequence.best_bound:16.4f} {alternative.best_bound:16.4f} "
              f"{best:8.0f}（{kind}） {ratio:>16s}   {solved.status}")
    print("  seq 的 root bound 恒为 0（= 平凡下界）；alt 的 root bound 离最优只有零点几个百分点。")
    print(f"  alt 的求解预算 {BUDGET}s 内直接给出 OPTIMAL —— 强松弛省下的是整棵搜索树。")
    print()


def enumerate_min_valid_m(instance: Instance) -> tuple[dict[tuple[str, str], int], int]:
    """穷举全部加工顺序，算出每一对 (later, earlier) 的**最小可行** M。

    对 a 先于 b 的排程，约束 ``s_b >= s_a + p_a - M_ab`` 被放松成需要
    ``M_ab >= end_a - start_b``；把该值在所有排程上取最大，就得到 M_ab 的下确界。
    """
    op_by_job = {op.job_id: op for op in instance.operations}
    release = {job.id: job.release_time for job in instance.jobs}
    need = {
        (a.id, b.id): 0 for a in instance.jobs for b in instance.jobs if a.id != b.id
    }
    count = 0
    for order in permutations(job.id for job in instance.jobs):
        clock = 0
        starts: dict[str, int] = {}
        ends: dict[str, int] = {}
        for job_id in order:
            op = op_by_job[job_id]
            begins = max(clock, release[job_id])
            starts[job_id] = begins
            ends[job_id] = begins + op.processing_time
            clock = ends[job_id]
        for index, earlier in enumerate(order):
            for later in order[index + 1 :]:
                need[(later, earlier)] = max(need[(later, earlier)], ends[later] - starts[earlier])
        count += 1
    return need, count


def lp_bound_with_variants(instance: Instance, need: dict[tuple[str, str], int]) -> dict[str, float | None]:
    """在同一个 LP relaxation 上试几种「约束表达方式」，返回每个变体的界。"""
    horizon = time_horizon(instance)
    tight = pair_big_m(instance, horizon)
    loose = loose_big_m(instance, horizon)
    op_by_job = {op.job_id: op for op in instance.operations}
    variants: dict[str, tuple[bool, str]] = {
        "现状（tight Big-M）": (False, "tight"),
        "tight + disjunction 等式": (True, "tight"),
        "逐对最小可行 M": (False, "min"),
        "逐对最小可行 M + 等式": (True, "min"),
        "loose + 等式": (True, "loose"),
    }
    results: dict[str, float | None] = {}
    for label, (equality, mode) in variants.items():
        solver = pywraplp.Solver.CreateSolver("GLOP")
        start: dict[str, object] = {}
        for job in instance.jobs:
            op = op_by_job[job.id]
            start[job.id] = solver.NumVar(
                float(job.release_time), float(horizon - op.processing_time), f"s_{job.id}"
            )
        for index, first in enumerate(instance.jobs):
            for second in instance.jobs[index + 1 :]:
                x = solver.NumVar(0.0, 1.0, f"x_{first.id}_{second.id}")
                partner = solver.NumVar(0.0, 1.0, f"x_{second.id}_{first.id}")
                p_first = op_by_job[first.id].processing_time
                p_second = op_by_job[second.id].processing_time
                if mode == "loose":
                    m_fs = m_sf = float(loose)
                elif mode == "min":
                    m_fs = float(need[(first.id, second.id)])
                    m_sf = float(need[(second.id, first.id)])
                else:
                    m_fs = float(tight[(first.id, second.id)])
                    m_sf = float(tight[(second.id, first.id)])
                solver.Add(start[second.id] >= start[first.id] + p_first - m_fs * (1 - x))
                solver.Add(start[first.id] >= start[second.id] + p_second - m_sf * x)
                if equality:
                    solver.Add(x + partner == 1)
        objective = solver.Objective()
        for job in instance.jobs:
            op = op_by_job[job.id]
            tardy = solver.NumVar(0.0, float(horizon), f"T_{job.id}")
            solver.Add(tardy >= start[job.id] + op.processing_time - job.due_date)
            objective.SetCoefficient(tardy, 1.0)
        objective.SetMinimization()
        status = solver.Solve()
        results[label] = (
            float(solver.Objective().Value()) if status == pywraplp.Solver.OPTIMAL else None
        )
    return results


def print_expression_experiment() -> None:
    instance = generate_instance(seed=50, jobs=8, machines=1)
    horizon = time_horizon(instance)
    tight = pair_big_m(instance, horizon)
    need, orders = enumerate_min_valid_m(instance)
    print("== 表 C：换个写法能把 LP 松弛救回来吗（8 job 实例）==")
    print(f"  先把「合法 M 的下确界」用穷举算出来（{orders} 个加工顺序）：")
    print(f"    逐对最小可行 M ∈ [{min(need.values())}, {max(need.values())}]，"
          f"而 tight 逐对界 ∈ [{min(tight.values())}, {max(tight.values())}]")
    print(f"    单道工序的最大加工时间 = "
          f"{max(op.processing_time for op in instance.operations)}")
    results = lp_bound_with_variants(instance, need)
    print("  变体                          root LP bound")
    for label, value in results.items():
        shown = "-" if value is None else f"{value:.4f}"
        print(f"    {label:28s}  {shown}")
    print("  五种写法全部是 0：M 取到「可证明的最小值」、再补上 disjunction 等式，")
    print("  都挡不住 LP 用 x = 0.5 让两条约束各放松 M/2 —— 而 M/2 仍远大于任何一道")
    print("  工序的加工时间，于是所有工序依旧能重叠。松弛弱的是 formulation 的**结构**，")
    print("  不是某个系数写得不够紧。")
    print()


def main() -> None:
    load_week_modules()
    for name in ("milp_tight", "milp_loose", "milp_alt"):
        if name not in available():
            raise SystemExit(f"未注册的方法：{name}")
    print("=== 为什么有的模型快、有的模型慢：三个可测量的原因 ===")
    print()
    print_scaling()
    print_strength()
    print_expression_experiment()
    print("== 小结：把「快」拆成三句话 ==")
    print("  1. 规模：sequence 模型的变量是 O(n^2)（每对一个 x），time-indexed 是 O(n·H)；")
    print("     实例一大，后者的建模成本与内存会先碰到天花板。")
    print("  2. 松弛：root LP bound 离最优有多远，决定了搜索树有多大；")
    print("     在这族实例上 sequence 模型的界恒为 0，搜索只能在整棵树上跑。")
    print("  3. 表达方式：换系数的紧度（Big-M）不改变松弛强度，换变量定义才改变。")
    print("  选模型时的顺序应该是：先看时间界 H 与 job 数 n 落在哪个规模区间，")
    print("  再看目标函数对松弛是否友好（tardiness 对完工时间的依赖是分段线性的），")
    print("  最后才去调 M 这类系数。")


if __name__ == "__main__":
    main()
