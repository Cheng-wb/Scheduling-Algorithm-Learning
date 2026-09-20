"""M3 Week 2 Day 6：四种方法在同一批实例上的比较（质量 / 耗时 / 失败案例）。

四种方法：

```text
fjsp_random       随机机器指派 + 非延迟 ECT 派工
fjsp_shortest     每道工序的最快机器 + 同一个派工规则
fjsp_loadbalance  预计负载最小 + 同一个派工规则
fjsp_cpsat        CP-SAT（可选区间 + ExactlyOne + NoOverlap）
```

三个控制变量：**同一个实例、同一个目标（makespan）、同一个时间预算（10 秒）**。
三个启发式共用同一个派工规则，所以它们的差异只来自机器指派。

脚本做四件事：

```text
1. 七个实例 x 四种方法的主表：目标值、状态、下界、耗时
2. 参考值分档：小实例有 oracle 证书，大实例只有 CP-SAT 自证（并标明适用条件）
3. 失败案例：把 objective 换成另一个目标名之后，四个方法分别怎么回应
4. 汇总写入 artifacts/month3_w2/compare.csv
```

运行：``python examples/m3w2d6_compare.py``
"""

import csv
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fjsp_core.models import FJSPInstance
from fjsp_core.objective import evaluate
from fjsp_core.result import ShopResult
from fjsp_core.schedule_validation import validate_schedule
from fjsp_io.generator import generate_instance
from fjsp_shop import oracle
from fjsp_shop.cpsat_fjsp import fjsp_cpsat
from fjsp_shop.fjsp import fjsp_loadbalance, fjsp_random, fjsp_shortest
from fjsp_shop.toy_instances import TOY_INSTANCES

TIME_LIMIT = 10.0
SPEC = {"objective": "makespan", "time_limit": TIME_LIMIT, "seed": 0}
ARTIFACTS = Path(__file__).resolve().parents[1] / "artifacts" / "month3_w2"

METHODS = (
    ("fjsp_random", fjsp_random),
    ("fjsp_shortest", fjsp_shortest),
    ("fjsp_loadbalance", fjsp_loadbalance),
    ("fjsp_cpsat", fjsp_cpsat),
)


def build_instances() -> list[tuple[str, FJSPInstance]]:
    """七个实例：四个手算 + 三个生成（后两个与 configs/month3.json 同参数）。"""
    return [
        ("tiny_2x2", TOY_INSTANCES["tiny_2x2"]()),
        ("gap_2x2", TOY_INSTANCES["gap_2x2"]()),
        ("assign_2x3", TOY_INSTANCES["assign_2x3"]()),
        ("jsp_fixed_2x2", TOY_INSTANCES["jsp_fixed_2x2"]()),
        ("jsp_6x4 (s102)",
         generate_instance(seed=102, jobs=6, machines=4, operations_per_job=3, flexibility=1)),
        ("fjsp_6x4_f2 (s104)",
         generate_instance(seed=104, jobs=6, machines=4, operations_per_job=3, flexibility=2)),
        ("fjsp_10x5_f3 (s105)",
         generate_instance(seed=105, jobs=10, machines=5, operations_per_job=3, flexibility=3)),
    ]


def reference(instance: FJSPInstance) -> tuple[str, float | None]:
    """参考值分档。

    - 小实例：穷举 oracle 给出**证书**，并用 ``LB == optimum`` 再证一次
    - 大实例：空间太大，oracle 拒绝；此时只有 CP-SAT 自证（``OPTIMAL``），
      它的适用范围是「模型覆盖了实例的全部约束」—— 本批都是纯 FJSP，成立。
    """
    try:
        value, schedule = oracle.exhaustive_optimum(instance, "makespan", limit=200_000)
    except ValueError:
        return "cpsat_only", None
    validate_schedule(instance, schedule)
    return "oracle", value


def main() -> None:
    instances = build_instances()
    print("=== 四种方法同实例比较：质量 / 耗时 / 失败案例 ===")
    print(f"统一预算：time_limit = {TIME_LIMIT:.0f}s（启发式用不到，CP-SAT 证明完成后提前退出）")
    print()

    rows: list[dict[str, object]] = []
    print("== 1. 主表 ==")
    print("  实例                 工序  random  shortest  loadbalance   cpsat   参考值")
    for label, instance in instances:
        kind, ref = reference(instance)
        values: dict[str, ShopResult] = {}
        for name, solve in METHODS:
            result = solve(instance, SPEC)
            validate_schedule(instance, result.schedule)
            values[name] = result
            rows.append(
                {
                    "instance": label,
                    "operations": len(instance.operations),
                    "machines": len(instance.machines),
                    "method": name,
                    "status": result.status,
                    "objective": result.objective,
                    "best_bound": result.best_bound,
                    "build_time_s": round(result.build_time, 6),
                    "solve_time_s": round(result.solve_time, 6),
                    "iterations": result.iterations,
                    "reference_kind": kind,
                    "reference": ref,
                }
            )
        cpsat = values["fjsp_cpsat"]
        if kind == "oracle":
            ref_text = f"{ref:.0f} (oracle 证书)"
        else:
            ref_text = f"{cpsat.objective:.0f} (仅 CP-SAT 自证)"
        print(
            f"  {label:<20}{len(instance.operations):>3}"
            f"{values['fjsp_random'].objective:>8.0f}"
            f"{values['fjsp_shortest'].objective:>10.0f}"
            f"{values['fjsp_loadbalance'].objective:>11.0f}"
            f"{cpsat.objective:>8.0f}   {ref_text}"
        )
    print()

    # ---------------------------------------------------------------- 2
    print("== 2. 状态、下界与耗时 ==")
    print("  方法            状态分布                best_bound")
    for name, _ in METHODS:
        mine = [row for row in rows if row["method"] == name]
        statuses = "/".join(sorted({str(row["status"]) for row in mine}))
        bounds = [row["best_bound"] for row in mine]
        objectives = [float(row["objective"]) for row in mine]
        if all(bound is None for bound in bounds):
            bound_text = "全为 None（启发式不填下界）"
        else:
            numbers = [float(bound) for bound in bounds if bound is not None]
            equal = sum(1 for bound, value in zip(numbers, objectives) if bound == value)
            bound_text = (f"{len(numbers)} 个值，其中 {equal} 个等于目标值"
                          f"（{min(numbers):.0f} ~ {max(numbers):.0f}）")
        print(f"  {name:<15} {statuses:<23} {bound_text}")
    print()
    print("  耗时（七次运行合计，秒）：")
    for name, _ in METHODS:
        total = sum(float(row["solve_time_s"]) + float(row["build_time_s"])
                    for row in rows if row["method"] == name)
        worst = max(float(row["solve_time_s"]) for row in rows if row["method"] == name)
        print(f"  {name:<15} 合计 {total:>8.4f}s    最慢一次 {worst:>7.4f}s")
    print()

    # ---------------------------------------------------------------- 3
    print("== 3. 四方法一致 / 分歧 ==")
    for label, _ in instances:
        values = [float(row["objective"]) for row in rows if row["instance"] == label]
        low, high = min(values), max(values)
        tag = "四种方法一致" if low == high else f"分歧（最差/最好 = {high / low:.2f} 倍）"
        print(f"  {label:<20} 最好 {low:>3.0f}  最差 {high:>3.0f}  {tag}")
    print("  jsp_fixed_2x2 是唯一一个四种方法全部落在最优的实例：每道工序只有一台机器，")
    print("  「选机」这一维退化了，任何指派都一样 —— 这也说明 FJSP 的难度是从选机来的。")
    print("  其余六行都有分歧，而且实例越大分歧越大：fjsp_6x4_f2 上差 2.07 倍。")
    print("  三个启发式之间的差异只能来自机器指派（派工规则是共享的）；")
    print("  它们与 CP-SAT 的差距则同时来自指派与排序 —— CP-SAT 两个维度一起优化。")
    print()

    # ---------------------------------------------------------------- 4
    print("== 4. 失败案例：换一个目标名，四个方法分别怎么回应 ==")
    label6, instance6 = next(pair for pair in instances if pair[0].startswith("fjsp_6x4_f2"))
    other = {**SPEC, "objective": "total_tardiness"}
    print(f"  实例 = {label6}；交货期由生成器给出，把 objective 由 makespan 换成 "
          f"{other['objective']}：")
    for name, solve in METHODS[:3]:
        alt = solve(instance6, other)
        base = solve(instance6, SPEC)
        base_tardiness = evaluate(instance6, base.schedule, other["objective"])
        print(f"  {name:<15} 新目标名下 = {alt.objective:>5.0f}   "
              f"同一个方法在 makespan 下的排程算出 = {base_tardiness:>5.0f}")
    for name, action in (
        ("fjsp_cpsat", lambda: fjsp_cpsat(instance6, other)),
        ("oracle", lambda: oracle.exhaustive_optimum(instance6, other["objective"], 200_000)),
    ):
        try:
            action()
        except ValueError as exc:
            print(f"  {name:<15} 拒绝：{exc}")
        else:  # pragma: no cover - 闸门失效时才会走到
            raise AssertionError(f"{name} 本该拒绝非 makespan 目标")
    print("  两列数字逐个相同：目标名只改变了 evaluate 怎么给一个排程打分，改变不了搜索 ——")
    print("  这三个方法的规则里没有交货期，换个名字不会让它们朝拖期方向多走一步。")
    print("  能报出一个合法的目标值，不等于为这个目标优化过。CP-SAT 与 oracle 宁可拒绝，")
    print("  也不给出一个「目标名与实际优化对象不一致」的结果。")
    print()

    # ---------------------------------------------------------------- 5
    print("== 5. 落盘 ==")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    target = ARTIFACTS / "compare.csv"
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"  写入 {target.relative_to(Path(__file__).resolve().parents[1])}"
          f"（{len(rows)} 行 = 7 实例 x 4 方法）")


if __name__ == "__main__":
    main()
