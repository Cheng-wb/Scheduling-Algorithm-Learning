"""Day 5：区分 OPTIMAL / FEASIBLE / UNKNOWN / INFEASIBLE / MODEL_INVALID。

五个状态各自配一个**能稳定复现**的最小实例：

```text
OPTIMAL       2 台机器、5 个单工序 job，1 秒预算内证完 -> 状态 OPTIMAL，bound == 目标
FEASIBLE      单机 12 个 job 的 total_tardiness，预算太短 -> 找到解，没证完
UNKNOWN       25 个 job 的实例，预算 0.01 秒 -> 既没找到解，也没证明不可行
INFEASIBLE    3 个工序各占 2 单位，资源容量只有 1 -> 单个工序自己就超容量
MODEL_INVALID 用 horizon = -1 建出空域的变量 -> 求解器拒绝执行
```

两条纪律要在输出里看得很清楚：

1. 除了 OPTIMAL / FEASIBLE，**不读任何 ``solver.Value()``**，所以
   ``objective`` 与 ``best_bound`` 都是 ``None``；
2. ``INFEASIBLE`` 时 ``BestObjectiveBound()`` 返回 ``0.0``，这个数**不能**写进
   ``best_bound`` —— 否则「无解」会伪装成「下界为 0」。脚本把原始值单独打印出来
   对照（``detail['raw_best_bound']``）。

第 6 节讨论时间限制与参数：``num_search_workers=1`` + 固定 ``random_seed``
是可复现性的前提，而 ``max_time_in_seconds`` 决定的是「搜多久」，
不是「搜多好」。

只打印，不写盘。
"""

import sys
import time
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ortools.sat.python import cp_model

from opt_common.bridge import (
    Instance,
    Job,
    Machine,
    Operation,
    generate_instance,
    makespan,
    validate_schedule,
)
from opt_models.cpsat_models import (
    cpsat_cumulative,
    cpsat_parallel,
    cp_status_name,
    m2_status,
    solve_model_invalid_demo,
)
from opt_solvers.result import STATUSES


def one_op_instance(times: list[int], machines: int) -> Instance:
    eligible = tuple(f"M{i}" for i in range(machines))
    return Instance(
        tuple(Job(f"J{index}", (f"J{index}_O0",)) for index in range(len(times))),
        tuple(
            Operation(f"J{index}_O0", f"J{index}", value, eligible)
            for index, value in enumerate(times)
        ),
        tuple(Machine(f"M{i}", f"M{i}") for i in range(machines)),
    )


def show(label: str, result, instance: Instance | None = None) -> None:
    """统一打印一次求解的五要素，缺什么就显式写 None。"""
    detail = result.detail
    print(f"  {label}")
    print(f"    M2 状态         : {result.status}（CP-SAT 原生 {detail.get('cp_status')}）")
    print(f"    objective       : {result.objective}")
    print(f"    best_bound      : {result.best_bound}")
    print(f"    raw_best_bound  : {detail.get('raw_best_bound')}  <- 求解器原始返回值")
    print(f"    schedule        : {'有' if result.schedule is not None else 'None'}")
    print(f"    iterations      : {result.iterations}")
    print(f"    build/solve     : {result.build_time:.4f} s / {result.solve_time:.4f} s")
    if instance is not None and result.schedule is not None:
        validate_schedule(instance, result.schedule)
        print(f"    独立验证器      : 通过，Cmax = {makespan(instance, result.schedule)}")
    if result.best_bound is not None and result.objective is not None:
        gap = (result.objective - result.best_bound) / abs(result.objective) if result.objective else 0.0
        print(f"    相对 gap        : {gap:.4f}")


def main() -> None:
    print("=== 1. OPTIMAL：预算内既找到解、又证完了 ===")
    small = one_op_instance([3, 3, 2, 2, 2], 2)
    show(
        "cpsat_parallel，makespan，time_limit = 1.0",
        cpsat_parallel(small, {"objective": "makespan", "time_limit": 1.0}),
        small,
    )
    print("  判据：状态 OPTIMAL 且 bound == objective。此时「这是最优值」有证明，不是猜测。")

    print()
    print("=== 2. FEASIBLE：找到解，但没证完 ===")
    single = generate_instance(51, jobs=12, machines=1)
    show(
        "generate_instance(51, jobs=12, machines=1)，total_tardiness，time_limit = 0.05",
        cpsat_parallel(
            single, {"objective": "total_tardiness", "time_limit": 0.05}
        ),
        single,
    )
    print("  注意 best_bound = 0.0：这是「所有完工时间都不超过交期」的平凡下界。")
    print("  它不是垃圾，但几乎没有信息量 —— gap = 1.0 说明证明离得还很远。")
    print("  短预算下这个目标值还会随机器负载抖动（见第 6 节的重复测量）。")

    print()
    print("=== 3. UNKNOWN：预算内什么都没判定出来 ===")
    hard = generate_instance(50, jobs=25, machines=3)
    show(
        "generate_instance(50, jobs=25, machines=3)，makespan，time_limit = 0.01",
        cpsat_parallel(hard, {"objective": "makespan", "time_limit": 0.01}),
        hard,
    )
    print("  UNKNOWN 的含义是「不知道」：既没有可行解，也没有不可行的证明。")
    print("  它和 INFEASIBLE 的区别是决定性的 —— 不能把 UNKNOWN 当成「无解」来汇报。")

    print()
    print("=== 4. INFEASIBLE：证明了无可行解 ===")
    tight = one_op_instance([5, 5, 5], 3)
    show(
        "3 个工序、每工序占 2 单位、resource_capacity = 1",
        cpsat_cumulative(
            tight,
            {
                "objective": "makespan",
                "time_limit": 5.0,
                "resource_capacity": 1,
                "resource_demand": 2,
            },
        ),
    )
    print("  单个工序的需求 2 就超过容量 1，任何时刻都不可行，所以分支数是")
    print("  0：求解器在传播阶段就判死了，不需要搜索。")
    print("  特别注意 raw_best_bound = 0.0 —— 这个 0 被刻意丢掉，best_bound 写的是 None。")

    print()
    print("=== 5. MODEL_INVALID：模型本身非法，求解器拒绝执行 ===")
    show(
        "solve_model_invalid_demo：所有变量上界设成 -1（空域）",
        solve_model_invalid_demo(
            one_op_instance([3, 2], 2), {"objective": "makespan", "time_limit": 5.0}
        ),
    )
    print("  MODEL_INVALID 不是「问题无解」，而是「题目本身写错了」：")
    print("  变量的 domain 为空、表达式整型溢出等等。它属于建模 bug，必须与")
    print("  INFEASIBLE 分开报 —— 把建模 bug 当成「实例无解」会直接毁掉实验结论。")

    print()
    print("=== 6. 时间限制与参数 ===")
    print("  同一实例、同一 spec，跑两次（num_search_workers=1、seed=7）：")
    spec = {"objective": "total_tardiness", "time_limit": 1.0, "seed": 7}
    first = cpsat_parallel(single, spec)
    second = cpsat_parallel(single, spec)
    print(f"    第一次 -> 状态 {first.status}, objective {first.objective}, "
          f"分支 {first.iterations}, 冲突 {first.detail['conflicts']}")
    print(f"    第二次 -> 状态 {second.status}, objective {second.objective}, "
          f"分支 {second.iterations}, 冲突 {second.detail['conflicts']}")
    print("  实测观察：两次的目标值一致，但分支数与冲突数不同。原因是时间预算")
    print("  按**墙钟**截断，两次运行在搜索树里停下的位置本来就不同（机器负载波动）。")
    print("  所以「可复现」的准确说法是：给足预算、搜到最优时目标值可复现；")
    print("  在时间限制下截断时，只有目标值稳定，搜索轨迹本身不保证逐位一致。")
    print("  测试里断言的也正是目标值相等，不是分支数相等。")

    print()
    print("  time_limit 阶梯（同一实例，只改预算）：")
    for limit in (0.05, 0.2, 1.0, 5.0):
        result = cpsat_parallel(
            single, {"objective": "total_tardiness", "time_limit": limit}
        )
        bound = "-" if result.best_bound is None else f"{result.best_bound:g}"
        print(f"    time_limit={limit:<5} 状态 {result.status:<9} "
              f"objective={str(result.objective):<8} bound={bound:<8} "
              f"分支={result.iterations:<7} 实测求解 {result.solve_time:.4f} s")
    print("  实测求解时间始终略大于 time_limit：预算是给搜索的，")
    print("  建模、读解、返回还要额外花时间；detail['cp_wall_time'] 是求解器自己记的墙钟。")

    print()
    print("  短预算 vs 长预算的重复测量（同一 spec 各跑 5 次）：")
    short_runs = [
        cpsat_parallel(single, {"objective": "total_tardiness", "time_limit": 0.05}).objective
        for _ in range(5)
    ]
    long_runs = []
    for _ in range(3):
        stable = cpsat_parallel(single, {"objective": "total_tardiness", "time_limit": 5.0})
        long_runs.append((stable.status, stable.objective, stable.best_bound))
    print(f"    time_limit=0.05 五次目标值 -> {short_runs}")
    print(f"    time_limit=5.0  三次（状态, 目标值, bound）-> {long_runs}")
    print("  实测观察：短预算下目标值逐次不同（墙钟截断点不同，得到的是不同的次优解）；")
    print("  长预算下每次都稳定收敛到同一个值。所以「可复现」不是免费的，")
    print("  它取决于预算是否足以让搜索走完同一段确定性路径。")

    print()
    print("=== 7. 状态在统一词表里的位置 ===")
    print(f"  opt_solvers.result.STATUSES 共 {len(STATUSES)} 个：")
    for status in STATUSES:
        print(f"    {status}")
    print("  前五个是 CP-SAT 原生状态的一一对应（脚本里 cp_status_name / m2_status 就是这个映射）；")
    print("  后三个是工程包装：FEASIBLE_OR_UNKNOWN（只找可行解模式）、")
    print("  FAILED（包装层异常，原因进 detail）、NOT_SOLVED（求解器根本没被调用）。")
    print("  映射自查（CP-SAT 原生状态码 -> M2 状态名）：")
    for code in ("UNKNOWN", "MODEL_INVALID", "FEASIBLE", "INFEASIBLE", "OPTIMAL"):
        raw = getattr(cp_model, code)
        print(f"    cp_model.{code:<14} = {raw} -> {m2_status(raw)}"
              f"（原生名 {cp_status_name(raw)}）")


if __name__ == "__main__":
    main()
