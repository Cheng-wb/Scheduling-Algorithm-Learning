"""M3 Week 3 Day 3：多目标归一化与权重敏感性。

同一个实例、同一个求解器，只换归一化口径。三件事要一次看清：

1. 为什么必须归一化：`Cmax`、`ΣT`、`setup` 三个分量都用分钟计，但**不是同一种分钟**
   （排程长度 / 迟交量 / 换型耗时），数值尺度也差得远；原始加权和实际上由
   「数值最大的那个分量」说话；
2. 三种口径的分母从哪来：`none`（1,1,1）、`trivial`（平凡上界）、
   `ideal`（三个单目标的最优值，由本脚本现算）；
3. 权重敏感性：`β` 扫描下选出的排程会不会换、翻转点在哪里，
   以及同一个 `(α, β, γ) = (1, 1, 1)` 在三种口径下会不会选出不同排程。

实例、口径、设置全部取自 `fjsp_experiments.weight_sensitivity`，
所以本脚本打印的表与 `artifacts/month3_w3/report.md` 逐格一致。

    python examples/m3w3d3_normalization_sensitivity.py
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fjsp_experiments.weight_sensitivity import (
    NORMALIZATION_MODES,
    crossover_beta,
    single_objective_optima,
    sweep,
    tiny_tradeoff,
)
from fjsp_shop.registry import load_week_modules

#: `(标签, alpha, beta, gamma)`。前四个是 `γ = 0` 的 `β` 扫描（看翻转点），
#: 最后一个是三个分量等权（看口径会不会改变等权下的选择）。
SETTINGS = (
    ("cmax_only", 1.0, 0.0, 0.0),
    ("tardiness_light", 1.0, 0.25, 0.0),
    ("tardiness_heavy", 1.0, 4.0, 0.0),
    ("balanced", 1.0, 1.0, 1.0),
)


def main() -> None:
    load_week_modules()
    instance = tiny_tradeoff()

    print("== 实例 T ==")
    print("  M0: A(6, F0, J0 d=100)  B(2, F1, J1 d=1)")
    print("  M1: C(5, F0, J2 d=4)    D(2 on M1 / 4 on M0, F1, J3 d=30)")
    print("  换型 F0 -> F1 = 1，F1 -> F0 = 8")

    print()
    print("== 第一步：三个分量的数值尺度差多少 ==")
    optima = single_objective_optima(instance)
    names = {
        "makespan": "min Cmax",
        "total_tardiness": "min ΣT",
        "total_setup_time": "min setup",
    }
    for objective, label in names.items():
        item = optima[objective]
        print(
            f"  {label:<10} = {item['value']:>6.1f}   ({item['status']}, "
            f"排程 {item['schedule_key']})"
        )
    print("  三个分量各自最好的值是 9、2、1，**数值尺度本来就不同**。")
    print("  直接加权相加，等于先替业务主张「一个单位的 Cmax = 一个单位的 ΣT")
    print("  = 一个单位的 setup」；而业务对这三件事的定价几乎不可能正好相等。")

    print()
    print("== 第二步：三种口径的分母 ==")
    rows = sweep(instance, name="tiny_tradeoff", settings=SETTINGS, modes=NORMALIZATION_MODES,
                 ideal={
                     "cmax": optima["makespan"]["value"],
                     "total_tardiness": optima["total_tardiness"]["value"],
                     "setup": optima["total_setup_time"]["value"],
                 })
    for mode in NORMALIZATION_MODES:
        sample = next(row for row in rows if row["normalization_mode"] == mode)
        divisors = (sample["d_cmax"], sample["d_total_tardiness"], sample["d_setup"])
        print(f"  {mode:<8} 分母 (d_cmax, d_ΣT, d_setup) = "
              f"({divisors[0]:g}, {divisors[1]:g}, {divisors[2]:g})")
    print("  `trivial` 用平凡上界，不求解就能算，但很松；`ideal` 用单目标最优值，")
    print("  紧到「每个分量单独看时都是 1」——代价是必须先解三个单目标模型。")
    print("  口径真正决定的是**交换率**：归一化后 `1` 单位 `ΣT` 值 `d_cmax / d_ΣT` 单位 `Cmax`。")

    print()
    print("== 第三步：β 扫描，逐行原始值与归一化值 ==")
    for mode in NORMALIZATION_MODES:
        print()
        print(f"-- 口径 {mode} --")
        print(
            f"{'设置':<17}{'α':>5}{'β':>6}{'γ':>5}{'Cmax':>6}{'ΣT':>6}{'setup':>7}"
            f"{'原始加权和':>12}{'归一化加权和':>14}  {'模型状态':<9}排程"
        )
        for row in rows:
            if row["normalization_mode"] != mode:
                continue
            print(
                f"{row['setting']:<17}{row['alpha']:>5.2f}{row['beta']:>6.2f}"
                f"{row['gamma']:>5.1f}{row['cmax']:>6.0f}{row['total_tardiness']:>6.0f}"
                f"{row['setup']:>7.0f}{row['weighted_raw']:>12.2f}"
                f"{row['weighted_normalized']:>14.4f}  {row['model_status']:<9}"
                f"{row['schedule_key']}"
            )

    print()
    print("== 第四步：翻转点 β* 与手算对照 ==")
    print("`cmax_only` 与 `tardiness_heavy` 两条排程的 Cmax 差 +7、ΣT 差 -7（大小相等），")
    print("所以令加权和相等解出的翻转点恰好是 `β* = d_ΣT / d_cmax`：")
    print("  分母之比就是这两个目标的交换率。")
    print()
    print(f"{'口径':<9}{'d_cmax':>8}{'d_ΣT':>9}{'β* = d_ΣT/d_cmax':>20}   "
          f"{'β=0/0.25/4 选出的排程':<26}预测 vs 观察")
    for mode in NORMALIZATION_MODES:
        selected = [row for row in rows if row["normalization_mode"] == mode]
        left = next(row for row in selected if row["setting"] == "cmax_only")
        mid = next(row for row in selected if row["setting"] == "tardiness_light")
        right = next(row for row in selected if row["setting"] == "tardiness_heavy")
        star = crossover_beta(
            left, right,
            {"cmax": left["d_cmax"], "total_tardiness": left["d_total_tardiness"]},
        )
        pattern = " / ".join(
            "S1" if row["schedule_key"] == left["schedule_key"] else "S2"
            for row in (left, mid, right)
        )
        predicted = "".join(
            "L" if beta < (star or 0.0) else "R" for beta in (0.0, 0.25, 4.0)
        )
        observed = "".join(
            "L" if row["schedule_key"] == left["schedule_key"] else "R"
            for row in (left, mid, right)
        )
        flag = "一致" if predicted == observed else "不一致"
        print(
            f"{mode:<9}{left['d_cmax']:>8.0f}{left['d_total_tardiness']:>9.0f}"
            f"{star:>20.4f}   {pattern:<26}{flag} 预测 {predicted} / 观察 {observed}"
        )
    print()
    print("同一个 `(α, β, γ)`：口径是 `none` 时 `β = 0.25` 选 S1，口径换成 `ideal` 就选 S2。")
    print("`ideal` 的分母把「一个单位的迟交」定价成 `d_cmax / d_ΣT = 9/2` 个单位的完工时间，")
    print("而 `none` 口径的定价是 1 —— 定价变了，同一个 β 的含义就变了，选出的排程自然可能变。")

    print()
    print("== 第五步：等权 (1, 1, 1) 在三种口径下的选择 ==")
    print(f"{'口径':<9}{'Cmax':>6}{'ΣT':>6}{'setup':>7}{'归一化加权和':>14}  排程")
    for mode in NORMALIZATION_MODES:
        row = next(
            row for row in rows
            if row["normalization_mode"] == mode and row["setting"] == "balanced"
        )
        print(
            f"{mode:<9}{row['cmax']:>6.0f}{row['total_tardiness']:>6.0f}"
            f"{row['setup']:>7.0f}{row['weighted_normalized']:>14.4f}  {row['schedule_key']}"
        )
    print()
    print("`none` 与 `trivial` 都选 (9, 9, 2)；`ideal` 换成了 (13, 9, 1) ——")
    print("setup 的分母只有 1，省 1 分钟换型在归一化尺度上等于省 1 整分钟，")
    print("而 Cmax 的分母是 9，多用 4 分钟只值 4/9。于是「用 4 分钟 Cmax 换 1 分钟换型」")
    print("在 `ideal` 口径下划算，在 `none` 口径下不划算。**这不是求解器不稳定，")
    print("是两组分母在说两件事。**")


if __name__ == "__main__":
    main()
