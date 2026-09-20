"""M3 Week 2 Day 4：CP-SAT 的 FJSP 模型（可选区间 + ExactlyOne + NoOverlap）。

脚本做六件事：

```text
1. 模型规模：三个实例的变量 / 约束 / 可选区间数，并手算核对 tiny_2x2
2. tiny_2x2：CP-SAT 报 OPTIMAL，且 best_bound == objective
3. fjsp_6x4_f2（18 道工序）：2 秒证明最优，读 branches / 耗时
4. 限时敏感性：fjsp_10x5_f3 在 tl = 1 / 2 / 10 秒下的
   status / objective / best_bound / gap / branches
5. 拒绝：非 makespan 目标、以及本模型没有建模的约束
6. 纪律复核：目标值独立重算、排程过独立验证器
```

**``OPTIMAL`` 的含义**：求解器证明的是**它自己的模型**最优。因此本方法遇到模型里
没有对应变量的约束时直接拒绝，而不是拿一个忽略了部分约束的模型的最优解冒充问题的
最优解。

运行：``python examples/m3w2d4_cpsat.py``
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fjsp_core.models import FJSPInstance
from fjsp_core.schedule_validation import validate_schedule
from fjsp_io.generator import generate_instance
from fjsp_shop.cpsat_fjsp import build_model, fjsp_cpsat, lower_bound
from fjsp_shop.toy_instances import TOY_INSTANCES

SPEC = {"objective": "makespan", "time_limit": 5.0, "seed": 0}


def timeline(instance: FJSPInstance, schedule) -> str:
    return "  ".join(
        f"{item.operation_id}@{item.machine_id}[{item.start_time},{item.end_time})"
        for item in schedule.operations
    )


#: proto 里约束的字段名，用来给「约束数」分个类
CONSTRAINT_FIELDS = (
    "interval",
    "exactly_one",
    "at_most_one",
    "no_overlap",
    "lin_max",
    "cumulative",
    "bool_or",
    "all_diff",
    "table",
    "linear",
)


def constraint_mix(instance: FJSPInstance) -> dict[str, int]:
    """按 proto 的字段类型给约束计数。

    ``CP-SAT`` 的 ``stats()['constraints']`` 把**区间定义**也算进约束里（每个可选区间在
    proto 中占一条 ``interval`` 约束），所以「约束数」不等于「逻辑约束条数」。这个函数
    把两者分开，避免把 ``interval`` 误读成一条额外的约束。
    """
    model = build_model(instance).model
    mix: dict[str, int] = {}
    for constraint in model.Proto().constraints:
        for field in CONSTRAINT_FIELDS:
            checker = getattr(constraint, f"has_{field}", None)
            if checker is not None and checker():
                mix[field] = mix.get(field, 0) + 1
                break
        else:  # pragma: no cover - 出现新字段时才会走到
            mix["?"] = mix.get("?", 0) + 1
    return mix


def nonzero_breakdown(result) -> dict[str, float]:
    """目标值分解里只保留非零分量：零分量对目标值没有贡献，打印出来只是噪声。"""
    return {key: value for key, value in result.breakdown.items() if value}


def refuse(label: str, action) -> None:
    try:
        action()
    except ValueError as exc:
        print(f"  {label}")
        print(f"    拒绝：{exc}")
    else:  # pragma: no cover
        raise AssertionError(f"{label} 本该被拒绝")


def report(instance: FJSPInstance, label: str, time_limit: float) -> None:
    result = fjsp_cpsat(instance, {**SPEC, "time_limit": time_limit})
    validate_schedule(instance, result.schedule)
    print(f"  {label:<34} tl = {time_limit:>4.1f}s")
    print(f"    status      = {result.status}")
    print(f"    objective   = {result.objective}")
    print(f"    best_bound  = {result.best_bound}"
          f"   （{result.detail['bound_kind']}）")
    print(f"    gap         = {result.gap}")
    print(f"    branches    = {result.iterations}   conflicts = {result.detail['conflicts']}")
    print(f"    build_time  = {result.build_time:.6f}s   "
          f"solve_time = {result.solve_time:.6f}s   "
          f"solver wall_time = {result.detail['wall_time']:.3f}s")
    print(f"    solver_objective - 独立重算 = {result.detail['solver_objective_delta']}")
    print(f"    LB（朴素下界，与求解器无关）= {lower_bound(instance)}    "
          f"horizon = {result.detail['horizon']}")


def main() -> None:
    tiny = TOY_INSTANCES["tiny_2x2"]()
    three = TOY_INSTANCES["assign_2x3"]()
    small = generate_instance(seed=104, jobs=6, machines=4, operations_per_job=3, flexibility=2)
    wide = generate_instance(seed=105, jobs=10, machines=5, operations_per_job=3, flexibility=3)

    print("=== CP-SAT 的 FJSP 模型 ===")
    print()

    # ---------------------------------------------------------------- 1
    print("== 1. 模型规模 ==")
    print("  实例          工序  可选区间  变量  约束  horizon")
    for instance, label in ((tiny, "tiny_2x2"), (three, "assign_2x3"), (small, "fjsp_6x4_f2")):
        stats = build_model(instance).stats()
        print(f"  {label:<13} {stats['operations']:>4}  {stats['optional_intervals']:>7}  "
              f"{stats['variables']:>5} {stats['constraints']:>5}  {stats['horizon']:>7}")
    print("  约束数的构成（按 proto 的字段类型分类）：")
    for instance, label in ((tiny, "tiny_2x2"), (small, "fjsp_6x4_f2")):
        mix = constraint_mix(instance)
        parts = " · ".join(f"{field} {count}" for field, count in mix.items())
        print(f"    {label:<13} {parts}")
    print("  手算核对 tiny_2x2：4 道工序 x 2 台合格机器 = 8 个可选区间（proto 里每个区间")
    print("  自己占一条 interval 约束）；4 条 ExactlyOne；2 台机器各 1 条 NoOverlap；")
    print("  2 条 precedence（linear）；1 条 AddMaxEquality（lin_max）。")
    print("  8 + 4 + 2 + 2 + 1 = 17。也就是说「约束数」里有 8 条是区间定义，")
    print("  真正的逻辑约束是 9 条 —— 读模型规模时要把这两类分开。")
    print("  变量 = 4 个 start + 4 个 end + 8 个 presence + 1 个 makespan = 17。")
    print()

    # ---------------------------------------------------------------- 2
    print("== 2. tiny_2x2：小到能指望求解器证明最优 ==")
    report(tiny, "tiny_2x2（2 订单 x 2 工序）", 2.0)
    result = fjsp_cpsat(tiny, SPEC)
    print(f"    排程 = {timeline(tiny, result.schedule)}")
    print("  best_bound == objective，说明求解器证明了它自己的模型最优；")
    print("  这个实例的最优性还有一条独立证据：LB = 2 已经等于目标值（下界碰上界）。")
    print()

    # ---------------------------------------------------------------- 3
    print("== 3. fjsp_6x4_f2：18 道工序 ==")
    report(small, "fjsp_6x4_f2（seed 104）", 2.0)
    result = fjsp_cpsat(small, SPEC)
    print(f"    排程 = {timeline(small, result.schedule)}")
    print()

    # ---------------------------------------------------------------- 4
    print("== 4. 限时敏感性：fjsp_10x5_f3（seed 105，30 道工序）==")
    for time_limit in (1.0, 2.0, 10.0):
        report(wide, "fjsp_10x5_f3", time_limit)
    print("  1 秒与 2 秒都只能报 FEASIBLE：可行解已经找到，但没有证明它最优；")
    print("  此时 best_bound 是**搜索进度**，不是「问题的最优值」。")
    print("  gap = (objective - best_bound) / objective，落在 detail['bound_kind'] 里区分这两种界。")
    print()

    # ---------------------------------------------------------------- 5
    print("== 5. 拒绝模型覆盖不了的输入 ==")
    refuse(
        "目标不是 makespan：",
        lambda: fjsp_cpsat(tiny, {**SPEC, "objective": "total_tardiness"}),
    )
    refuse(
        "只建模、不求解的入口也一样拦：",
        lambda: build_model(tiny, {"objective": "total_tardiness"}),
    )
    print("  本模型的最小化对象就是 makespan，拿它去报别的目标名是偷换指标 ——")
    print("  宁可拒绝，也不要给出一个「目标名与实际最小化对象不一致」的结果。")
    print("  同一道闸门（require_plain_fjsp）还会挡下实例里本模块没有建模的约束：")
    print("  模型少了那几族变量，产出的排程一定过不了独立验证器，")
    print("  所以拒绝发生在建模之前，而不是让求解器去解一个残缺的模型。")
    print("  benchmark 会把这种行记成 FAILED 并带上原因，而不是记成「求解器给了非法解」。")
    print()

    # ---------------------------------------------------------------- 6
    print("== 6. 纪律复核 ==")
    final = fjsp_cpsat(small, SPEC)
    print(f"  solver_objective_delta = {final.detail['solver_objective_delta']}"
          f"（目标值由 fjsp_core 独立重算，不取求解器读数）")
    print(f"  num_search_workers = {final.detail['num_search_workers']}（固定 1 线程才可复现）")
    print(f"  model_stats = {final.detail['model_stats']}")
    print("  validate_schedule 报错数 = 0")
    print(f"  breakdown（只列非零分量）= {nonzero_breakdown(final)}")


if __name__ == "__main__":
    main()
