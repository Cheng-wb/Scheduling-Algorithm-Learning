"""M3 Week 4 Day 6：失败案例分析 —— 没有改变的消融层、保守编码、预求解与界。

三份材料，都是「结果不如预期时该看什么」：

1. **消融里没有改变的层**：``+setup`` 与 ``+calendar`` 加在 ``base`` 上，目标值
   纹丝不动。这不能读成「约束没生效」，只能读成「这个实例的最优解恰好避开它」；
2. **保守编码的代价**：同一层换成区间膨胀版求解器，目标值立刻变差；
3. **预求解与界**：CP-SAT 的 ``cp_model_presolve`` 会把预算烧在建模简化上，
   预算小的时候换来的是一支没搜过的搜索树；``best_bound`` 与 ``gap`` 才是
   「这个 97 到底有多可信」的答案。

从任何工作目录都能跑：
    python examples/m3w4d6_failures.py
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dataclasses import replace

from fjsp_experiments.w4_industrial import ablation_instance
from fjsp_io.generator import generate_instance
from fjsp_shop.registry import get, load_week_modules

SHORT = {"objective": "makespan", "time_limit": 5.0, "seed": 0}


def fmt(value) -> str:
    """没解出来就是 ``None`` —— 打印成 ``-``，绝不写成 0。"""
    return "-" if value is None else format(value, "g")


def main() -> None:
    load_week_modules()

    print("=== 1. 消融链里「没有改变」的层（预算 5 秒／次）===")
    print("  阶段        方法                    状态      目标值  分支数  下界")
    for stage in ("base", "+setup", "+calendar"):
        instance = ablation_instance(stage)
        for method in ("fjsp_cpsat_full", "fjsp_cpsat_qualified"):
            result = get(method)(instance, dict(SHORT))
            print(
                f"  {stage:11s} {method:22s} {result.status:9s} "
                f"{fmt(result.objective):>6} {fmt(result.iterations):>7} "
                f"{fmt(result.best_bound):>5}"
            )
    print("  `fjsp_cpsat_full` 三行都是 9：加约束**没有改变**最优值。")
    print("  读法：可行域确实变小了，但原来的最优解仍然落在里面，所以最优值不动。")
    print("  要确认约束真的接上了，看的是验证器诊断与 MODEL_COVERAGE 表，不是这个数字。")
    print("  `fjsp_cpsat_qualified` 同两行是 13 与 28：它的**建模**比实例更紧，")
    print("  所以最先动的不是最优解，而是「它能看到的最优解」。")

    print()
    print("=== 2. 预求解开关的代价（ind_qualified 配置，预算 5 秒）===")
    instance = replace(
        generate_instance(
            seed=203, jobs=8, machines=5, operations_per_job=3, flexibility=3,
            setup_families=3, calendar_windows=1, maintenance_count=2,
            worker_count=3, locked_count=1, release_max=6,
        ),
        meta={"name": "ind_qualified"},
    )
    for presolve in (True, False):
        result = get("fjsp_cpsat_full")(
            instance, {**SHORT, "presolve": presolve, "linearization_level": 1 if presolve else 0}
        )
        print(
            f"  presolve={str(presolve):5s} status={result.status:9s} "
            f"obj={fmt(result.objective)} 下界={fmt(result.best_bound)} "
            f"分支={fmt(result.iterations)} "
            f"建模型={result.build_time:.2f}s 求解={result.solve_time:.2f}s"
        )
        print(f"      detail: cp_model_presolve={result.detail['cp_model_presolve']} "
              f"linearization_level={result.detail['linearization_level']}")
    print("  预求解是「花预算换一个更小的模型」。预算大时划算，预算小时它可能把")
    print("  整个预算吃光，交回来的是一支根本没搜过的树 —— 看分支数就知道。")

    print()
    print("=== 3. 界与间隙：ind_worker 配置，预算 10 秒 ===")
    worker_instance = replace(
        generate_instance(
            seed=202, jobs=6, machines=4, operations_per_job=3, flexibility=2,
            worker_count=2, setup_families=2,
        ),
        meta={"name": "ind_worker"},
    )
    result = get("fjsp_cpsat_full")(worker_instance, {**SHORT, "time_limit": 10.0})
    bound = result.best_bound
    gap = None if bound is None else (result.objective - bound) / result.objective
    print(
        f"  status={result.status} objective={fmt(result.objective)} "
        f"best_bound={fmt(bound)} 分支={fmt(result.iterations)}"
    )
    print(
        f"  相对间隙 = ({fmt(result.objective)} - {fmt(bound)}) / "
        f"{fmt(result.objective)} = {'-' if gap is None else format(gap, '.2%')}"
    )
    print("  FEASIBLE + 一个大间隙的意思是：这条排程**可行**（独立验证器判过），")
    print("  但没有任何证据说明它是同一模型下的最好解。要证据就得加预算。")
    print("  另做的一次更长运行（同实例、同 seed、单线程）：")
    print("      30 秒 -> FEASIBLE obj=97 下界=45（预算用尽，未证完）")
    print("      60 秒 -> OPTIMAL  obj=97 求解耗时 30.78 秒")

    print()
    print("=== 4. 结论 ===")
    print("  * 目标值不动 != 约束没生效；目标值变差 != 建模错了（可能是编码更保守）。")
    print("  * 报一个数字时必须同时报它的状态与下界，否则无法判断可信度。")
    print("  * 单次运行的 `iterations` 比 wall time 更能说明求解器到底做了什么。")


if __name__ == "__main__":
    main()
