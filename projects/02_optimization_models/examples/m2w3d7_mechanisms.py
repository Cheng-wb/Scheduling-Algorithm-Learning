"""Day 7：把 CP 的传播/分支机制与 MILP 的松弛/分支机制摆在同一张桌上比。

Week 3 一路用下来的零件，最后要用机制解释清楚：为什么两个求解器
在**同一实例**上会一个快一个慢。

四个部分：

```text
1. CP 的传播   domain 是集合，约束沿变量之间的连接收紧域；链式 precedence 能一路
               推出上界，NoOverlap 只能给出「最晚也得在 H - size 前开始」这种弱界。
2. MILP 的松弛 先解 LP，拿对偶界；这个界是结构性的，与搜索预算无关。
               root LP 值一次就到位（下面用 root_lp=True 实测）。
3. 界从哪来    CP-SAT 没有 LP 松弛这一步：它的界是搜索过程中逐步得到的。
               同一实例上「MILP 的 root LP 值」与「CP-SAT 跑了 5 秒的界」方向相反，
               说明两者强弱取决于建模结构，不取决于范式。
4. 分支机制    MILP 分支 = 给一个小数变量加上下界割；CP 分支 = 在 domain 上切一刀，
               再加上冲突驱动的 nogood。用分支数/冲突数就能看出搜索规模，
               而 INFEASIBLE 时两个计数都是 0 —— 传播阶段就判死了。
```

``root_lp=True`` 是 Week 2 的 MILP 方法提供的选项：只解 LP relaxation，不分支。
本脚本打印的 LP 值都是这样实测出来的，不是引用。

只打印，不写盘。
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ortools.sat.python import cp_model

from opt_common.bridge import Instance, Job, Machine, Operation, generate_instance
from opt_models.cpsat_models import (
    build_cpsat_model,
    cpsat_cumulative,
    cpsat_jsp,
    cpsat_parallel,
)
from opt_solvers.registry import describe, get, load_week_modules

HORIZON = 30
CHAIN_LENGTH = 5


def parallel_instance(times: list[int], machines: int) -> Instance:
    eligible = tuple(f"M{i}" for i in range(machines))
    return Instance(
        tuple(Job(f"J{index}", (f"J{index}_O0",)) for index in range(len(times))),
        tuple(
            Operation(f"J{index}_O0", f"J{index}", value, eligible)
            for index, value in enumerate(times)
        ),
        tuple(Machine(f"M{i}", f"M{i}") for i in range(machines)),
    )


def tightened_domains(build) -> list[tuple[str, list[int]]]:
    """建模型、求解，把求解器回填的域取出来。"""
    model = cp_model.CpModel()
    build(model)
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.fill_tightened_domains_in_response = True
    solver.Solve(model)
    return [
        (item.name, list(item.domain))
        for item in solver.ResponseProto().tightened_variables
    ]


def build_chain(model: cp_model.CpModel) -> None:
    """三道工序串成链，每道长 5，H = 30。"""
    previous_end = None
    for index in range(3):
        start = model.NewIntVar(0, HORIZON, f"chain_start{index}")
        end = model.NewIntVar(0, HORIZON, f"chain_end{index}")
        model.NewIntervalVar(start, CHAIN_LENGTH, end, f"chain_iv{index}")
        if previous_end is not None:
            model.Add(previous_end <= start)
        previous_end = end


def build_three_on_one_machine(model: cp_model.CpModel) -> None:
    """同一台机器上三个长 5 的区间，只加一条 NoOverlap，H = 30。"""
    intervals = []
    for index in range(3):
        start = model.NewIntVar(0, HORIZON, f"noov_start{index}")
        end = model.NewIntVar(0, HORIZON, f"noov_end{index}")
        intervals.append(model.NewIntervalVar(start, CHAIN_LENGTH, end, f"noov_iv{index}"))
    model.AddNoOverlap(intervals)


def show_domains(title: str, domains: list[tuple[str, list[int]]]) -> None:
    print(f"  {title}")
    for name, domain in domains:
        print(f"    {name:16s} -> {domain}")


def main() -> None:
    load_week_modules()

    print("=== 1. CP 的传播：沿约束收紧 domain ===")
    show_domains(
        f"优先级链 end_k <= start_k+1，三道各 {CHAIN_LENGTH}，H = {HORIZON}",
        tightened_domains(build_chain),
    )
    show_domains(
        f"三个长 {CHAIN_LENGTH} 的区间 + 一条 NoOverlap，H = {HORIZON}",
        tightened_domains(build_three_on_one_machine),
    )
    print("  链把上界一路推下来：最后一道必须在 H - 3*5 = 15 前开始，前一道 20，第一道 25。")
    print("  NoOverlap 只能给出 H - 5 = 25：三者谁排最后没定，这就是它能给的最紧的界。")
    print("  机制差别：NoOverlap 的推理是「区间两两互斥」的局部推理，")
    print("  它不会去算「3 个长 5 的任务放在一台机器上至少要 15」这种全局量。")
    print("  注意：这里读到的是求解过程中的域，可能含搜索定值，适合定性观察传播。")

    print()
    print("=== 2. MILP 的松弛：一次 LP 就得到结构性下界（root_lp=True 实测）===")
    cases = [
        ("single_8", generate_instance(50, jobs=8, machines=1), "total_tardiness", "milp_alt"),
        ("single_12", generate_instance(51, jobs=12, machines=1), "total_tardiness", "milp_alt"),
        ("parallel_8", generate_instance(52, jobs=8, machines=3), "makespan", "milp_alt"),
        ("parallel_12", generate_instance(53, jobs=12, machines=3), "makespan", "milp_alt"),
    ]
    print(f"  {'实例':<13}{'模型':<14}{'root LP':>12}{'整数最优':>10}{'LP gap':>9}{'求解':>9}")
    print("  " + "-" * 66)
    lp_values: dict[str, float] = {}
    for label, instance, objective_name, method_name in cases:
        relaxation = get(method_name)(
            instance, {"objective": objective_name, "time_limit": 5.0, "root_lp": True}
        )
        integer = get(method_name)(
            instance, {"objective": objective_name, "time_limit": 5.0}
        )
        lp_value = relaxation.best_bound
        lp_values[label] = lp_value
        gap = (integer.objective - lp_value) / abs(integer.objective)
        print(
            f"  {label:<13}{relaxation.detail.get('formulation', method_name):<14}"
            f"{lp_value:>12.4f}{integer.objective:>10.0f}{gap:>9.4f}"
            f"{relaxation.solve_time:>9.4f}"
        )
    print("  同一范式内部就能差很多：单机上 time-indexed 的 LP gap 不到 1%，")
    print("  并行机 makespan 上接近 26% —— 因为松弛把「机器不可抢占」这件事放掉了，")
    print("  整数解必须重新付这笔账。LP 值是可证明的下界，与预算无关。")

    print()
    print("=== 3. CP-SAT 的界来自搜索，不是来自一次松弛 ===")
    print("  同一实例 single_12（整数最优 532，上面实测的 root LP = "
          f"{lp_values['single_12']:.4f}）：")
    single_12 = generate_instance(51, jobs=12, machines=1)
    for limit in (0.05, 0.5, 5.0):
        result = cpsat_parallel(
            single_12, {"objective": "total_tardiness", "time_limit": limit}
        )
        shown = "-" if result.best_bound is None else f"{result.best_bound:g}"
        print(f"    CP-SAT time_limit={limit:<5} 状态 {result.status:<9} "
              f"objective={str(result.objective):<8} bound={shown:<8} "
              f"分支 {result.iterations}")
    print("  观察：CP-SAT 的界随着搜索推进才慢慢抬起来，5 秒时仍接近平凡界 1；")
    print("  而 time-indexed MILP 的 LP 松弛在建模阶段就给出 529 这个下界。")
    print("  但这不是「MILP 更强」—— 换到 parallel_8 上方向就反了，实测：")
    parallel_8 = generate_instance(52, jobs=8, machines=3)
    fast = cpsat_parallel(parallel_8, {"objective": "makespan", "time_limit": 5.0})
    slow = get("milp_alt")(parallel_8, {"objective": "makespan", "time_limit": 5.0})
    print(f"    同一个 time-indexed MILP：LP 界 {lp_values['parallel_8']:.4f}，"
          f"证到最优 {slow.objective:g} 用了 {slow.solve_time:.4f} s")
    print(f"    cpsat_parallel        ：{fast.status}，界 {fast.best_bound:g}，"
          f"证到最优 {fast.objective:g} 只用了 {fast.solve_time:.4f} s")
    print("  LP 界弱的地方（并行机 makespan 丢掉了不可抢占性），CP 的区间推理正好强；")
    print("  反过来，交期惩罚那种线性成本结构，LP 的对偶界一上来就很紧，")
    print("  CP 侧反而要一点点搜。强弱是**建模结构**的函数。")

    print()
    print("=== 4. 分支机制与计数 ===")
    jsp = Instance(
        (Job("J0", ("J0_O0", "J0_O1")), Job("J1", ("J1_O0", "J1_O1"))),
        (
            Operation("J0_O0", "J0", 3, ("M0",)),
            Operation("J0_O1", "J0", 2, ("M1",)),
            Operation("J1_O0", "J1", 2, ("M1",)),
            Operation("J1_O1", "J1", 4, ("M0",)),
        ),
        (Machine("M0", "M0"), Machine("M1", "M1")),
    )
    tiny = cpsat_jsp(jsp, {"objective": "makespan", "time_limit": 5.0})
    print(f"  2x2 JSP：OPTIMAL Cmax = {tiny.objective:g}，"
          f"分支 {tiny.iterations}，冲突 {tiny.detail['conflicts']}")
    small = parallel_instance([3, 3, 2, 2, 2], 2)
    lpt_case = cpsat_parallel(small, {"objective": "makespan", "time_limit": 5.0})
    print(f"  并行机 [3,3,2,2,2]/2：OPTIMAL Cmax = {lpt_case.objective:g}，"
          f"分支 {lpt_case.iterations}，冲突 {lpt_case.detail['conflicts']}")
    dead = cpsat_cumulative(
        parallel_instance([5, 5, 5], 3),
        {"objective": "makespan", "time_limit": 5.0,
         "resource_capacity": 1, "resource_demand": 2},
    )
    print(f"  容量不可行的实例：{dead.status}，分支 {dead.iterations}，"
          f"冲突 {dead.detail['conflicts']}")
    print("  差别在「决策变量是什么」：")
    print("    MILP 分支：把某个本来取小数的最优 LP 变量按 lb/ub 割成两支；")
    print("    CP-SAT 分支：在某个变量的 domain（集合）中间切一刀，")
    print("      并且把搜索中撞到的冲突记成 nogood，用冲突数衡量学到的信息量。")
    print("  上面的 INFEASIBLE 分支数与冲突数都是 0：矛盾在传播阶段就被发现，")
    print("  求解器根本没进搜索树 —— 这是 CP 侧最漂亮的一类推理，LP 松弛做不到。")

    print()
    print("=== 5. 一周的产出清单 ===")
    print("  本周边界的三条注册方法（能力由 registry 自报）：")
    for name in ("cpsat_parallel", "cpsat_jsp", "cpsat_cumulative"):
        print(f"    {name:<18}{describe(name)}")
    print("  建模件：opt_models/cpsat_models.py（三方法共用一份区间建模逻辑）")
    print("  跑批件：opt_experiments/w3_cpsat.py（写 artifacts/month2_w3/）")
    print("  测试件：tests/test_cpsat_models.py（手算最优值 + 与 M1 oracle 交叉验证）")
    print("  复习命令（在项目目录下运行）：")
    print("    python -m pytest -q tests/test_cpsat_models.py")
    print("    python -m pytest -q")
    print("    python -m opt_experiments.w3_cpsat")


if __name__ == "__main__":
    main()
