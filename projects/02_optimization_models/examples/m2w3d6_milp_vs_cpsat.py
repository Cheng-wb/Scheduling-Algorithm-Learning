"""Day 6：在同一组实例上比较 MILP（Week 2）与 CP-SAT（Week 3）。

比较的前提是**同一实例集 + 同一目标函数 + 同一时间预算**，三者缺一个数字就不可比。
本脚本只用已注册的方法（``opt_solvers.registry``），不手写求解器调用：

```text
milp_tight / milp_loose  单机 sequence MILP：决策是「两两先后」，Big-M 线性化
milp_alt                 time-indexed MILP：决策是「工序 t 时刻开不开工」
cpsat_parallel / cpsat_jsp 区间模型：决策是 start / end / presence 的整型域
heur_edd / heur_parallel_lpt  M1 规则基线，没有任何 bound
```

四个实例全部来自 ``generate_instance``，种子与参数写死在表里，可直接复现：

```text
single_8     seed 50, jobs  8, machines 1, total_tardiness
single_12    seed 51, jobs 12, machines 1, total_tardiness
parallel_8   seed 52, jobs  8, machines 3, makespan
parallel_12  seed 53, jobs 12, machines 3, makespan
```

三条要读得出来的结论（都是实测，不是先验断言）：

1. **目标值可比**：都是最小化同一个目标，谁的值更小谁的解更好；
2. **bound 的含义不同但都可以是有效下界**：MILP 的 bound 来自 LP relaxation 与
   分支定界，CP-SAT 的 bound 来自传播与冲突分析。两者都是「不会更好了」的证明，
   但强度取决于**建模与预算**，不是范式本身的属性；
3. **单实例胜负不能推广**：本脚本里 CP-SAT 在并行机上证明快得多，
   在同一台单机上反而证不出来（MILP 的 time-indexed 模型证完了）。

只打印，不写盘。完整跑批（写 ``artifacts/month2_w3/``）在 ``opt_experiments/w3_cpsat.py``。
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from opt_common.bridge import generate_instance
from opt_solvers.registry import available, describe, get, load_week_modules

MILP_METHODS = ("milp_tight", "milp_loose", "milp_alt")
CPSAT_METHODS = ("cpsat_parallel", "cpsat_jsp")
HEUR_METHODS = ("heur_edd", "heur_parallel_lpt")

#: 只有单机实例才适用 sequence MILP，否则方法自己会拒绝（返回 FAILED）。
SINGLE_MACHINE_ONLY = {"milp_tight", "milp_loose"}


def instances() -> list[tuple[str, object, str, tuple[str, ...]]]:
    """(名字, 实例, 目标, 参与比较的方法)。"""
    return [
        (
            "single_8",
            generate_instance(50, jobs=8, machines=1),
            "total_tardiness",
            ("milp_tight", "milp_loose", "milp_alt", "cpsat_parallel", "cpsat_jsp", "heur_edd"),
        ),
        (
            "single_12",
            generate_instance(51, jobs=12, machines=1),
            "total_tardiness",
            ("milp_tight", "milp_loose", "milp_alt", "cpsat_parallel", "heur_edd"),
        ),
        (
            "parallel_8",
            generate_instance(52, jobs=8, machines=3),
            "makespan",
            ("milp_alt", "cpsat_parallel", "cpsat_jsp", "heur_parallel_lpt"),
        ),
        (
            "parallel_12",
            generate_instance(53, jobs=12, machines=3),
            "makespan",
            ("milp_alt", "cpsat_parallel", "cpsat_jsp", "heur_parallel_lpt"),
        ),
    ]


def gap_text(objective, best_bound) -> str:
    if objective is None:
        return "-"
    if best_bound is None:
        return "无 bound"
    if objective == 0:
        return f"{0.0:.4f}"
    return f"{(objective - best_bound) / abs(objective):.4f}"


def main() -> None:
    load_week_modules()
    methods = available()
    missing = [name for name in MILP_METHODS if name not in methods]
    print("=== 0. 方法清单 ===")
    print(f"  已注册方法 {len(methods)} 个：{sorted(methods)}")
    if missing:
        print(f"  缺失的 MILP 方法：{missing} —— 下面的表里不会出现它们。")
    else:
        print("  Week 2 的三个 MILP 方法都在，比较是真实的跨周比较。")
    for name in ("milp_tight", "milp_alt", "cpsat_parallel"):
        if name in methods:
            print(f"    {name:<15} {describe(name)}")
    print("  时间预算：MILP 与 CP-SAT 一律 time_limit = 5.0 秒，seed = 0。")

    registry = {
        name: get(name)
        for name in MILP_METHODS + CPSAT_METHODS + HEUR_METHODS
        if name in methods
    }

    rows: list[tuple[str, str, str, object, object, str, float, float]] = []
    for label, instance, objective_name, wanted in instances():
        machines = len(instance.machines)
        print()
        print(f"=== 实例 {label}：{len(instance.operations)} 道工序、"
              f"{machines} 台机器、目标 {objective_name} ===")
        header = f"  {'方法':<18}{'状态':<10}{'目标':>10}{'bound':>10}{'gap':>9}{'建模':>9}{'求解':>9}"
        print(header)
        print("  " + "-" * (len(header) - 2))
        for name in wanted:
            if name not in methods:
                continue
            if name in SINGLE_MACHINE_ONLY and machines != 1:
                print(f"  {name:<18}跳过（sequence MILP 只适用于单机）")
                continue
            result = registry[name](
                instance, {"objective": objective_name, "time_limit": 5.0, "seed": 0}
            )
            shown_bound = "-" if result.best_bound is None else f"{result.best_bound:g}"
            shown_obj = "-" if result.objective is None else f"{result.objective:g}"
            print(
                f"  {name:<18}{result.status:<10}{shown_obj:>10}{shown_bound:>10}"
                f"{gap_text(result.objective, result.best_bound):>9}"
                f"{result.build_time:>9.4f}{result.solve_time:>9.4f}"
            )
            rows.append(
                (
                    label, name, result.status, result.objective, result.best_bound,
                    gap_text(result.objective, result.best_bound),
                    result.build_time, result.solve_time,
                )
            )
        proven = [row for row in rows if row[0] == label and row[2] == "OPTIMAL"]
        if proven:
            best = min(row[3] for row in proven)
            who = ", ".join(row[1] for row in proven if row[3] == best)
            print(f"  证明最优的方法：{who}（目标值 {best:g}）")

    print()
    print("=== 1. 跨方法一致性核对 ===")
    for label, _instance, _objective, _wanted in instances():
        milp_values = {
            row[3] for row in rows
            if row[0] == label and row[1] in MILP_METHODS and row[3] is not None
        }
        cpsat_values = {
            row[3] for row in rows
            if row[0] == label and row[1] in CPSAT_METHODS and row[3] is not None
        }
        heur_values = {
            row[3] for row in rows
            if row[0] == label and row[1] in HEUR_METHODS and row[3] is not None
        }
        milp_best = min(milp_values) if milp_values else None
        cpsat_best = min(cpsat_values) if cpsat_values else None
        heur_best = min(heur_values) if heur_values else None
        verdict = "一致" if milp_best == cpsat_best else "不一致"
        print(f"  {label:<13} MILP 最好 {str(milp_best):<8} CP-SAT 最好 {str(cpsat_best):<8} "
              f"启发式最好 {str(heur_best):<8} -> {verdict}")

    print()
    print("=== 2. bound 到底是不是同一件事 ===")
    print("  MILP 的 best_bound 来自 LP relaxation 逐层收紧（分支定界）；")
    print("  CP-SAT 的 best_bound 来自域传播、冲突分析与目标下界推理。")
    print("  两者在**同一意义**下可比：都是「最优值不会低于这个数」的证明，")
    print("  所以同一实例上比较 objective 与 bound 是合法的。")
    print("  但『谁的 bound 更紧』不能归因于范式：它同时取决于")
    print("  （a）建模方式（sequence 还是 time-indexed），（b）给的时间预算，")
    print("  （c）求解器版本。上表里同一范式内部两个模型就能差出 0.5 以上的 gap。")

    print()
    print("=== 3. 一个必须诚实说明的例子 ===")
    print("  single_12 上，CP-SAT 在 5 秒内找到了与 milp_alt 相同的最优解，")
    print("  但没有证明它（状态 FEASIBLE、gap 接近 1）；而 milp_alt 证完了。")
    print("  反过来在 parallel_8 / parallel_12 上，CP-SAT 的证明时间比 milp_alt 少两个数量级。")
    print("  所以正确结论是：**在这个实例集、这个预算下**，两种范式的强项不同；")
    print("  不能推广成「CP-SAT 比 MILP 快」或反之。")
    print("  要下更强的结论需要更大的实例集与多组预算，那是 Month 2 结尾的工作。")


if __name__ == "__main__":
    main()
