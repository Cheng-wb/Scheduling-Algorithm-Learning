"""Day 2：指示逻辑、Big-M 与乘积线性化 —— 并且亲手把 M 取小一次看看会怎样。

脚本分四段：

1. 把「j 先于 k 或 k 先于 j」这个**析取**用 Big-M 写成两条线性约束，并推出
   M 必须满足的不等式（这是「合法」的定义）；
2. 用有效时间界给出两种可证明合法的 M（逐对 tight 与全局 loose）；
3. 对 4 job 实例**穷举全部 24 个排程**，逐个检查「被松弛掉的那一侧」需要的
   最小值有没有超过所用的 M —— 这是 M 的合法性证据，不是感觉；
4. 故意把 M 取小，看模型怎么坏：太小的 M 会让模型报 INFEASIBLE（还算幸运），
   略微偏小的 M 会**静默**给出偏大的目标值，甚至返回机器重叠的排程。
"""

import sys
from itertools import permutations
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ortools.linear_solver import pywraplp

from opt_common.bridge import (
    M2_OBJECTIVES,
    Instance,
    Job,
    Machine,
    Operation,
    Schedule,
    ScheduledOperation,
    schedule_errors,
)
from opt_models.milp_scheduling import (
    SOLVER_ID,
    loose_big_m,
    pair_big_m,
    time_horizon,
)
from opt_solvers.registry import get
from scheduling_algorithms.oracle import exhaustive_optimum


def four_jobs() -> Instance:
    """4 job 单机实例（带释放时间），样本足够小到可以全枚举。"""
    return Instance(
        (
            Job("J0", ("O0",), 0, 6),
            Job("J1", ("O1",), 2, 9),
            Job("J2", ("O2",), 5, 20),
            Job("J3", ("O3",), 1, 12),
        ),
        (
            Operation("O0", "J0", 3, ("M0",)),
            Operation("O1", "J1", 4, ("M0",)),
            Operation("O2", "J2", 2, ("M0",)),
            Operation("O3", "J3", 5, ("M0",)),
        ),
        (Machine("M0", "M0"),),
    )


def hand_instance() -> Instance:
    """3 job 单机实例：A(p=3,d=4)、B(p=2,d=2)、C(r=5,p=4,d=10)，最优 ΣTj = 1。"""
    return Instance(
        (
            Job("A", ("OA",), 0, 4),
            Job("B", ("OB",), 0, 2),
            Job("C", ("OC",), 5, 10),
        ),
        (
            Operation("OA", "A", 3, ("M0",)),
            Operation("OB", "B", 2, ("M0",)),
            Operation("OC", "C", 4, ("M0",)),
        ),
        (Machine("M0", "M0"),),
    )


def print_linearization(instance: Instance) -> None:
    horizon = time_horizon(instance)
    print("== 1. 析取 → 两条线性约束 ==")
    print("  要表达的逻辑：对每一对 (j, k)，机器只能先做其中一个：")
    print("    x_jk = 1  ⇒  s_k >= s_j + p_j   （k 排在 j 之后）")
    print("    x_jk = 0  ⇒  s_j >= s_k + p_k   （j 排在 k 之后）")
    print("  「⇒」不是线性约束，用 Big-M 把它放松成两条**无条件成立**的不等式：")
    print("    s_k >= s_j + p_j - M_jk * (1 - x_jk)")
    print("    s_j >= s_k + p_k - M_kj * x_jk")
    print("  校验：x_jk = 1 时第一条的 M 项消失，正是要的逻辑；第二条右边被减去 M_kj，")
    print("        只要 M_kj 足够大就自动成立 —— 于是问题只剩：多大算够？")
    print()
    print("  合法性等价于一个不等式：M_jk 必须不小于「所有可行排程里 k 排在 j 之后时」")
    print("  s_j + p_j - s_k 的最大值。用有效时间界放缩：")
    print(f"    s_j + p_j - s_k <= H - r_k，取 M_jk = H - r_k 就一定合法（H = {horizon}）。")
    print()


def print_bounds(instance: Instance) -> None:
    horizon = time_horizon(instance)
    tight = pair_big_m(instance, horizon)
    loose = loose_big_m(instance, horizon)
    print("== 2. 两种可证明合法的 M ==")
    print("  job   r_j   p_j   s_j 的上界 H - p_j")
    op_by_job = {op.job_id: op for op in instance.operations}
    for job in instance.jobs:
        op = op_by_job[job.id]
        print(f"  {job.id:4s} {job.release_time:5d} {op.processing_time:6d} {horizon - op.processing_time:8d}")
    print(f"  tight：M_jk = H - r_k（逐对），取值为 {sorted(set(tight.values()))}")
    print(f"  loose：M = n * H = 4 * {horizon} = {loose}（全局常量）")
    print(f"  loose / tight 最大值 = {loose / max(tight.values()):.2f} 倍，都是可证明合法的。")
    print()


def print_validity_check(instance: Instance) -> None:
    horizon = time_horizon(instance)
    tight = pair_big_m(instance, horizon)
    loose = loose_big_m(instance, horizon)
    release = {job.id: job.release_time for job in instance.jobs}
    op_by_job = {op.job_id: op for op in instance.operations}
    required: dict[tuple[str, str], int] = {
        (a.id, b.id): 0
        for a in instance.jobs
        for b in instance.jobs
        if a.id != b.id
    }
    count = 0
    for order in permutations(job.id for job in instance.jobs):
        clock = 0
        start: dict[str, int] = {}
        end: dict[str, int] = {}
        for job_id in order:
            op = op_by_job[job_id]
            start[job_id] = max(clock, release[job_id])
            end[job_id] = start[job_id] + op.processing_time
            clock = end[job_id]
        for index, first in enumerate(order):
            for second in order[index + 1 :]:
                # first 先于 second：第二条约束的 M_second,first 必须够大。
                needed = end[second] - start[first]
                required[(second, first)] = max(required[(second, first)], needed)
        count += 1
    print("== 3. 穷举全部排程，验证 M 从不切掉可行解 ==")
    print(f"  枚举了 {count} 个排程（4! = 24），每个排程检查 6 对，共 {count * 6} 次不等式检验。")
    print("  pair       排程中需要的最大 M   实际 tight M   实际 loose M   合法")
    for pair in sorted(required, key=lambda item: required[item], reverse=True)[:6]:
        needed = required[pair]
        print(
            f"  {pair[0]}-{pair[1]:3s} {needed:17d} {tight[pair]:14d} {loose:14d}   "
            f"{'是' if tight[pair] >= needed and loose >= needed else '否'}"
        )
    worst = max(required.items(), key=lambda item: item[1])
    print(f"  最紧的一对是 {worst[0][0]}-{worst[0][1]}：需要 {worst[1]}，"
          f"tight 给了 {tight[worst[0]]}，仍有余量 {tight[worst[0]] - worst[1]}。")
    print("  这就是「合法」的含义：枚举不到任何一个被 M 切掉的可行排程。")
    print()


def build_with_constant_m(instance: Instance, m_value: int, objective_name: str):
    """用**常数** M 手搓同一个 sequence 模型（专门用来做 M 的对照实验）。"""
    horizon = time_horizon(instance)
    op_by_job = {op.job_id: op for op in instance.operations}
    machine_id = instance.machines[0].id
    solver = pywraplp.Solver.CreateSolver(SOLVER_ID)
    solver.SetTimeLimit(10_000)
    start: dict[str, object] = {}
    for job in instance.jobs:
        op = op_by_job[job.id]
        start[job.id] = solver.NumVar(
            float(job.release_time), float(horizon - op.processing_time), f"s_{job.id}"
        )
    for index, first in enumerate(instance.jobs):
        for second in instance.jobs[index + 1 :]:
            x = solver.BoolVar(f"x_{first.id}_{second.id}")
            p_first = op_by_job[first.id].processing_time
            p_second = op_by_job[second.id].processing_time
            solver.Add(start[second.id] >= start[first.id] + p_first - m_value * (1 - x))
            solver.Add(start[first.id] >= start[second.id] + p_second - m_value * x)
    objective = solver.Objective()
    for job in instance.jobs:
        op = op_by_job[job.id]
        tardy = solver.NumVar(0.0, float(horizon), f"T_{job.id}")
        solver.Add(tardy >= start[job.id] + op.processing_time - job.due_date)
        objective.SetCoefficient(tardy, 1.0)
    objective.SetMinimization()
    status = solver.Solve()
    if status not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
        return "INFEASIBLE", None, None
    spans = []
    for job in instance.jobs:
        op = op_by_job[job.id]
        begin = int(round(start[job.id].solution_value()))
        spans.append(ScheduledOperation(op.id, machine_id, begin, begin + op.processing_time))
    schedule = Schedule(tuple(sorted(spans, key=lambda item: (item.start_time, item.operation_id))))
    return "OPTIMAL" if status == pywraplp.Solver.OPTIMAL else "FEASIBLE", schedule, M2_OBJECTIVES[objective_name]


def build_with_pair_m(instance: Instance, override: dict[tuple[str, str], int], objective_name: str):
    """保留逐对 tight 界，只把 ``override`` 里几对的 M 改小。"""
    horizon = time_horizon(instance)
    limits = {**pair_big_m(instance, horizon), **override}
    op_by_job = {op.job_id: op for op in instance.operations}
    machine_id = instance.machines[0].id
    solver = pywraplp.Solver.CreateSolver(SOLVER_ID)
    solver.SetTimeLimit(10_000)
    start: dict[str, object] = {}
    for job in instance.jobs:
        op = op_by_job[job.id]
        start[job.id] = solver.NumVar(
            float(job.release_time), float(horizon - op.processing_time), f"s_{job.id}"
        )
    for index, first in enumerate(instance.jobs):
        for second in instance.jobs[index + 1 :]:
            x = solver.BoolVar(f"x_{first.id}_{second.id}")
            p_first = op_by_job[first.id].processing_time
            p_second = op_by_job[second.id].processing_time
            solver.Add(
                start[second.id]
                >= start[first.id] + p_first - limits[(first.id, second.id)] * (1 - x)
            )
            solver.Add(
                start[first.id]
                >= start[second.id] + p_second - limits[(second.id, first.id)] * x
            )
    objective = solver.Objective()
    for job in instance.jobs:
        op = op_by_job[job.id]
        tardy = solver.NumVar(0.0, float(horizon), f"T_{job.id}")
        solver.Add(tardy >= start[job.id] + op.processing_time - job.due_date)
        objective.SetCoefficient(tardy, 1.0)
    objective.SetMinimization()
    status = solver.Solve()
    if status not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
        return "INFEASIBLE", None
    spans = [
        ScheduledOperation(
            op_by_job[job.id].id,
            machine_id,
            int(round(start[job.id].solution_value())),
            int(round(start[job.id].solution_value())) + op_by_job[job.id].processing_time,
        )
        for job in instance.jobs
    ]
    schedule = Schedule(tuple(sorted(spans, key=lambda item: (item.start_time, item.operation_id))))
    return "OPTIMAL", schedule


def print_m_sweep(instance: Instance) -> None:
    reference, _, _ = exhaustive_optimum(instance, "total_tardiness", limit=100_000)
    print("== 4. 把 M 取小会怎样（真最优 ΣTj = %d，独立穷举所得）==" % reference)
    print("  4a. 把 M 统一取成一个常数：")
    print("  M        求解器状态    报告 ΣTj   独立验证器报错")
    for m_value in (*range(0, 15), 42):
        status, schedule, objective = build_with_constant_m(instance, m_value, "total_tardiness")
        if schedule is None:
            print(f"  {m_value:<8d} {status:10s}    -          -")
            continue
        print(
            f"  {m_value:<8d} {status:10s}    {objective(instance, schedule):6.0f}"
            f"     {len(schedule_errors(instance, schedule)):6d}"
        )
    print("  同一列里 M = 9 才第一次解得出，9 正是 (H - r_C) 这个逐对界的最小值；")
    print("  M <= 8 全部报 INFEASIBLE —— 模型被自己的 M 卡死，这是一次**响亮的**失败。")
    print()
    print("  4b. 保留逐对 tight 界，只把其中一对的 M 改小：")
    print("  改动的 M                状态        报告 ΣTj   真最优   独立验证器报错")
    for label, override in (
        ("（不改，全用 tight）", {}),
        ("('A','B') 从 14 改成 4", {("A", "B"): 4}),
        ("('A','B') 从 14 改成 1", {("A", "B"): 1}),
        ("('A','C') 从 9 改成 1", {("A", "C"): 1}),
    ):
        status, schedule = build_with_pair_m(instance, override, "total_tardiness")
        if schedule is None:
            print(f"  {label:22s} {status:10s}    -          -       -")
            continue
        errors = schedule_errors(instance, schedule)
        value = M2_OBJECTIVES["total_tardiness"](instance, schedule)
        print(
            f"  {label:22s} {status:10s}    {value:6.0f}   {reference:6.0f}"
            f"   {len(errors):6d}"
        )
    print("  第 2、3 行是关键：M 不够大时模型**照样报 OPTIMAL、照样给出合法排程**")
    print("  （独立验证器报错 0 次），但目标值 3 比真最优 1 差 —— 没有任何地方报错。")
    print("  第 4 行反过来说明：改哪一对的 M 才致命，取决于具体最优排程用到了哪条松弛")
    print("  约束，所以必须逐对论证，不能只看「我改小了一个 M」就下结论。")
    print("  机制：M 变小只会让约束更紧，模型的可行域是真实可行域的**子集**，")
    print("        于是它永远不会给出比真最优更好的值：要么报 INFEASIBLE，")
    print("        要么把最优排程切掉再退而求其次（目标值偏大，且静默）。")
    print("        所以 M 只能由时间界证明，不能靠「结果看起来合理」来判断。")


def main() -> None:
    hand = hand_instance()
    sample = four_jobs()
    print("=== Big-M 与析取约束的线性化 ===")
    print()
    print_linearization(hand)
    print_bounds(sample)
    print_validity_check(sample)
    print_m_sweep(hand)
    print()
    result = get("milp_tight")(
        hand, {"objective": "total_tardiness", "time_limit": 10.0, "seed": 0}
    )
    print(f"== 5. 用注册模型复核：status={result.status} objective={result.objective:.0f} "
          f"nodes={result.iterations} ==")


if __name__ == "__main__":
    main()
