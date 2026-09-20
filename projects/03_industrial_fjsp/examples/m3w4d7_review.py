"""M3 Week 4 Day 7：收官核对 —— 约束覆盖表、两个求解器的正面对比、选型建议。

这个脚本只做「把这一周的东西摆到一张桌子上」：

1. 打印 ``fjsp_shop.constraints2.MODEL_COVERAGE``：每条工业约束落在模型的哪个
   字段、由验证器的哪条检查兜底、求解器在哪儿用到了它；
2. 两个 batch 实例 × 两个求解器，同一预算下的目标值、状态、下界；
3. 选型建议（哪条实例特征该用哪个）。

从任何工作目录都能跑：
    python examples/m3w4d7_review.py
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dataclasses import replace

from fjsp_io.generator import generate_instance
from fjsp_shop.constraints2 import MODEL_COVERAGE
from fjsp_shop.registry import available, describe_missing, get, load_week_modules

TIME_LIMIT = 8.0

#: 真减号 U+2212 与 ASCII 连字符。Windows 控制台默认 GBK，U+2212 编不出来会直接抛
#: ``UnicodeEncodeError``。``MODEL_COVERAGE`` 是**给人读的说明文字**，里面用了真减号，
#: 打印前必须换成 ASCII —— 这不是改内容，是改编码。
DASHES = {"−": "-", "–": "-", "—": "--"}


def printable(text: str) -> str:
    """把不可编码的破折号换成 ASCII，保证 stdout 在 GBK 控制台上打得出来。"""
    for fancy, plain in DASHES.items():
        text = text.replace(fancy, plain)
    return text

BATCH = {
    "ind_worker": (
        dict(
            seed=202, jobs=6, machines=4, operations_per_job=3,
            flexibility=2, worker_count=2, setup_families=2,
        ),
        "makespan",
    ),
    "ind_qualified": (
        dict(
            seed=203, jobs=8, machines=5, operations_per_job=3, flexibility=3,
            setup_families=3, calendar_windows=1, maintenance_count=2,
            worker_count=3, locked_count=1, release_max=6,
        ),
        "weighted_sum",
    ),
}


def main() -> None:
    failures = load_week_modules()
    print("=== 1. 注册表 ===")
    print(f"  available() = {available()}")
    # describe_missing 是「反着问」：给我一串名字，告诉你哪些**没**注册。
    wanted = ["fjsp_cpsat_qualified", "fjsp_cpsat_full"]
    missing = describe_missing(wanted)
    print(f"  describe_missing({wanted}) = {missing or '[] —— 两个名字都在'}")
    if failures:
        print(f"  有模块没加载成功：{failures}")
    print("  本月的批次只认注册表里的名字：名字没注册，那一行就是 FAILED。")
    print("  `load_week_modules()` 只是「把模块导入一遍」；导入成功不等于注册成功，")
    print("  所以上面这一步要单独问一遍。")

    print()
    print("=== 2. 约束覆盖表（MODEL_COVERAGE）===")
    print(f"  共 {len(MODEL_COVERAGE)} 行")
    for row in MODEL_COVERAGE:
        owner = getattr(row.owner, "__name__", str(row.owner))
        print(f"  - {printable(row.constraint)}")
        print(f"      字段    : {row.field}")
        print(f"      归属    : {owner}")
        print(f"      验证器  : {printable(row.validator_check)}")
        print(f"      求解器  : {printable(row.solver_use)}")

    print()
    print(f"=== 3. batch 对比（预算 {TIME_LIMIT:g} 秒／次，seed 0）===")
    print("  实例           目标函数        方法                    状态      目标值  下界")
    for name, (kwargs, objective) in BATCH.items():
        instance = replace(generate_instance(**kwargs), meta={"name": name})
        for method in ("fjsp_cpsat_full", "fjsp_cpsat_qualified"):
            result = get(method)(
                instance,
                {"objective": objective, "time_limit": TIME_LIMIT, "seed": 0},
            )
            bound = result.best_bound
            print(
                f"  {name:14s} {objective:14s} {method:22s} {result.status:9s} "
                f"{result.objective:>6g} "
                f"{'-' if bound is None else format(bound, 'g'):>5}"
            )

    print()
    print("=== 4. 选型建议 ===")
    print("  实例里有换型、且同族工序多   -> fjsp_cpsat_full（精确槽位链，可行域更大）")
    print("  实例很小或预算极短           -> fjsp_cpsat_qualified（模型小，出手快）")
    print("  需要 worker_id / 资质判定    -> 两个都做，只是换型编码不同")
    print("  任何情况下报数字             -> 同时报 status + best_bound，别只报目标值")


if __name__ == "__main__":
    main()
