"""M3 Week 3 Day 7：一周总结——三个模型、一张权重敏感性表、几条被证明的结论。

本周的三条模型各自管一个约束面，合起来才是「能执行」的排程：

```text
释放时间 / 交期 / 权重   ->  三个模型都支持（订单属性，不新增硬约束）
sequence-dependent setup ->  fjsp_cpsat_setup    （紧前工序 circuit 编码）
机器日历 + 计划维护      ->  fjsp_cpsat_calendar （按窗切分）
                              fjsp_cpsat_setup    （起点域限制 + 停机区间）
α·Cmax + β·ΣT + γ·setup ->  fjsp_cpsat_multiobj （加权和 + 归一化）
```

    python examples/m3w3d7_week3_summary.py

脚本先把这一周**唯一一张要反复引用的实验表**重算一遍（实例 T、6 组权重、
3 种归一化口径，共 18 行），再逐行做手算校验，最后把「哪些结论是被证明的、
哪些只是没做」列清楚。表与 `artifacts/month3_w3/` 里的落盘结果同源——
两者都调用 `fjsp_experiments.weight_sensitivity.sweep`。
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fjsp_experiments.weight_sensitivity import (
    NORMALIZATION_MODES,
    SWEEP_SETTINGS,
    crossover_beta,
    single_objective_optima,
    sweep,
    tiny_tradeoff,
)
from fjsp_shop.registry import load_week_modules

#: 六个设置里把 `β` 扫得最开的两个端点，翻转点就在它们之间。
LEFT_SETTING = "cmax_only"
RIGHT_SETTING = "tardiness_heavy"


def main() -> None:
    load_week_modules()
    instance = tiny_tradeoff()

    print("== 一、本周的实例与能力表 ==")
    print("  实例 T：2 机器 4 订单，每单 1 道工序；换型 F0->F1 = 1、F1->F0 = 8。")
    print("  它小到每行都能手算，却同时含 Cmax / ΣT / setup 三个分量的真实取舍。")
    print()
    # 表头与数据都按**显示宽度**补空格：汉字占两列，`:<n` 只数字符不数宽度。
    print(_row("约束", "模型", "验证器标签", widths=CAPABILITY_WIDTHS))
    for row in _capability_rows():
        print(_row(*row, widths=CAPABILITY_WIDTHS))
    print("  `fjsp_cpsat_setup` 与 `fjsp_cpsat_calendar` 是同一个模型的两种**日历编码**：")
    print("  前者用 `blocker`（起点域 + 停机区间），后者用 `split`（每窗一个布尔变量）。")
    print("  Day 5 实测两者同解、规模不同——换模型和换编码不是一回事。")

    print()
    print("== 二、三个单目标最优值（`ideal` 口径的分母） ==")
    optima = single_objective_optima(instance)
    for objective, label in (
        ("makespan", "min Cmax"),
        ("total_tardiness", "min ΣT"),
        ("total_setup_time", "min setup"),
    ):
        item = optima[objective]
        print(f"  {label:<10} = {item['value']:>6.1f}   ({item['status']}, 排程 {item['schedule_key']})")
    print("  三个值只有被**证明**（`OPTIMAL`）才能当分母用；有一个是 `FEASIBLE` 或为 0，")
    print("  `ideal` 口径就用不了——此时驱动拒绝用别的分母顶替，而是把那一格标成跳过。")

    ideal = {
        "cmax": optima["makespan"]["value"],
        "total_tardiness": optima["total_tardiness"]["value"],
        "setup": optima["total_setup_time"]["value"],
    }
    rows = sweep(
        instance,
        name="tiny_tradeoff",
        settings=SWEEP_SETTINGS,
        modes=NORMALIZATION_MODES,
        ideal=ideal,
    )

    print()
    print("== 三、权重敏感性表：6 组权重 x 3 种口径 ==")
    worst = 0.0
    for mode in NORMALIZATION_MODES:
        print()
        print(f"-- 口径 {mode} --")
        print(_row("设置", "α", "β", "γ", "Cmax", "ΣT", "setup", "原始加权和",
                   "归一化加权和", "模型状态", "排程", aligns=("l", "r", "r", "r", "r", "r", "r", "r", "r", "l", "l")))
        for row in rows:
            if row["normalization_mode"] != mode:
                continue
            hand = (
                row["alpha"] * row["cmax"]
                + row["beta"] * row["total_tardiness"]
                + row["gamma"] * row["setup"]
            )
            worst = max(worst, abs(hand - row["weighted_raw"]))
            print(_row(
                row["setting"], f"{row['alpha']:.2f}", f"{row['beta']:.2f}",
                f"{row['gamma']:.1f}", f"{row['cmax']:.0f}",
                f"{row['total_tardiness']:.0f}", f"{row['setup']:.0f}",
                f"{row['weighted_raw']:.2f}", f"{row['weighted_normalized']:.4f}",
                row["model_status"], row["schedule_key"],
                aligns=("l", "r", "r", "r", "r", "r", "r", "r", "r", "l", "l"),
            ))
    print()
    print(f"  逐行手算校验：|α·Cmax + β·ΣT + γ·setup - 求解器报的原始加权和| 最大偏差 = {worst:.1e}")
    print("  「原始加权和」是未归一化的三个分量直接相加；「归一化加权和」是")
    print("  各自除以本口径的分母之后再加权——两者可以排序不同，这正是口径的作用。")

    print()
    print("== 四、翻转点与分母之比 ==")
    print(f"{'口径':<9}{'d_cmax':>8}{'d_ΣT':>9}{'d_setup':>9}{'β*':>9}   β=0 / 0.25 / 4 选出的排程")
    for mode in NORMALIZATION_MODES:
        group = [row for row in rows if row["normalization_mode"] == mode]
        left = _pick(group, LEFT_SETTING)
        middle = _pick(group, "tardiness_light")
        right = _pick(group, RIGHT_SETTING)
        star = crossover_beta(
            left, right, {"cmax": left["d_cmax"], "total_tardiness": left["d_total_tardiness"]}
        )
        pattern = " / ".join(
            "S1" if row["schedule_key"] == left["schedule_key"] else "S2"
            for row in (left, middle, right)
        )
        print(
            f"{mode:<9}{left['d_cmax']:>8.0f}{left['d_total_tardiness']:>9.0f}"
            f"{left['d_setup']:>9.0f}{star:>9.4f}   {pattern}"
        )
    print("  `β* = d_ΣT / d_cmax`：两条候选排程的 ΔCmax 与 ΔΣT 大小相等时，")
    print("  **分母之比就是两个目标的交换率**。口径换了，同一个 β 的含义就换了：")
    print("  `none` 口径下 β = 0.25 选 S1，`ideal` 口径下同一个 β 选 S2——都不是错，")
    print("  是两组分母在说两件不同的事。")

    print()
    print("== 五、这一周被证明的结论 ==")
    print(_row("结论", "证据", widths=CLAIM_WIDTHS))
    for claim, evidence in _claims():
        print(_row(claim, evidence, widths=CLAIM_WIDTHS))
    print()
    print("  每一行的数字都能在本周的脚本里重现，没有一个是估的。")

    print()
    print("== 六、本周没做的事（明确留白，不是遗漏） ==")
    for item in _leftovers():
        print(f"  - {item}")
    print("  把这些留白写清楚，比含糊地宣布「模型已完整」有用：")
    print("  上面每一条都指出了下一步该改哪个函数、哪张表。")


def _capability_rows() -> list[tuple[str, str, str]]:
    return [
        ("释放时间 / 交期 / 权重", "三个模型都支持", "release"),
        ("sequence-dependent setup", "fjsp_cpsat_setup", "overlap（间隔不够时）"),
        ("机器日历 + 计划维护", "fjsp_cpsat_calendar", "calendar / maintenance"),
        ("α·Cmax + β·ΣT + γ·setup", "fjsp_cpsat_multiobj", "（不新增约束）"),
    ]


def _claims() -> list[tuple[str, str]]:
    return [
        ("换型是**顺序相关**的相邻间隔，不是工序的固有属性", "Day 4：相邻对 3 vs 任意前后对 6"),
        ("单机上 Cmax = Σp + Σsetup，两目标必然同向", "Day 4：6 + 3 = 9 = Cmax"),
        ("日历要**先扣维护**再判「放得下」", "Day 5：Y 要 6 分钟，[0, 5) 被筛掉"),
        ("两条日历编码可行集相同、规模不同", "Day 5：11/20 vs 7/12，同解"),
        ("归一化口径决定 β*（交换率）", "本节：1.0000 / 2.3000 / 0.2222"),
        ("单目标最优解可能被多目标解**支配**", "Day 6：(63, 67, 3) vs (63, 55, 3)"),
        ("目标值相等时排程不唯一", "Day 6：setup 都是 2，Cmax 14 vs 19"),
        ("`ideal` 口径在 min setup = 0 时不可用", "驱动 report.md：唯一分母为 0 的边界"),
    ]


def _leftovers() -> list[str]:
    return [
        "换型矩阵只测了 2x2；真实车间的族数决定矩阵是几十乘几十，需要按实例生成。",
        "权重只扫了 6 组、实例只有 2 个；口径的影响还需要更多实例才敢下一般性结论。",
        "归一化只实现了一种线性口径（各自除以一个常数）；非线性口径没实现也没测。",
        "`total_tardiness` 是**不带订单权重**的；`Job.weight` 目前只进 `weighted_tardiness`。",
        "驱动在 `plant_batch` 上的 `ideal` 口径整列跳过，只证明了「跳过是对的」，没给替代方案。",
    ]


def _pick(rows: list[dict], setting: str) -> dict:
    return next(row for row in rows if row["setting"] == setting)


def _row(*cells: object, aligns: tuple[str, ...] | None = None,
         widths: tuple[int, ...] | None = None) -> str:
    """按**显示宽度**排一行表：汉字占两列，`str.ljust` 只数字符数。"""
    modes = aligns or ("l",) * len(cells)
    sizes = widths or COLUMNS
    return "  ".join(
        _pad(str(cell), sizes[index], modes[index]) for index, cell in enumerate(cells)
    )


def _pad(text: str, width: int, mode: str) -> str:
    shown = sum(2 if ord(char) > 0x2E7F else 1 for char in text)
    filler = " " * max(0, width - shown)
    return filler + text if mode == "r" else text + filler


#: 权重表各列的显示宽度；最后一列（排程指纹）不补白，它天然长短不一。
COLUMNS = (22, 6, 6, 5, 6, 6, 7, 11, 13, 9, 0)
#: 能力表与结论表各自的第一列更宽，其余列不留白。
CAPABILITY_WIDTHS = (26, 24, 0)
CLAIM_WIDTHS = (56, 0)


if __name__ == "__main__":
    main()
