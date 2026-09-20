"""M3 Week 2 Day 7：本周收口 —— 把四条纪律做成可执行检查，并量出两个维度各值多少。

脚本做五件事：

```text
1. 注册表：四个方法名与它们的描述（configs/month3.json 就按这些名字调用）
2. 四条纪律逐条做成可执行检查，打印 PASS/FAIL 与检查次数
3. 两个决策维度的分量分解（fjsp_6x4_f2）：
   (a) 只动机器指派  (b) 只动工序顺序  (c) 两维一起（CP-SAT）
   并给出「最优的启发式组合」——它不等于注册时的默认组合
4. 覆盖边界：本周的方法在哪几类输入上可用，边界之外拒绝在哪里发生
5. 落盘与遗留问题
```

纪律检查不打印「我检查过了」，而是**打印检查次数与失败数**。M1/M2 的教训是：
一句「已复核」在笔记里活不过一个季度，一个断言可以。

运行：``python examples/m3w2d7_week2_wrapup.py``
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fjsp_core.models import FJSPInstance
from fjsp_core.objective import evaluate
from fjsp_core.result import ShopResult
from fjsp_core.schedule_validation import schedule_errors, validate_schedule
from fjsp_io.generator import generate_instance
from fjsp_shop import registry
from fjsp_shop.cpsat_fjsp import fjsp_cpsat
from fjsp_shop.fjsp import fjsp_loadbalance, fjsp_random, fjsp_shortest
from fjsp_shop.toy_instances import TOY_INSTANCES

SPEC = {"objective": "makespan", "time_limit": 10.0, "seed": 0}
METHODS = (
    ("fjsp_random", fjsp_random),
    ("fjsp_shortest", fjsp_shortest),
    ("fjsp_loadbalance", fjsp_loadbalance),
    ("fjsp_cpsat", fjsp_cpsat),
)
DISPATCH_RULES = ("ect", "est", "spt", "mwkr")

#: 注册表里**本周**负责的四个名字
WEEK2_METHODS = ("fjsp_random", "fjsp_shortest", "fjsp_loadbalance", "fjsp_cpsat")


def label(instance: FJSPInstance) -> str:
    """给实例起个短名字：订单数 x 每订单工序数 x 机器数。"""
    return (f"{len(instance.jobs)}x{len(instance.jobs[0].operation_ids)}"
            f"x{len(instance.machines)}")


def pad(text: str, width: int) -> str:
    """按**显示宽度**补空格：中日韩字符占两列，``str.ljust`` 按字符数算会错位。"""
    display = sum(2 if ord(char) > 0x2000 else 1 for char in text)
    return text + " " * max(0, width - display)


def machine_histogram(assignment: dict[str, str], machines) -> str:
    """``{M0: 4, M1: 8, ...}``：指派里每台机器分到几道工序。"""
    counts = {machine.id: 0 for machine in machines}
    for machine_id in assignment.values():
        counts[machine_id] += 1
    return "  ".join(f"{mid}:{count}" for mid, count in counts.items())


def main() -> None:
    print("=== M3 Week 2 收口：纪律检查与维度分解 ===")
    print()

    # ---------------------------------------------------------------- 1
    print("== 1. 注册表 ==")
    print(f"  available() = {registry.available()}")
    for name in WEEK2_METHODS:
        print(f"    {name:<16} {registry.describe(name)}")
    missing = registry.describe_missing(list(WEEK2_METHODS))
    print(f"  configs/month3.json 引用的本周四个名字，缺失的 = {missing}")
    print()

    # ---------------------------------------------------------------- 2
    print("== 2. 四条纪律的可执行检查 ==")
    instances = [
        TOY_INSTANCES["tiny_2x2"](),
        TOY_INSTANCES["assign_2x3"](),
        TOY_INSTANCES["gap_2x2"](),
        TOY_INSTANCES["jsp_fixed_2x2"](),
        generate_instance(seed=104, jobs=6, machines=4, operations_per_job=3, flexibility=2),
        generate_instance(seed=105, jobs=10, machines=5, operations_per_job=3, flexibility=3),
    ]
    results: dict[tuple[int, str], ShopResult] = {}
    for index, instance in enumerate(instances):
        for name, solve in METHODS:
            results[(index, name)] = solve(instance, SPEC)

    bound_checks = bound_bad = 0
    for (index, name), result in results.items():
        if name == "fjsp_cpsat":
            continue
        bound_checks += 1
        if result.best_bound is not None or result.gap is not None:
            bound_bad += 1
    print(f"  1) 启发式的 best_bound / gap 必须为 None："
          f"{bound_checks} 次检查，失败 {bound_bad} 次  "
          f"{'PASS' if bound_bad == 0 else 'FAIL'}")

    validator_checks = validator_bad = 0
    for (index, name), result in results.items():
        validator_checks += 1
        errors = schedule_errors(instances[index], result.schedule)
        if errors:
            validator_bad += 1
    print(f"  2) 每个排程过独立验证器：{validator_checks} 次检查，"
          f"失败 {validator_bad} 次  {'PASS' if validator_bad == 0 else 'FAIL'}")

    recompute_gap = 0.0
    for (index, name), result in results.items():
        value = float(evaluate(instances[index], result.schedule, "makespan"))
        recompute_gap = max(recompute_gap, abs(value - float(result.objective)))
    print(f"  3) 目标值可独立重算：最大偏差 = {recompute_gap:.1e}  "
          f"{'PASS' if recompute_gap == 0.0 else 'FAIL'}")

    repeat_bad = 0
    for index, instance in enumerate(instances):
        for name, solve in METHODS:
            again = solve(instance, SPEC)
            if again.schedule != results[(index, name)].schedule:
                repeat_bad += 1
    print(f"  4) 同 spec 两次结果一致：{len(instances) * len(METHODS)} 次检查，"
          f"失败 {repeat_bad} 次  {'PASS' if repeat_bad == 0 else 'FAIL'}")
    print()

    # ---------------------------------------------------------------- 3
    print("== 3. 两个决策维度各值多少（fjsp_6x4_f2，seed 104）==")
    target = instances[4]
    print(f"  实例 = {label(target)}（订单 x 工序 x 机器），CP-SAT 的参考值 = "
          f"{results[(4, 'fjsp_cpsat')].objective:.0f}")
    print("  (a) 只动机器指派（派工规则固定 ect）：")
    values_a: dict[str, float] = {}
    for name, _ in METHODS[:3]:
        values_a[name] = float(results[(4, name)].objective)
        counts = machine_histogram(results[(4, name)].detail["assignment"], target.machines)
        print(f"      {name:<18} {values_a[name]:>4.0f}   每台机器的工序数 = {counts}")
    print(f"      极差 = {max(values_a.values()) - min(values_a.values()):.0f}"
          f"（最好 {min(values_a.values()):.0f} / 最差 {max(values_a.values()):.0f}）")

    print("  (b) 只动工序顺序（指派固定为 assign_shortest 的结果）：")
    values_b = {}
    for rule in DISPATCH_RULES:
        result = fjsp_shortest(target, {**SPEC, "rule": rule})
        values_b[rule] = result.objective
        print(f"      rule={rule:<5} {result.objective:>4.0f}")
    print(f"      极差 = {max(values_b.values()) - min(values_b.values()):.0f}"
          f"（最好 {min(values_b.values()):.0f} / 最差 {max(values_b.values()):.0f}）")

    print("  (c) 两维一起优化（CP-SAT）：")
    print(f"      fjsp_cpsat         {results[(4, 'fjsp_cpsat')].objective:>4.0f}"
          f"   （{results[(4, 'fjsp_cpsat')].status}）")

    print("  (d) 把两个维度各自的偏好组合起来：")
    values_d = {}
    for rule in DISPATCH_RULES:
        values_d[rule] = fjsp_loadbalance(target, {**SPEC, "rule": rule}).objective
    best_rule = min(values_d, key=lambda key: values_d[key])
    for rule in DISPATCH_RULES:
        print(f"      loadbalance + rule={rule:<5} {values_d[rule]:>4.0f}"
              f"{'   <- 最好' if rule == best_rule else ''}")
    print("  结论：机器指派与工序顺序都值得优化，而且两个维度不是简单相加的关系：")
    print(f"  「负载均衡 + {best_rule}」把最好值从 {values_a['fjsp_loadbalance']:.0f} 压到 "
          f"{values_d[best_rule]:.0f}，")
    print("  而注册的三个方法共用 ect 只是控制变量的需要 —— 控制变量是为了让 Day 6 的")
    print("  差异可归因，不代表 ect 就是最好的规则。")
    print()

    # ---------------------------------------------------------------- 4
    print("== 4. 覆盖边界：本周的方法在哪几类输入上可用 ==")
    probe_base = dict(jobs=6, machines=4, operations_per_job=3, flexibility=2)
    plain = generate_instance(seed=300, **probe_base)
    released = generate_instance(seed=300, **probe_base, release_max=5)
    for title, instance in (("纯 FJSP（无额外约束）", plain),
                            ("带释放时间", released),
                            ("大实例（30 道工序）", instances[5])):
        result = fjsp_cpsat(instance, SPEC)
        print(f"  {pad(title, 24)} 可用：status = {result.status:<9} "
              f"objective = {result.objective:.0f}")
    print(f"  带释放时间的那一行前三个释放时间 = "
          f"{[job.release_time for job in released.jobs][:3]}：")
    print("  释放时间是开工时刻的下界，模型与解码器都照做，所以它在覆盖范围之内。")
    print("  边界之外有三类输入会在算之前被拒绝，判据各自可查：")
    print("    目标不是 makespan —— CP-SAT 与 oracle 在建模 / 枚举前拒绝（见 Day 4 与")
    print("      Day 5 各自的拒绝清单）；三个启发式会接受这个目标名，但它们的规则里没有它。")
    print("    空间超过 200000 —— oracle 拒绝：18 道工序的实例已经远超它的能力，")
    print("      大实例上的最优性证据只剩 CP-SAT 自证（第 3 节）。")
    print("    实例带有本模型没有建模的约束 —— require_plain_fjsp 在建模前拒绝：")
    print("      模型少了那几族变量，产出的排程一定过不了独立验证器。")
    print("  拒绝不是缺陷：它把「能证明什么」和「跑得出什么」分开摆在台面上。")
    print()

    # ---------------------------------------------------------------- 5
    print("== 5. 落盘与遗留 ==")
    artifacts = Path(__file__).resolve().parents[1] / "artifacts" / "month3_w2"
    csv_path = artifacts / "compare.csv"
    print(f"  artifacts/month3_w2/compare.csv 存在 = {csv_path.exists()}"
          f"（由 Day 6 的脚本生成）")
    print("  遗留 1：oracle 只能证明 makespan，且空间上限 200000 —— 18 道工序的实例已经")
    print("          远超它的能力，最优性证据在大实例上只剩 CP-SAT 自证。")
    print("  遗留 2：三个启发式的派工规则默认 ect，没有做「规则 x 指派」的系统搜索；")
    print("          它们也不为 makespan 以外的目标做任何事。")
    print("  遗留 3：本周的模型只覆盖「纯 FJSP + 释放时间」；实例里若带有本模型没有")
    print("          建模的约束，四个方法一律在建模前拒绝 —— 本周不对它们做任何事。")
    validate_schedule(instances[0], results[(0, "fjsp_cpsat")].schedule)
    print("  （最后一次 validate_schedule 也通过了。）")


if __name__ == "__main__":
    main()
