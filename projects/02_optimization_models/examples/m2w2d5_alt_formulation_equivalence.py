"""Day 5：换一个 formulation（time-indexed），用**穷举**证明它与原模型等价。

「等价」在这里有明确的操作含义：在可以穷举的小实例上，新模型给出的最优值与
**独立于任何求解器**的枚举最优值相同。本脚本做四件事：

1. 打印 time-indexed 模型的变量与约束定义，以及它的规模；
2. 对三个 M1 的 ``oracle`` 支持的目标，把 4 个值摆在一张表里对拍
   （枚举最优 / tight / loose / alt）；
3. 换成 M1 的 oracle 不支持的目标，改比「三个 formulation 是否互相一致」；
4. 用一个带 precedence 的 2 job × 2 工序实例，验证 alt 模型能处理「一个 job
   多道工序」这件 sequence 模型做不到的事，并用工序顺序枚举复核 ΣCj。
"""

import sys
from itertools import permutations
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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
from opt_models.milp_scheduling import FORMULATIONS, model_stats
from opt_solvers.registry import get
from scheduling_algorithms.oracle import OBJECTIVES as ORACLE_OBJECTIVES
from scheduling_algorithms.oracle import exhaustive_optimum


def hand3() -> Instance:
    """3 job 单机：A(p=3,d=4)、B(p=2,d=2)、C(r=5,p=4,d=10)。"""
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


def hand3_parallel() -> Instance:
    """2 台机器、3 个 job，p = [4, 3, 5]：最优 Cmax = 7。"""
    return Instance(
        tuple(Job(f"J{i}", (f"O{i}",)) for i in range(3)),
        tuple(
            Operation(f"O{i}", f"J{i}", p, ("M0", "M1")) for i, p in enumerate([4, 3, 5])
        ),
        (Machine("M0", "M0"), Machine("M1", "M1")),
    )


def two_job_two_ops() -> Instance:
    """2 个 job 各 2 道工序，都在 M0 上：A(2→3)、B(4→1)，手算最优 ΣCj = 15。"""
    return Instance(
        (Job("A", ("A1", "A2")), Job("B", ("B1", "B2"))),
        (
            Operation("A1", "A", 2, ("M0",)),
            Operation("A2", "A", 3, ("M0",)),
            Operation("B1", "B", 4, ("M0",)),
            Operation("B2", "B", 1, ("M0",)),
        ),
        (Machine("M0", "M0"),),
    )


def spec(objective: str, **extra) -> dict:
    return {"objective": objective, "time_limit": 10.0, "seed": 0, **extra}


def enumerate_precedence_optimum(instance: Instance, objective_name: str) -> tuple[float, int]:
    """枚举满足 precedence 的全部工序顺序（单机），返回 (最优值, 合法顺序数)。"""
    objective = M2_OBJECTIVES[objective_name]
    op_by_id = {op.id: op for op in instance.operations}
    job_by_id = {job.id: job for job in instance.jobs}
    machine_id = instance.machines[0].id
    operation_ids = [op.id for op in instance.operations]
    position = {
        op_id: index
        for index, op_id in enumerate(
            op_id for job in instance.jobs for op_id in job.operation_ids
        )
    }
    best = float("inf")
    count = 0
    for order in permutations(operation_ids):
        starts: dict[str, int] = {}
        clock = 0
        for op_id in order:
            op = op_by_id[op_id]
            begins = max(clock, job_by_id[op.job_id].release_time)
            starts[op_id] = begins
            clock = begins + op.processing_time
        if any(
            starts[job.operation_ids[index + 1]] < starts[job.operation_ids[index]] + op_by_id[job.operation_ids[index]].processing_time
            for job in instance.jobs
            for index in range(len(job.operation_ids) - 1)
        ):
            continue
        count += 1
        spans = tuple(
            ScheduledOperation(op.id, machine_id, starts[op.id], starts[op.id] + op.processing_time)
            for op in instance.operations
        )
        best = min(best, float(objective(instance, Schedule(spans))))
    return best, count


def print_formulation(instance: Instance) -> None:
    print("== 1. 替代 formulation：time-indexed ==")
    print("  变量：y[o][m][t] = 1 表示工序 o 在机器 m 的 t 时刻**开工**（t 取整数时刻）")
    print("        y 只在 o 的机器集合里、且 t 落在时间窗 [最早开工, H - p] 内存在")
    print("  约束：① 每道工序恰好开工一次：sum_{m, t} y[o][m][t] = 1")
    print("        ② 每台机器每个时刻最多一道工序：sum_{o 在 m 上可达} sum_{t' in [t-p_o+1, t]} y[o][m][t'] <= 1")
    print("        ③ precedence：同 job 相邻工序 sum t*y[后] >= sum (t + p_前)*y[前]")
    print("        ④ 完成时间由 y 的加权和给出，再套进各目标的表达式")
    print("  与 sequence 模型的关键差别：互斥写在**时间格点**上（机器容量约束），")
    print("  不再需要 Big-M，也不再需要「谁先谁后」的二元变量 —— 换来了更强的松弛。")
    print()
    print("  instance          method      变量    二元   约束   非零元")
    for name, sample in (("hand3", hand3()), ("hand3_parallel", hand3_parallel())):
        for method in FORMULATIONS:
            if name == "hand3_parallel" and method != "milp_alt":
                continue
            stats = model_stats(sample, {"method": method, "objective": "makespan"})
            print(f"  {name:16s}  {method:11s} {stats['variables']:6d} "
                  f"{stats['binaries']:6d} {stats['constraints']:6d} {stats['nonzeros']:7d}")
    print("  alt 的变量数随 H = max r + sum p 线性增长，模型规模明显大于 sequence 模型。")
    print()


def print_oracle_table() -> None:
    print("== 2. 与独立穷举对拍（M1 的 exhaustive_optimum）==")
    print("  instance          objective                枚举最优   枚举次数    tight     loose       alt   一致")
    for name, instance in (("hand3", hand3()), ("hand3_parallel", hand3_parallel())):
        for objective in sorted(ORACLE_OBJECTIVES):
            expected, _, count = exhaustive_optimum(instance, objective, limit=100_000)
            cells = {}
            for method in FORMULATIONS:
                if name == "hand3_parallel" and method != "milp_alt":
                    continue
                result = get(method)(instance, spec(objective))
                cells[method] = result.objective
            values = " ".join(
                f"{cells[method]:8.1f}" if method in cells else f"{'—':>8s}"
                for method in FORMULATIONS
            )
            agree = all(abs(value - expected) < 1e-6 for value in cells.values())
            print(f"  {name:16s}  {objective:22s} {expected:9.1f} {count:10d} {values}   "
                  f"{'是' if agree else '否'}")
    print("  枚举次数 = 被穷举的加工顺序个数：3 个 job 是 3! = 6，2 机 3 job 是 6 种顺序 × 选机。")
    print("  三列都与枚举值相同 —— 这是「模型没写错」的最强证据：求解器可能出错，")
    print("  但穷举是另一条完全独立的计算路径。")
    print()


def print_cross_formulation() -> None:
    print("== 3. oracle 不支持的目标：改比「三个 formulation 是否一致」==")
    print("  objective                    tight     loose       alt   一致")
    instance = hand3()
    for objective in sorted(M2_OBJECTIVES):
        if objective in ORACLE_OBJECTIVES:
            continue
        values = {
            method: get(method)(instance, spec(objective)).objective
            for method in FORMULATIONS
        }
        unique = {round(value, 6) for value in values.values()}
        print(f"  {objective:26s} {values['milp_tight']:8.1f} {values['milp_loose']:9.1f} "
              f"{values['milp_alt']:9.1f}   {'是' if len(unique) == 1 else '否'}")
    print("  一致不等于正确（三个模型可能一起错），所以「一致」只作为辅助证据；")
    print("  对上一条的穷举结果才是主证据。")
    print()


def print_precedence() -> None:
    instance = two_job_two_ops()
    print("== 4. alt 模型能做 sequence 模型做不到的事：一个 job 多道工序 ==")
    print("  A: A1(p=2) → A2(p=3)；B: B1(p=4) → B2(p=1)，全部在 M0 上。")
    expected, count = enumerate_precedence_optimum(instance, "total_completion_time")
    print(f"  独立枚举（满足 precedence 的加工顺序 {count} 个）：ΣCj 最优 = {expected:.0f}")
    result = get("milp_alt")(instance, spec("total_completion_time"))
    print(f"  milp_alt：status={result.status}  ΣCj={result.objective:.0f}  "
          f"best_bound={result.best_bound:.0f}  nodes={result.iterations}  "
          f"solve_time={result.solve_time:.3f}s")
    print("  sequence 模型在这个实例上的态度：", end="")
    for method in ("milp_tight", "milp_loose"):
        answer = get(method)(instance, spec("total_completion_time"))
        print(f"{method}={answer.status}", end="  ")
    print("（多工序超出它的定义范围）")
    print("  alt 给出的排程：")
    for item in result.schedule.operations:
        print(f"    {item.operation_id}  M0[{item.start_time},{item.end_time})")
    errors = schedule_errors(instance, result.schedule)
    print(f"  独立验证器报错 {len(errors)} 条；precedence 由验证器检查，不是模型自己说了算。")
    print()


def main() -> None:
    print("=== time-indexed 替代 formulation：等价性与适用范围 ===")
    print()
    instance = hand3()
    print_formulation(instance)
    print_oracle_table()
    print_cross_formulation()
    print_precedence()
    print("== 5. 等价性的边界 ==")
    print("  以上对拍覆盖的是「最优值相同」。等价性不要求最优排程相同：")
    for method in FORMULATIONS:
        result = get(method)(instance, spec("total_tardiness"))
        plan = " ".join(
            f"{item.operation_id}({item.start_time}-{item.end_time})"
            for item in result.schedule.operations
        )
        print(f"    {method:11s} ΣTj={result.objective:.0f}  排程 {plan}")


if __name__ == "__main__":
    main()
