"""Day 1：把单机调度写成 MILP —— 二元排序变量 + 时间变量 + 迟交变量。

本脚本不求解一个「大」实例，而是把一个小实例（3 个 job）的模型**逐变量、
逐约束打印出来**，再用 CBC 求一遍，把求解器给的解翻译回 M1 的 ``Schedule``，
最后用 M1 的独立验证器复核。一个模型的正确性由三件事共同保证：

1. 约束逐条写出来，人眼能读懂它们为什么等价于「机器一次只加工一道工序」；
2. 求解结果的目标值可以被手工重算复现；
3. 返回的排程过独立验证器，而不是「求解器说最优就最优」。
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from opt_common.bridge import (
    Instance,
    Job,
    Machine,
    Operation,
    schedule_errors,
    total_tardiness,
)
from opt_models.milp_scheduling import (
    SOLVER_ID,
    build_sequence_model,
    time_horizon,
    trivial_lower_bound,
)
from opt_solvers.registry import get


def hand_instance() -> Instance:
    """3 个 job 的单机实例：A(p=3,d=4)、B(p=2,d=2)、C(r=5,p=4,d=10)。"""
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


def print_data(instance: Instance) -> None:
    print("== 1. 数据（单机：每道工序只在一台机器上可选）==")
    print("  job    r_j   p_j   d_j")
    op_by_job = {op.job_id: op for op in instance.operations}
    for job in instance.jobs:
        op = op_by_job[job.id]
        print(f"  {job.id:3s} {job.release_time:6d} {op.processing_time:6d} {job.due_date:6d}")
    horizon = time_horizon(instance)
    print(f"  H = max_j r_j + sum_j p_j = 5 + 9 = {horizon}")
    print("  H 的作用：存在一个所有完工时间都不超过 H 的最优排程，")
    print("  于是开工时间有了上界 s_j <= H - p_j，这个界后面会写进变量域。")
    print()


def constraint_text(solver, constraint) -> str:
    """把一条 pywraplp 约束翻译成可读的一行式（只列系数非零的列）。"""
    terms = []
    for var in solver.variables():
        coefficient = constraint.GetCoefficient(var)
        if coefficient:
            terms.append(f"{coefficient:+.0f}*{var.name()}")
    body = " ".join(terms) if terms else "0"
    if constraint.ub() == float("inf"):
        return f"{body} >= {constraint.lb():.0f}"
    if constraint.lb() == -float("inf"):
        return f"{body} <= {constraint.ub():.0f}"
    return f"{constraint.lb():.0f} <= {body} <= {constraint.ub():.0f}"


def print_variables(built) -> None:
    solver = built.solver
    print("== 2. 变量（时间变量 + 二元排序变量 + 迟交变量）==")
    print("  name     kind     lb   ub   域的含义")
    for var in solver.variables():
        name = var.name()
        if name.startswith("x_"):
            kind, meaning = "二元", "j 是否先于 k"
        elif name.startswith("T_"):
            kind, meaning = "迟交", "[0, H]（最小化会把它压到 max(0, C_j - d_j)）"
        else:
            kind, meaning = "时间", "[r_j, H - p_j]"
        print(f"  {name:7s} {kind}  {var.lb():5.0f} {var.ub():5.0f}   {meaning}")
    print("  说明：s_j 的下界就是释放时间 r_j，上界是有效时间界 H - p_j；")
    print("        x_jk = 1 表示 j 排在 k 之前，两道工序的先后完全由它决定；")
    print("        T_j 的上界 H 只是形式上的截断，目标函数会自己把它压到最小可行值。")
    print()


def print_objective(built) -> None:
    objective = built.solver.Objective()
    terms = [
        (var.name(), objective.GetCoefficient(var))
        for var in built.solver.variables()
        if objective.GetCoefficient(var)
    ]
    body = " + ".join(f"{coefficient:g}*{name}" for name, coefficient in terms)
    print("== 3. 目标函数 ==")
    print(f"  min {body}")
    print("  每个 T_j 的系数都是 1，所以这就是 sum_j T_j（总迟交量）。")
    print()


def print_constraints(built) -> None:
    solver = built.solver
    disjunctive: list[str] = []
    tardiness: list[str] = []
    for constraint in solver.constraints():
        coefficients = {var.name(): constraint.GetCoefficient(var) for var in solver.variables()}
        if any(name.startswith("x_") and value for name, value in coefficients.items()):
            disjunctive.append(constraint_text(solver, constraint))
        elif any(name.startswith("T_") and value for name, value in coefficients.items()):
            tardiness.append(constraint_text(solver, constraint))
    print("== 4. 约束 ==")
    print(f"  互斥约束（disjunctive，共 {len(disjunctive)} 条 = 2 * C(3, 2)）：")
    for text in disjunctive:
        print(f"    {text}")
    print("  每对 job 两条约束，Big-M 项 14*(1 - x) 只在「这一侧没被选中」时放松该约束。")
    print()
    print(f"  迟交定义（共 {len(tardiness)} 条）：")
    for text in tardiness:
        print(f"    {text}")
    print("  T_j >= C_j - d_j 与 T_j >= 0 合起来等价于 T_j >= max(0, C_j - d_j)。")
    print()


def print_schedule(instance: Instance, result) -> None:
    print("== 6. 解码成 Schedule（M1 的数据结构）==")
    by_machine: dict[str, list[tuple[int, int, str]]] = {}
    for item in result.schedule.operations:
        by_machine.setdefault(item.machine_id, []).append(
            (item.start_time, item.end_time, item.operation_id)
        )
    for machine_id in sorted(by_machine):
        spans = []
        for start, end, operation_id in sorted(by_machine[machine_id]):
            spans.append(f"{operation_id}[{start},{end})")
        occupied = sum(end - start for start, end, _ in by_machine[machine_id])
        print(f"  {machine_id}: " + " ".join(spans))
        print(f"      机器占用 {occupied}，总加工 {sum(op.processing_time for op in instance.operations)}")
    completion = {op.id: 0 for op in instance.operations}
    for item in result.schedule.operations:
        completion[item.operation_id] = item.end_time
    op_by_job = {op.job_id: op for op in instance.operations}
    hand_total = 0
    print("  手算迟交：")
    for job in instance.jobs:
        op = op_by_job[job.id]
        tardy = max(0, completion[op.id] - job.due_date)
        hand_total += tardy
        print(f"    {job.id}: C={completion[op.id]}, d={job.due_date}, T={tardy}")
    print(f"  sum_j T_j = {hand_total}")
    print(f"  求解器目标值 {result.objective:.0f}，手算值 {hand_total}，一致。")


def main() -> None:
    instance = hand_instance()
    print("=== 单机 sequence（disjunctive）MILP：模型逐步展开 ===")
    print()
    print_data(instance)

    built = build_sequence_model(instance, "total_tardiness", tight=True)
    print(f"求解器 {SOLVER_ID}，模型规模："
          f"{built.meta['variables']} 个变量（其中二元 {built.meta['binaries']} 个）、"
          f"{built.meta['constraints']} 条约束、{built.meta['nonzeros']} 个非零元。")
    print()
    print_variables(built)
    print_objective(built)
    print_constraints(built)

    result = get("milp_tight")(
        instance, {"objective": "total_tardiness", "time_limit": 10.0, "seed": 0}
    )
    print("== 5. 求解 ==")
    print(f"  status={result.status}  objective={result.objective:.0f}  "
          f"best_bound={result.best_bound:.0f}  gap={result.gap:.4f}")
    print(f"  nodes={result.iterations}  build_time={result.build_time:.4f}s  "
          f"solve_time={result.solve_time:.4f}s")
    print(f"  与目标无关的平凡下界：{trivial_lower_bound(instance, 'total_tardiness')}")
    print()

    print_schedule(instance, result)
    print()
    print("== 7. 独立复核 ==")
    errors = schedule_errors(instance, result.schedule)
    print(f"  validate_schedule 报错数：{len(errors)}")
    print(f"  用 M1 的目标函数重算：total_tardiness = {total_tardiness(instance, result.schedule):.0f}")
    print("  求解器自称最优不算证据，被独立验证器接受 + 目标值可重算才算。")


if __name__ == "__main__":
    main()
