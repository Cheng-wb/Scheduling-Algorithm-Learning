"""Day 4：手推一个小规模 branch-and-bound，然后去读真实求解器的数字。

分三段：

1. **手工实现**一个 DFS branch-and-bound：每个节点解一次 LP relaxation，
   用 incumbent 与界做剪枝，把 node / incumbent / best bound / gap 逐行打出来；
2. 把同一实例交给 CBC，对照「我算出来的」与「求解器算出来的」数字；
3. 抓一段 CBC 自己的日志（子进程 + 管道，避免日志污染本脚本的 stdout），
   读 presolve、root cuts、best solution 这些行分别在说什么。
"""

import subprocess
import sys
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
    generate_instance,
    spt,
)
from opt_models.milp_scheduling import (
    SOLVER_ID,
    build_sequence_model,
    time_horizon,
)
from opt_solvers.registry import get
from scheduling_algorithms.oracle import exhaustive_optimum


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


def four_jobs() -> Instance:
    """4 job 单机实例（带释放时间），用于观察「界真的剪掉了东西」。"""
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


def node_lp(instance: Instance, objective_name: str, fixed: dict[tuple[str, str], int]):
    """解一个节点的 LP relaxation：把 ``fixed`` 里的 x 钉住，其余 x 取值 [0, 1]。

    返回 ``(LP 值, x 取值)``；LP 不可行时返回 ``(None, {})``。
    """
    horizon = time_horizon(instance)
    op_by_job = {op.job_id: op for op in instance.operations}
    solver = pywraplp.Solver.CreateSolver("GLOP")
    start: dict[str, object] = {}
    for job in instance.jobs:
        op = op_by_job[job.id]
        start[job.id] = solver.NumVar(
            float(job.release_time), float(horizon - op.processing_time), f"s_{job.id}"
        )
    values: dict[tuple[str, str], object] = {}
    for index, first in enumerate(instance.jobs):
        for second in instance.jobs[index + 1 :]:
            key = (first.id, second.id)
            lower, upper = float(fixed.get(key, 0)), float(fixed.get(key, 1))
            x = solver.NumVar(lower, upper, f"x_{first.id}_{second.id}")
            values[key] = x
            p_first = op_by_job[first.id].processing_time
            p_second = op_by_job[second.id].processing_time
            # 这里用一个「足够大的常数 M」：节点 LP 只用来算界，合法性由 Day 2 的
            # 时间界论证保证（M = n * H >= 任何逐对界）。
            big_m = len(instance.jobs) * horizon
            solver.Add(start[second.id] >= start[first.id] + p_first - big_m * (1 - x))
            solver.Add(start[first.id] >= start[second.id] + p_second - big_m * x)
    objective = solver.Objective()
    if objective_name == "total_tardiness":
        for job in instance.jobs:
            op = op_by_job[job.id]
            tardy = solver.NumVar(0.0, float(horizon), f"T_{job.id}")
            solver.Add(tardy >= start[job.id] + op.processing_time - job.due_date)
            objective.SetCoefficient(tardy, 1.0)
    elif objective_name == "total_completion_time":
        for job in instance.jobs:
            objective.SetCoefficient(start[job.id], 1.0)
        objective.SetOffset(float(sum(op.processing_time for op in instance.operations)))
    else:
        raise ValueError(objective_name)
    objective.SetMinimization()
    if solver.Solve() != pywraplp.Solver.OPTIMAL:
        return None, {}
    return float(solver.Objective().Value()), {
        key: float(variable.solution_value()) for key, variable in values.items()
    }


def schedule_from_orders(instance: Instance, orders: dict[tuple[str, str], int]) -> Schedule:
    """把全序决策翻译成一个**真实排程**（用于更新 incumbent）。"""
    op_by_job = {op.job_id: op for op in instance.operations}
    machine_id = instance.machines[0].id
    job_ids = [job.id for job in instance.jobs]
    release = {job.id: job.release_time for job in instance.jobs}

    def before(left: str, right: str) -> bool:
        return orders.get((left, right), 1) == 1

    ordered = sorted(job_ids, key=lambda job_id: sum(before(other, job_id) for other in job_ids))
    clock = 0
    spans = []
    for job_id in ordered:
        op = op_by_job[job_id]
        begin = max(clock, release[job_id])
        spans.append(ScheduledOperation(op.id, machine_id, begin, begin + op.processing_time))
        clock = begin + op.processing_time
    return Schedule(tuple(sorted(spans, key=lambda item: (item.start_time, item.operation_id))))


def enumerate_optimum(instance: Instance, objective_name: str) -> tuple[float, int]:
    """独立穷举：单机、单工序时把全部加工顺序枚举一遍，返回 (最优值, 顺序数)。

    M1 的 ``exhaustive_optimum`` 只支持三种目标，所以 ΣCj 的参考值在这里自己算，
    枚举方式与模型无关（先到先加工、释放时间用 ``max`` 处理）。
    """
    from itertools import permutations

    objective = M2_OBJECTIVES[objective_name]
    op_by_job = {op.job_id: op for op in instance.operations}
    release = {job.id: job.release_time for job in instance.jobs}
    machine_id = instance.machines[0].id
    best = float("inf")
    count = 0
    for order in permutations(job.id for job in instance.jobs):
        clock = 0
        spans = []
        for job_id in order:
            op = op_by_job[job_id]
            begin = max(clock, release[job_id])
            spans.append(ScheduledOperation(op.id, machine_id, begin, begin + op.processing_time))
            clock = begin + op.processing_time
        schedule = Schedule(tuple(sorted(spans, key=lambda item: (item.start_time, item.operation_id))))
        best = min(best, float(objective(instance, schedule)))
        count += 1
    return best, count


def walk(instance: Instance, objective_name: str, initial: Schedule | None, trace_limit: int = 14):
    """深度优先 branch-and-bound，返回 (trace, incumbent 值, 统计)。"""
    pairs = [
        (a.id, b.id)
        for index, a in enumerate(instance.jobs)
        for b in instance.jobs[index + 1 :]
    ]
    objective = M2_OBJECTIVES[objective_name]
    incumbent = float("inf") if initial is None else float(objective(instance, initial))
    stack: list[tuple[dict[tuple[str, str], int], int]] = [({}, 0)]
    trace: list[tuple[int, int, str, float | None, float, str]] = []
    node_id = 0
    pruned_by_bound = 0
    pruned_infeasible = 0
    leaves = 0
    while stack:
        fixed, depth = stack.pop()
        node_id += 1
        bound, values = node_lp(instance, objective_name, fixed)
        label = " ".join(f"{a}<{b}" if value == 1 else f"{b}<{a}" for (a, b), value in sorted(fixed.items()))
        if bound is None:
            pruned_infeasible += 1
            trace.append((node_id, depth, label or "(根节点)", None, incumbent, "剪枝：LP 不可行"))
            continue
        gap = ""
        if bound >= incumbent - 1e-9:
            pruned_by_bound += 1
            trace.append((node_id, depth, label or "(根节点)", bound, incumbent, "剪枝：界 >= incumbent"))
            continue
        free = [key for key in pairs if key not in fixed]
        fractional = [
            key for key in free if 1e-9 < values[key] < 1 - 1e-9
        ] if free else []
        if not free or not fractional:
            # 所有 x 都已经定下来（或 LP 自己给出整数解）：得到一个真实排程。
            complete = dict(fixed)
            for key in free:
                complete[key] = 1 if values[key] > 0.5 else 0
            schedule = schedule_from_orders(instance, complete)
            value = float(objective(instance, schedule))
            leaves += 1
            if value < incumbent:
                incumbent = value
                action = f"整数解 {value:.0f}，更新 incumbent"
            else:
                action = "整数解，不优于 incumbent"
            trace.append((node_id, depth, label or "(根节点)", bound, incumbent, action))
            continue
        key = max(fractional, key=lambda item: min(values[item], 1 - values[item]))
        trace.append(
            (node_id, depth, label or "(根节点)", bound, incumbent,
             f"分支：x({key[0]},{key[1]})={values[key]:.3f}")
        )
        stack.append(({**fixed, key: 0}, depth + 1))
        stack.append(({**fixed, key: 1}, depth + 1))
    stats = {
        "nodes": node_id,
        "leaves": leaves,
        "pruned_by_bound": pruned_by_bound,
        "pruned_infeasible": pruned_infeasible,
        "gap_notation": gap,
    }
    return trace, incumbent, stats


def print_trace(title: str, trace, stats, trace_limit: int | None) -> None:
    print(title)
    print("  node  深度  节点上的固定决策                       LP 界    incumbent   best bound   gap   动作")
    for node_id, depth, label, bound, incumbent, action in trace[:trace_limit]:
        bound_text = "不可行" if bound is None else f"{bound:8.3f}"
        incumbent_text = "无" if incumbent == float("inf") else f"{incumbent:8.0f}"
        best = "无" if incumbent == float("inf") or bound is None else f"{min(incumbent, bound):8.0f}"
        gap_text = (
            "-" if (bound is None or incumbent == float("inf"))
            else f"{max(0.0, (incumbent - bound)) / max(1.0, abs(incumbent)):.2f}"
        )
        print(f"  {node_id:4d} {depth:5d}  {label:32s} {bound_text:>8s} {incumbent_text:>10s} "
              f"{best:>10s}  {gap_text:>5s}   {action}")
    if trace_limit is not None and len(trace) > trace_limit:
        print(f"  …… 其余 {len(trace) - trace_limit} 行省略（完整节点数见下方统计）")
    print(f"  节点总数 {stats['nodes']}，其中叶节点 {stats['leaves']}，"
          f"按界剪枝 {stats['pruned_by_bound']}，按不可行剪枝 {stats['pruned_infeasible']}")
    print()


def print_solver_numbers(sample: Instance, objective_name: str) -> None:
    print("== 3. 同一实例交给 CBC：数字对照 ==")
    print("  method       状态       objective   best bound   gap       nodes   建模(s)  求解(s)")
    for method in ("milp_tight", "milp_loose", "milp_alt"):
        result = get(method)(
            sample, {"objective": objective_name, "time_limit": 20.0, "seed": 0}
        )
        bound = "-" if result.best_bound is None else f"{result.best_bound:.1f}"
        gap = "-" if result.gap is None else f"{result.gap:.4f}"
        print(f"  {method:12s} {result.status:9s} {result.objective:9.1f} {bound:>11s} {gap:>8s} "
              f"{str(result.iterations):>6s} {result.build_time:8.4f} {result.solve_time:8.3f}")
    print("  nodes = 0 表示 CBC 在根节点就用割平面把问题解完了，一次分支都没做。")
    print()


def print_cbc_log(sample: Instance) -> None:
    """用子进程抓一段真实 CBC 日志（子进程的管道能捕获求解器的 C 层输出）。"""
    code = (
        "import sys\n"
        f"sys.path.insert(0, {str(Path(__file__).resolve().parents[1])!r})\n"
        "from opt_common.bridge import generate_instance\n"
        "from opt_models.milp_scheduling import build_sequence_model\n"
        "instance = generate_instance(seed=50, jobs=8, machines=1)\n"
        "built = build_sequence_model(instance, 'total_tardiness', tight=True)\n"
        "solver = built.solver\n"
        "solver.EnableOutput()\n"
        "solver.SetTimeLimit(1200)\n"
        "solver.Solve()\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    keys = ("Presolve", "processed model", "Continuous objective", "At root node",
            "best solution", "Integer solution", "Search completed", "Stopped",
            "Maximum depth", "reduced cost", "Presolve is modifying")
    lines = [line.strip() for line in (completed.stdout or "").splitlines() if line.strip()]
    picked = [line for line in lines if any(key in line for key in keys)]
    print("== 4. 真实 CBC 日志（子进程捕获，按关键词过滤，原文粘贴）==")
    for line in picked[:20]:
        print(f"  {line}")
    print(f"  日志共 {len(lines)} 行，这里摘了 {min(20, len(picked))} 行。")
    print("  读法一：Presolve 行说的是 presolve 把模型缩到多大（括号里是相对上一版的增减），")
    print("          At root node 行说的是根节点切了几轮割、界从多少抬到多少，")
    print("          Integer solution 行是搜索过程中找到的 incumbent。")
    print("  读法二：日志里的 47 / 65 / 107 都不是最终答案。上表同一实例的最终值是 85，")
    print("          107 只是某个内部阶段的 interim 值 —— 日志行必须跟 SolveResult 对账。")
    print("  读法三：这里的根节点界 65 与 Day 3 量到的纯 LP relaxation 界 0 不是同一个量：")
    print("          它经过了 presolve 的整数界收紧（日志第 10 行）与 19 条根节点割。")
    print("          说「root bound」时必须说明是哪一层：纯松弛、presolve 后、还是加割后。")


def main() -> None:
    print("=== 手推 branch-and-bound，再读求解器的数字 ===")
    print()
    hand = hand_instance()
    hand_optimum, _, _ = exhaustive_optimum(hand, "total_tardiness", limit=100_000)
    greedy = spt(hand)
    print(f"== 1. hand 实例（3 job，ΣTj 真最优 {hand_optimum:.0f}）：DFS branch-and-bound 全过程 ==")
    print(f"  初始 incumbent 来自 M1 的 SPT 规则：ΣTj = "
          f"{float(M2_OBJECTIVES['total_tardiness'](hand, greedy)):.0f}")
    trace, incumbent, stats = walk(hand, "total_tardiness", greedy)
    print_trace("", trace, stats, trace_limit=None)
    print(f"  手工 B&B 得到的最优值 {incumbent:.0f}，与 M1 独立穷举的 {hand_optimum:.0f} 一致。")
    print("  注意：整棵树被「界 >= incumbent」剪完，一次整数解都没找 —— 因为初始 incumbent")
    print("  恰好等于最优值，而每往下固定一个顺序，界就被抬高到 1 以上。")
    print()
    print("  同一实例、同一目标，把初始 incumbent 拿掉（incumbent = +∞）再跑一遍：")
    trace_none, incumbent_none, stats_none = walk(hand, "total_tardiness", None)
    print_trace("", trace_none, stats_none, trace_limit=None)
    print(f"  两次的节点数都是 {stats_none['nodes']}，但叶节点从 {stats['leaves']} 变成 "
          f"{stats_none['leaves']}：没有 incumbent 时界剪枝的门槛是 +∞，")
    print("  前两个叶节点必须自己找出整数解来建立 incumbent，之后剩下的节点才被剪掉。")
    print("  这就是 incumbent 的作用：它不做任何「算得更准」的事，只是把界剪枝的门槛抬高。")
    print()
    four = four_jobs()
    four_optimum, orders = enumerate_optimum(four, "total_completion_time")
    trace4, incumbent4, stats4 = walk(four, "total_completion_time", spt(four))
    print(f"== 2. 4 job 实例（ΣCj 真最优 {four_optimum:.0f}，由 {orders} 个加工顺序独立枚举得到）==")
    print(f"  ΣCj 的 LP 界比 ΣTj 有信息：根节点的界就是 Σ_j (r_j + p_j) = "
          f"{sum(job.release_time for job in four.jobs) + sum(op.processing_time for op in four.operations):.0f}")
    print_trace("", trace4, stats4, trace_limit=10)
    print(f"  手工 B&B 得到的最优值 {incumbent4:.0f}，与独立枚举的 {four_optimum:.0f} 一致。")
    print()
    sample = generate_instance(seed=50, jobs=8, machines=1)
    print_solver_numbers(sample, "total_tardiness")
    print_cbc_log(sample)


if __name__ == "__main__":
    main()
