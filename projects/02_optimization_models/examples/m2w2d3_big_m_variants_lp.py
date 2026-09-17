"""Day 3：由有效时间界构造两种合法 Big-M，并解 LP relaxation 读 root bound。

这一天的重点是**把两个问题分开**：

- 「M 合法吗」—— 由时间界证明，Day 2 已经做过；
- 「M 紧能提高松弛强度吗」—— 只能由 root LP bound 回答，本脚本负责测量。

做法：同一个实例上建两个只差 M 取法的模型，各自把二元变量放松成 ``[0, 1]``
的连续变量（约束结构一点不改），解 LP 得到 root bound；再把 LP 的最优解本身
打印出来，看看这个界为什么这么弱 —— 这一步比记住「松弛弱」有用得多。
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ortools.linear_solver import pywraplp

from opt_common.bridge import Instance, M2_OBJECTIVES, generate_instance
from opt_models.milp_scheduling import (
    loose_big_m,
    model_stats,
    pair_big_m,
    time_horizon,
    trivial_lower_bound,
)
from opt_solvers.registry import get

INSTANCES: tuple[tuple[str, dict[str, int]], ...] = (
    ("single_a", {"seed": 50, "jobs": 8, "machines": 1}),
    ("single_c", {"seed": 60, "jobs": 15, "machines": 1}),
)
OBJECTIVES = ("total_tardiness", "total_completion_time")


def relaxed_lp_solution(instance: Instance, objective_name: str, mode: str):
    """手工建**放松后**的 sequence 模型并解 LP，返回 (LP 值, s 取值, x 取值)。

    建模方式与 ``opt_models.milp_scheduling`` 完全一致，只是二元变量换成
    ``[0, 1]`` 连续变量 —— 这正是「只摘掉整数性、不动结构」的 LP relaxation。
    """
    horizon = time_horizon(instance)
    tight = pair_big_m(instance, horizon)
    loose = loose_big_m(instance, horizon)
    op_by_job = {op.job_id: op for op in instance.operations}
    solver = pywraplp.Solver.CreateSolver("GLOP")
    start: dict[str, object] = {}
    for job in instance.jobs:
        op = op_by_job[job.id]
        start[job.id] = solver.NumVar(
            float(job.release_time), float(horizon - op.processing_time), f"s_{job.id}"
        )
    pairs: dict[tuple[str, str], object] = {}
    for index, first in enumerate(instance.jobs):
        for second in instance.jobs[index + 1 :]:
            x = solver.NumVar(0.0, 1.0, f"x_{first.id}_{second.id}")
            pairs[(first.id, second.id)] = x
            p_first = op_by_job[first.id].processing_time
            p_second = op_by_job[second.id].processing_time
            m_fs = tight[(first.id, second.id)] if mode == "tight" else loose
            m_sf = tight[(second.id, first.id)] if mode == "tight" else loose
            solver.Add(start[second.id] >= start[first.id] + p_first - m_fs * (1 - x))
            solver.Add(start[first.id] >= start[second.id] + p_second - m_sf * x)
    objective = solver.Objective()
    if objective_name == "total_tardiness":
        for job in instance.jobs:
            op = op_by_job[job.id]
            variable = solver.NumVar(0.0, float(horizon), f"T_{job.id}")
            solver.Add(variable >= start[job.id] + op.processing_time - job.due_date)
            objective.SetCoefficient(variable, 1.0)
    elif objective_name == "total_completion_time":
        for job in instance.jobs:
            objective.SetCoefficient(start[job.id], 1.0)
        # Σ C_j = Σ (s_j + p_j)，建模时只写变量部分，常数部分用 offset 补上，
        # 这样 LP 值与注册模型报出的 bound 可以直接对照。
        objective.SetOffset(
            float(sum(op.processing_time for op in instance.operations))
        )
    else:
        raise ValueError(objective_name)
    objective.SetMinimization()
    status = solver.Solve()
    if status != pywraplp.Solver.OPTIMAL:
        raise RuntimeError(f"LP not optimal: {status}")
    # 解一次取干净：所有值都在求解后立刻读成 float，避免事后访问变量。
    value = float(solver.Objective().Value())
    starts = {job.id: float(start[job.id].solution_value()) for job in instance.jobs}
    values = {key: float(variable.solution_value()) for key, variable in pairs.items()}
    return value, starts, values


def print_time_bounds(instance: Instance) -> None:
    horizon = time_horizon(instance)
    op_by_job = {op.job_id: op for op in instance.operations}
    print("== 1. 有效时间界（M 与变量域的公共来源）==")
    print(f"  H = max_j r_j + sum_j p_j = {max(j.release_time for j in instance.jobs)} + "
          f"{sum(op.processing_time for op in instance.operations)} = {horizon}")
    print("  job     r_j   p_j   d_j    s_j 下界   s_j 上界 (H - p_j)")
    for job in instance.jobs:
        op = op_by_job[job.id]
        print(f"  {job.id:6s} {job.release_time:5d} {op.processing_time:5d} "
              f"{job.due_date:5d} {job.release_time:10d} {horizon - op.processing_time:14d}")
    print("  这两列就是变量域，同时也是「合法 M」的推导原料。")
    print()


def print_two_m(instance: Instance) -> None:
    horizon = time_horizon(instance)
    tight = pair_big_m(instance, horizon)
    loose = loose_big_m(instance, horizon)
    pairs = len(tight)
    print("== 2. 两种可证明合法的 M ==")
    print(f"  tight  逐对 M_jk = H - r_k：最小 {min(tight.values())}，最大 {max(tight.values())}，"
          f"和 {sum(tight.values())}")
    print(f"  loose  全局 M = n * H：{loose}")
    print(f"  M 的和之比 = {sum(tight.values()) / (pairs * loose):.3f}（loose 用同一个大数占满每个方向）")
    print(f"  最大逐对界与 loose 相差 {loose - max(tight.values())}，"
          f"但两者都满足 Day 2 证明的合法性不等式。")
    print()


def print_model_sizes(instances: dict[str, Instance]) -> None:
    print("== 3. 只换 M，模型结构一格没动 ==")
    print("  instance   method       变量  二元  约束  非零元   M 最小  M 最大   M 之和")
    for name, instance in instances.items():
        for method in ("milp_tight", "milp_loose"):
            stats = model_stats(instance, {"method": method, "objective": "total_tardiness"})
            print(
                f"  {name:10s} {method:11s} {stats['variables']:5d} {stats['binaries']:5d} "
                f"{stats['constraints']:5d} {stats['nonzeros']:7d} "
                f"{stats['big_m_min']:7d} {stats['big_m_max']:7d} {stats['big_m_sum']:8d}"
            )
    print("  变量数、约束数、非零元数**完全相同**，差别只在若干非零元的取值：")
    print("  所以「tight 与 loose 的差别」是纯粹的系数取值问题，没有结构差异。")
    print()


def print_root_bounds(instances: dict[str, Instance]) -> None:
    print("== 4. root LP bound：松弛强度指标 ==")
    print("  instance  objective                 milp_tight          milp_loose          相等")
    for name, instance in instances.items():
        for objective in OBJECTIVES:
            cells = {}
            for method in ("milp_tight", "milp_loose"):
                result = get(method)(
                    instance,
                    {"objective": objective, "time_limit": 60.0, "seed": 0, "root_lp": True},
                )
                cells[method] = result
            left, right = cells["milp_tight"], cells["milp_loose"]
            same = "是" if abs((left.best_bound or 0) - (right.best_bound or 0)) < 1e-9 else "否"
            print(
                f"  {name:9s} {objective:20s} {left.best_bound:10.4f} ({left.solve_time:.3f}s) "
                f"{right.best_bound:10.4f} ({right.solve_time:.3f}s)   {same}"
            )
            trivial = trivial_lower_bound(instance, objective)
            shown = "无（该目标没有一行式下界）" if trivial is None else f"{trivial}"
            print(f"            平凡下界（与求解器无关）：{shown}")
    print("  两个模型的状态都是 UNKNOWN：只有下界，没有可行排程可交。")
    print()


def print_lp_anatomy(instance: Instance) -> None:
    op_by_job = {op.job_id: op for op in instance.operations}
    print("== 5. LP 自己的最优解长什么样（为什么界这么弱）==")
    for objective in OBJECTIVES:
        value, starts, pairs = relaxed_lp_solution(instance, objective, "tight")
        fractional = sum(1 for item in pairs.values() if 1e-9 < item < 1 - 1e-9)
        at_release = sum(
            1 for job in instance.jobs if abs(starts[job.id] - job.release_time) < 1e-9
        )
        ideal = sum(
            job.release_time + op_by_job[job.id].processing_time for job in instance.jobs
        )
        print(f"  目标 {objective}：LP 值 {value:.2f}（Σ_j (r_j + p_j) = {ideal}）")
        print("  job     r_j   s_j(LP)   p_j   C_j(LP)    d_j   迟交(LP)")
        for job in instance.jobs:
            op = op_by_job[job.id]
            completion = starts[job.id] + op.processing_time
            print(f"  {job.id:6s} {job.release_time:5d} {starts[job.id]:9.3f} "
                  f"{op.processing_time:5d} {completion:8.3f} {job.due_date:6d} "
                  f"{max(0.0, completion - job.due_date):9.3f}")
        print(f"  在释放时间上就开工的 job：{at_release} / {len(instance.jobs)}，"
              f"分数取值的 x：{fractional} / {len(pairs)}")
        print()
    print("  读法（两段合起来看）：")
    print("  - 对 ΣC_j：LP 的最优解把每道工序都压到释放时间开工，值 = Σ_j (r_j + p_j)；")
    print("  - 对 ΣT_j：LP 只需「每道工序都不迟交」，值 = 0，正好是平凡下界；")
    print("  共同点：x_jk 取分数时两条 disjunctive 约束**同时被放松**（一侧减 M(1-x)，")
    print("  另一侧减 Mx），机器互斥在松弛里消失了 —— 松弛值于是塌到")
    print("  「只有释放时间、没有机器容量」的理想值。")
    print("  这就是改 M 的大小救不了它的原因：只要 M 大于重叠所需的那点余量，")
    print("  LP 就总能往这个方向跑。")
    print()


def main() -> None:
    instances = {name: generate_instance(**params) for name, params in INSTANCES}
    sample = instances["single_a"]
    print("=== 两种 Big-M 的合法性来源，以及它们的 LP relaxation ===")
    print()
    print_time_bounds(sample)
    print_two_m(sample)
    print_model_sizes(instances)
    print_root_bounds(instances)
    print_lp_anatomy(sample)
    print("== 6. 回到本日的两个问题 ==")
    print("  M 合法性：两种 M 都能由 H - r_k 的不等式证明，Day 2 已逐对验过。")
    print("  松弛强度：两个模型的 root bound 在以上实例上完全相同 —— 这是**实验观察**，")
    print("            不是「tight 一定不提高界」的定律；换成别的实例或别的模型形式，")
    print("            M 的取值仍可能通过分支定界的搜索路径影响结果。")
    print("  真正改变 root bound 的是变量定义（time-indexed 的 milp_alt），见 Day 6。")


if __name__ == "__main__":
    main()
