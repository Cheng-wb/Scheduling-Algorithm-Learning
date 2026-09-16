"""M1W4D6 敏感性分析：从 results.csv 读四组 SA 设置，把理论预期与实测结果分开。

四组：main = T0 10 / cooling 0.98，另有 (0.1, 0.98)、(100, 0.98)、(10, 0.9)。
只读 artifacts/month1_refactored：不写文件、不重跑基准。
"""

import csv
import json
import math
import statistics
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / "artifacts" / "month1_refactored"
MAIN = "main"
ORDER = (MAIN, "sa_t0.1_c0.98", "sa_t100.0_c0.98", "sa_t10.0_c0.9")
LABELS = {
    MAIN: "主配置 10/0.98",
    "sa_t0.1_c0.98": "低温 0.1/0.98",
    "sa_t100.0_c0.98": "高温 100/0.98",
    "sa_t10.0_c0.9": "快冷却 10/0.9",
}
TRACE_INSTANCE = "routes_12"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def fmt(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:.2f}"


def sa_rows(rows: list[dict[str, str]], group: str | None = None) -> list[dict[str, str]]:
    return [
        row
        for row in rows
        if row["algorithm"] == "sa" and (group is None or row["group"] == group)
    ]


def section_one(rows: list[dict[str, str]]) -> dict[str, tuple[float, float]]:
    print("== 1. 四组设置与参数映射（从 temperature / cooling 列验证） ==")
    config = json.loads((ROOT / "configs" / "month1.json").read_text(encoding="utf-8"))
    declared = {
        f"sa_t{item['temperature']}_c{item['cooling']}": (
            item["temperature"],
            item["cooling"],
        )
        for item in config["sensitivity"]
    }
    declared[MAIN] = (config["search"]["temperature"], config["search"]["cooling"])
    mapping: dict[str, tuple[float, float]] = {}
    for group in ORDER:
        selected = sa_rows(rows, group)
        pairs = {(float(row["temperature"]), float(row["cooling"])) for row in selected}
        assert len(pairs) == 1, group
        mapping[group] = pairs.pop()
        temperature, cooling = mapping[group]
        if group != MAIN:
            assert f"sa_t{temperature}_c{cooling}" == group, group
        print(
            f"  {group:<18} temperature={temperature:<6} cooling={cooling:<6}"
            f" SA 运行次数={len(selected)}  来自 configs/month1.json 的声明={declared[group]}"
        )
        assert mapping[group] == declared[group], group
        assert {row["algorithm"] for row in selected} == {"sa"}
    print()
    budgets = {row["budget"] for row in sa_rows(rows)}
    seeds = sorted({row["seed"] for row in sa_rows(rows)})
    instances = sorted({row["instance"] for row in sa_rows(rows)})
    sa_main_instances = sorted({row["instance"] for row in sa_rows(rows, MAIN)})
    print(f"  四组共用 budget={budgets}、seeds={seeds}、instances={len(instances)} 个（与主实验相同：{instances == sa_main_instances}）")
    print("  组名里的 t/c 与数据列 temperature/cooling 完全一致，映射不是靠命名猜的。")
    print("  前两组只改初温（0.1 / 10 / 100，cooling 同为 0.98），第三组只改冷却率（0.9）。")
    print("  因子被分开：初温的影响看 10 与 0.1、100 的差；冷却率的影响看 10/0.98 与 10/0.9 的差。")
    print()
    return mapping


def section_two(rows: list[dict[str, str]]) -> dict[str, dict[str, dict[str, float]]]:
    print("== 2. 每实例 mean / median / best（同一行内比较，三个 seed） ==")
    selected_rows = sa_rows(rows)
    table: dict[str, dict[str, dict[str, float]]] = {}
    objectives: dict[str, str] = {}
    for row in selected_rows:
        objectives.setdefault(row["instance"], row["objective_name"])
    header = f"  {'实例':<14}{'目标':<17}" + "".join(
        f"{LABELS[group]:<19}" for group in ORDER
    )
    print(header)
    print(f"  {'':<31}" + "".join(f"{'均值/中位/最好':<19}" for _ in ORDER))
    best_of_row: dict[str, float] = {}
    for instance in sorted(table_of_rows(selected_rows)):
        table[instance] = {}
        cells = []
        for group in ORDER:
            scores = sorted(
                float(item["objective"])
                for item in selected_rows
                if item["instance"] == instance and item["group"] == group
            )
            assert len(scores) == 3, (instance, group)
            summary = {
                "mean": statistics.mean(scores),
                "median": statistics.median(scores),
                "best": min(scores),
            }
            table[instance][group] = summary
            cells.append(
                f"{fmt(summary['mean'])}/{fmt(summary['median'])}/{fmt(summary['best'])}"
            )
        best_of_row[instance] = min(table[instance][group]["mean"] for group in ORDER)
        print(f"  {instance:<14}{objectives[instance]:<17}" + "".join(f"{cell:<19}" for cell in cells))
    print()
    print("  每实例按均值最小的设置（并列时全部列出）：")
    for instance in sorted(table):
        winners = [
            LABELS[group]
            for group in ORDER
            if table[instance][group]["mean"] == best_of_row[instance]
        ]
        print(f"    {instance:<14}{' / '.join(winners)}（均值 {fmt(best_of_row[instance])}）")
    print("  同一实例内每一行的参考值相同，所以行内可以直接比较。")
    print()
    return table


def table_of_rows(rows: list[dict[str, str]]) -> set[str]:
    return {row["instance"] for row in rows if row["group"] in ORDER}


def section_three(mapping: dict[str, tuple[float, float]]) -> None:
    print("== 3. 理论预期：公式直接读出的方向（理论结论，不是实测） ==")
    print("  SA 接受规则：Δ <= 0 时必接受；Δ > 0 时以概率 exp(-Δ / T) 接受。")
    print("  由此可以推出三条方向性结论：")
    print("    1. T 越小，exp(-Δ/T) 越接近 0，越少接受坏解（趋近贪心下降）。")
    print("    2. T 越大，exp(-Δ/T) 越接近 1，越常接受坏解（更像随机游走）。")
    print("    3. cooling 越小，T 衰减越快，越早进入「几乎只接受改善」的阶段。")
    print()
    print("  用具体数字感受（exp(-Δ/T)）：")
    for delta in (5.0,):
        for temperature in (0.1, 10.0, 100.0):
            print(f"    Δ={delta}，T={temperature:<6} 接受概率 = {math.exp(-delta / temperature):.6g}")
    print()
    print("  T 随评价次数衰减（T_k = T0 * cooling^k，预算 150 次评价，k 从 1 到 149）：")
    for group in ORDER:
        temperature, cooling = mapping[group]
        points = [f"k={k} → {temperature * cooling**k:.4f}" for k in (1, 20, 50, 149)]
        print(f"    {LABELS[group]:<16}" + "；".join(points))
    print("  10/0.9 在 k=20 时 T 已经降到 1.22，10/0.98 还停在 6.68：快冷却确实更早变贪心。")
    print("  注意这三条只说「接受坏解的概率」，没说「最终解更好还是更差」——")
    print("  接受更多坏解可以跳出局部最优，也可能把好解丢掉，方向不确定。")
    print()


def best_groups(table: dict[str, dict[str, dict[str, float]]], instance: str) -> list[str]:
    target = min(table[instance][group]["mean"] for group in ORDER)
    return [LABELS[group] for group in ORDER if table[instance][group]["mean"] == target]


def section_four(table: dict[str, dict[str, dict[str, float]]]) -> None:
    print("== 4. 实际批次结果（实验观察，必须读数据） ==")
    for instance in sorted(table):
        row = table[instance]
        spread = max(row[group]["mean"] for group in ORDER) - min(
            row[group]["mean"] for group in ORDER
        )
        winners = best_groups(table, instance)
        print(
            f"  {instance:<14}均值区间 [{fmt(min(r['mean'] for r in row.values()))},"
            f" {fmt(max(r['mean'] for r in row.values()))}]，极差 {fmt(spread)}，"
            f"均值最小：{' / '.join(winners)}"
        )
    print()
    print("  两个 tiny 实例上四组完全相同（都追平各自 optimum），说明这两个实例已经饱和，")
    print("  测不出参数差异——「同分」是实例太小的结果，不是「温度永远不重要」的证据。")
    print("  较大实例上差异才出现：single_12 快冷却均值最小（255.33），高温最大（282.67）；")
    print("  parallel_24 与 routes_12 是低温均值最小；parallel_12 高温与快冷却并列在 44.33。")
    print("  没有任何一组在六个实例上都最好：质量差异必须逐实例读，不能由公式推出。")
    print()


def trace_stats(path: Path) -> dict[str, float]:
    trace = read_csv(path)
    accepted = 0
    accepted_worse = 0
    for index in range(1, len(trace)):
        previous = float(trace[index - 1]["current"])
        score = float(trace[index]["proposed"])
        if trace[index]["accepted"] == "True":
            accepted += 1
            if score > previous:
                accepted_worse += 1
    return {
        "accepted": accepted,
        "proposals": len(trace) - 1,
        "accepted_worse": accepted_worse,
        "first_best": float(trace[0]["best"]),
        "last_best": float(trace[-1]["best"]),
        "proposed": [float(row["proposed"]) for row in trace[1:]],
    }


def section_five(mapping: dict[str, tuple[float, float]]) -> None:
    print(f"== 5. 同 seed 的轨迹对照（{TRACE_INSTANCE}、seed=0，配对起点 ≠ 同随机流） ==")
    stats = {
        group: trace_stats(BATCH / "runs" / f"{TRACE_INSTANCE}__{group}__sa__0.trace.csv")
        for group in ORDER
    }
    print(f"  {'设置':<18}{'接受/提议':<14}{'接受坏解':<12}{'首个最好':<10}{'末个最好':<10}")
    for group in ORDER:
        item = stats[group]
        print(
            f"  {LABELS[group]:<18}"
            f"{int(item['accepted'])}/{int(item['proposals']):<12}"
            f"{int(item['accepted_worse']):<12}"
            f"{fmt(item['first_best']):<10}{fmt(item['last_best']):<10}"
        )
    reference = stats[MAIN]["proposed"]
    for group in ORDER:
        if group == MAIN:
            continue
        other = stats[group]["proposed"]
        first = next(
            (
                index
                for index in range(min(len(reference), len(other)))
                if reference[index] != other[index]
            ),
            None,
        )
        print(
            f"  与主配置的 proposed 序列首次出现差异的位置：{LABELS[group]} → 第 "
            f"{'-' if first is None else first + 1} 次提议之后"
        )
    print()
    print("  同一个 seed 只是「相同的起始随机状态」，从第一次接受/拒绝判断不同开始，")
    print("  current 就不同，后续 random_move 提出的候选也随之不同，随机流分叉。")
    print("  所以这不是「同一串随机动作下换参数」的受控实验，只是配对起点。")
    print("  轨迹能说明机制：高温接受了最多的坏解，低温几乎不接受坏解（符合第 3 节方向），")
    print("  但机制成立不等于质量更好——该实例上低温这次刚好也拿到了更好的最好值。")
    print()


def section_six(table: dict[str, dict[str, dict[str, float]]]) -> None:
    print("== 6. 并列：三个 seed 上的同分说明不了什么 ==")
    ties = 0
    for instance in sorted(table):
        grouped: dict[float, list[str]] = {}
        for group in ORDER:
            grouped.setdefault(table[instance][group]["mean"], []).append(LABELS[group])
        for value, labels in sorted(grouped.items()):
            if len(labels) > 1:
                ties += 1
                print(f"  {instance:<14}均值 {fmt(value)} 并列：{' / '.join(labels)}")
    assert ties
    print()
    print("  并列组数：" + str(ties) + "。只有三个 seed，两次运行差 1 个单位就能改变排名。")
    print("  同分不能证明「温度不重要」：它只说明在这三个 seed、这批小实例上分辨不出来。")
    print("  小预算也可能是原因之一——低温的收益常在后期才体现，150 次评价可能还没走到那一步。")
    print()


def section_seven() -> None:
    print("== 7. 如果把这四组里最好的一组当成新默认值 ==")
    print("  那就是在这批数据上调参（tuning on the batch）：选中的设置见过这批实例的分数。")
    print("  之后再用同一批数据报告「参数 B 比参数 A 好」，这批数据就已经不是未见数据。")
    print("  正确做法是另留独立测试集（同分布、不参与选择），在它上面报告结果；")
    print("  或者做配对比较并给出不确定性，而不是直接比较四个均值。")
    print("  本项目保留原教学默认值 10/0.98：它是教学设置，不是调优结果，")
    print("  报告里也不声称已完成参数优化。")
    print()


def section_eight() -> None:
    print("== 8. 本月必要修复：不能让「修复前后」混成算法优劣 ==")
    print("  1. 单机规则的机器资格检查：现在 machine 不在 eligible_machine_ids 里会直接")
    print("     抛 illegal assignment，而不是静默排到一台没有资格的机器上。")
    print("  2. JSON 工时不再被静默截断：解析阶段原样保留，由输入校验要求整数，")
    print("     非整数的 processing_time 会被拒绝，而不是被 int() 悄悄改小。")
    print("  3. 非有限权重与非整数时刻被拒绝：weight 必须是有限数，")
    print("     release_time / due_date 必须是整数，nan / inf 一律报错。")
    print()
    print("  这三条改变的是「什么输入算合法」和「什么结果算可行」。")
    print("  修复前跑出来的数字与修复后跑出来的数字，合法性条件不同，")
    print("  直接比较它们会把工程修复读成算法变好/变差。本月的正式批次全部在修复后运行。")
    print()


def main() -> None:
    rows = read_csv(BATCH / "results.csv")
    summary = read_csv(BATCH / "summary.csv")
    split = {group: len(sa_rows(rows, group)) for group in ORDER}
    group_totals = {group: sum(row["group"] == group for row in rows) for group in ORDER}
    print(f"== 0. 本批 SA 运行数：{sum(split.values())} 次（{split}） ==")
    print(f"   主实验 SA {split[MAIN]} 次 = 6 实例 × 3 seed；敏感性 {sum(split.values()) - split[MAIN]} 次 = 6 实例 × 3 设置 × 3 seed。")
    print(f"   同名 main 组一共 {group_totals[MAIN]} 行，其余 {group_totals[MAIN] - split[MAIN]} 行是另外五个算法。")
    print("   敏感性结果按组单独列出，不算独立的新算法。")
    print()

    mapping = section_one(rows)
    table = section_two(rows)
    for item in sa_rows(summary):
        if item["group"] in ORDER:
            key = (item["instance"], item["group"])
            assert table[item["instance"]][item["group"]]["mean"] == float(item["mean"]), key
            assert table[item["instance"]][item["group"]]["best"] == float(item["best"]), key
    section_three(mapping)
    section_four(table)
    section_five(mapping)
    section_six(table)
    section_seven()
    section_eight()

    print("== 9. 结论 ==")
    print("  公式只能给出方向（低温少接受坏解、高温多接受坏解、快冷却更早贪心），")
    print("  最终质量如何必须读 summary.csv 的每实例均值，而且要考虑 seed 数与并列。")
    print("  全部断言通过。")


if __name__ == "__main__":
    main()
