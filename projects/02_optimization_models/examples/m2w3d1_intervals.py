"""Day 1：domain、propagation、IntervalVar、OptionalIntervalVar 与整数时间缩放。

本脚本不追求最优值，只把 CP-SAT 的基本零件摆出来看：

1. ``domain`` 是**集合**（若干整数区间的并），不是 MILP 那种「上下界 + 连续」；
2. ``IntervalVar`` 是 (start, size, end) 三元组，``end = start + size`` 是它的定义；
3. ``propagation`` 沿约束收紧 domain，可以把求解过程中的域回填到响应里看；
4. ``OptionalIntervalVar`` 多一个布尔 ``presence``，区间「在不在」本身是决策；
5. 时间必须是整数，非整数时间单位要先用 ``time_scale`` 放大。

只打印，不写盘；时钟变量与手算一致，输出为真实运行结果。
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ortools.sat.python import cp_model

from opt_common.bridge import Instance, Job, Machine, Operation, makespan, validate_schedule
from opt_models.cpsat_models import cpsat_parallel


def inspect(build):
    """建模、求解，并把求解器回填的「域」取出来。"""
    model = cp_model.CpModel()
    build(model)
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.fill_tightened_domains_in_response = True
    status = solver.Solve(model)
    domains = [
        (item.name, list(item.domain)) for item in solver.ResponseProto().tightened_variables
    ]
    return solver.StatusName(status), domains


def build_chain(model: cp_model.CpModel) -> None:
    """一个 job 的三道工序串成链：end_k <= start_{k+1}，每道长 5，H = 30。"""
    horizon = 30
    previous_end = None
    for index in range(3):
        start = model.NewIntVar(0, horizon, f"chain_start{index}")
        end = model.NewIntVar(0, horizon, f"chain_end{index}")
        model.NewIntervalVar(start, 5, end, f"chain_iv{index}")
        if previous_end is not None:
            model.Add(previous_end <= start)
        previous_end = end


def build_three_on_one_machine(model: cp_model.CpModel) -> None:
    """同一台机器上三个长 5 的区间，只加一条 NoOverlap，H = 30。"""
    horizon = 30
    intervals = []
    for index in range(3):
        start = model.NewIntVar(0, horizon, f"noov_start{index}")
        end = model.NewIntVar(0, horizon, f"noov_end{index}")
        intervals.append(model.NewIntervalVar(start, 5, end, f"noov_iv{index}"))
    model.AddNoOverlap(intervals)


def build_optional(model: cp_model.CpModel) -> None:
    """同一个工序在两台机器上各一个可选区间，恰好一个成立。"""
    horizon = 20
    start = model.NewIntVar(0, horizon, "opt_start")
    end = model.NewIntVar(0, horizon, "opt_end")
    flags = []
    for machine in ("M0", "M1"):
        flag = model.NewBoolVar(f"opt_presence_{machine}")
        model.NewOptionalIntervalVar(start, 7, end, flag, f"opt_iv_{machine}")
        flags.append(flag)
    model.AddExactlyOne(flags)
    # 固定一个目标，避免求解器随手做一个与演示无关的决策
    model.Add(start <= 4)


def scaling_instance() -> Instance:
    """2 台机器、5 个单工序 job 的小实例（M1 Week 1 Day 5 的 LPT 反例）。"""
    times = [3, 3, 2, 2, 2]
    return Instance(
        tuple(Job(f"J{index}", (f"J{index}_O0",)) for index in range(len(times))),
        tuple(
            Operation(f"J{index}_O0", f"J{index}", value, ("M0", "M1"))
            for index, value in enumerate(times)
        ),
        (Machine("M0", "M0"), Machine("M1", "M1")),
    )


def main() -> None:
    print("=== 1. domain：集合，不是区间 ===")
    sparse = cp_model.Domain.FromIntervals([[0, 3], [10, 12], [20, 20]])
    print(f"Domain.FromIntervals([[0,3],[10,12],[20,20]])  ->  {sparse}")
    print(f"Domain.FromValues([1,3,5,7])                      ->  {cp_model.Domain.FromValues([1, 3, 5, 7])}")
    model = cp_model.CpModel()
    choice = model.NewIntVarFromDomain(sparse, "choice")
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.Solve(model)
    print(f"域写成 [0,3] U [10,12] U {{20}} 的变量，求解后取值 {solver.Value(choice)}")
    print("MILP 的整数变量域只能写成 [lb, ub]；CP 的域是任意集合，这是两者最底层的差别。")

    print()
    print("=== 2. IntervalVar：end = start + size ===")
    model = cp_model.CpModel()
    start = model.NewIntVar(0, 30, "demo_start")
    end = model.NewIntVar(0, 30, "demo_end")
    model.NewIntervalVar(start, 5, end, "demo_iv")
    print("start 初始域 [0,30]，end 初始域 [0,30]，size 固定 5")
    print("IntervalVar 由 (start, size, end) 定义，本身是派生对象，不进 tightened_variables。")

    print()
    print("=== 3. propagation：沿约束收紧域（实测观察）===")
    status, domains = inspect(build_chain)
    print(f"优先级链 end_k <= start_k+1，每道 5，H = 30   ->  状态 {status}")
    for name, domain in domains:
        print(f"  {name:16s} -> {domain}")
    status, domains = inspect(build_three_on_one_machine)
    print(f"三个长 5 的区间 + 一条 NoOverlap，H = 30      ->  状态 {status}")
    for name, domain in domains:
        print(f"  {name:16s} -> {domain}")
    print("观察：链把上界一路推下来（start0 <= 15、start1 <= 20、start2 <= 25）；")
    print("      NoOverlap 只给出 start <= H - size = 25 —— 三者谁排最后没定，这就是最紧的界。")
    print("注意：这里的域是**求解过程中的域**（含传播收紧的界，也可能含搜索的定值），")
    print("      适合定性观察传播，不能当作传播不动点引用。")

    print()
    print("=== 4. OptionalIntervalVar：多一个布尔 presence ===")
    status, domains = inspect(build_optional)
    print(f"一个工序、两台机器、恰好一个成立，另加 start <= 4      ->  状态 {status}")
    for name, domain in domains:
        print(f"  {name:20s} -> {domain}")
    print("presence 是 BoolVar；它成立时区间才占用机器时间。选机决策 = 一组布尔变量。")

    print()
    print("=== 5. 整数时间缩放 ===")
    instance = scaling_instance()
    for scale in (1, 2, 4):
        result = cpsat_parallel(
            instance, {"objective": "makespan", "time_scale": scale, "time_limit": 5.0}
        )
        validate_schedule(instance, result.schedule)
        timeline = sorted(
            (item.machine_id, item.start_time, item.end_time)
            for item in result.schedule.operations
        )
        print(
            f"time_scale={scale}: 状态 {result.status}, Cmax={makespan(instance, result.schedule)}, "
            f"目标除数={result.detail['objective_divisor']:g}"
        )
        print(f"   排程（真实时间单位）{timeline}")
    print("放大 k 倍只是把同一组时间换成整数坐标；end = start + p * k 整除回来是精确的。")
    print("M1 的 processing_time / release_time 本来就是 int，所以 time_scale=1 即恒等映射。")


if __name__ == "__main__":
    main()
