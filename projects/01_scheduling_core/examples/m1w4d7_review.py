"""M1W4D7 月度复盘：验收证据表、修正后的结果摘要、复现命令、局限与接口边界。

只读 artifacts/month1_refactored：不写文件、不重跑基准、不重新出图。
"""

import csv
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scheduling_algorithms.oracle import exhaustive_optimum
from scheduling_io.parser import load_json_instance

ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / "artifacts" / "month1_refactored"
NOTES = ROOT.parents[1] / "Month_01_基础系统与框架设计"
OBJECTIVE_LABEL = {"total_tardiness": "ΣT", "makespan": "Cmax"}

EVIDENCE = (
    (
        "≥10 个手算规则与指标案例",
        "tests/test_month1.py::test_ten_hand_calculations（HAND_CASES 10 组）",
        "expected 全部来自手算时间线，不由被测函数生成",
    ),
    (
        "独立拒绝 ≥5 类违规",
        "scheduling_core/schedule_validation.py + test_independent_validator_corruption",
        "9 类破坏：precedence / overlap / illegal assignment / missing / duplicate / "
        "release / duration / unknown operation / invalid time type",
    ),
    (
        "统一五种搜索比较",
        "scheduling_algorithms/search.py（ALGORITHMS、SearchConfig、统一评价预算）",
        "lpt 基线 + random / first / best / multistart / sa 五种搜索，共用初始解与预算口径",
    ),
    (
        "≥5 个小实例枚举",
        "scheduling_algorithms/oracle.py + test_five_independent_enumerations",
        "seed 0..4，每例 4 工序 / 2 机器，384 个组合，oracle 与 decoder 最小值对拍",
    ),
    (
        "一条命令生成表和图",
        "scheduling_experiments/benchmark.py + configs/month1.json",
        "results.csv、summary.csv、report.md、quality/convergence/gantt 三张图",
    ),
    (
        "参数、状态、失败与 gap 留痕",
        "results.csv、metadata.json、runs/、failures.json、verification.json",
        "每次运行留 config/candidate/schedule/trace，失败留 FAILED 与原因，参考标 optimum 或 best-known",
    ),
    (
        "每周七天记录与周报",
        "Week_1..Week_4 的 28 篇 Day 笔记 + week1..week4 周报",
        "笔记按概念组织；周报汇总本周成果、局限与遗留问题",
    ),
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def fmt(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:.2f}"


def section_one(results: list[dict[str, str]]) -> None:
    print("== 1. 本月验收证据表：每条要求对应哪个具体产物 ==")
    for requirement, artifact, note in EVIDENCE:
        print(f"  [{requirement}]")
        print(f"    产物：{artifact}")
        print(f"    说明：{note}")
    print()

    print("  现场核对（全部来自当前 artifacts/，只读）：")
    main = [row for row in results if row["group"] == "main"]
    sensitivity = [row for row in results if row["group"] != "main"]
    print(f"    results.csv 行数 = {len(results)}（main {len(main)} + 敏感性 {len(sensitivity)}）")
    assert (len(results), len(main), len(sensitivity)) == (162, 108, 54)

    failures = json.loads((BATCH / "failures.json").read_text(encoding="utf-8"))
    print(f"    failures.json = {failures}（长度 {len(failures)}）")
    assert failures == []

    runs = sorted((BATCH / "runs").glob("*.json"))
    traces = sorted((BATCH / "runs").glob("*.trace.csv"))
    instances = sorted((BATCH / "instances").glob("*.json"))
    print(f"    runs/*.json = {len(runs)} 个；runs/*.trace.csv = {len(traces)} 个；instances/*.json = {len(instances)} 个")
    assert len(runs) == len(traces) == len(results) == 162
    assert len(instances) == 6

    statuses: dict[str, int] = {}
    for row in results:
        statuses[row["status"]] = statuses.get(row["status"], 0) + 1
    print(f"    status 计数 = {statuses}；FAILED = {statuses.get('FAILED', 0)}")
    assert statuses.get("FAILED", 0) == 0
    assert statuses["BASELINE"] == 18
    assert statuses["LOCAL_OPTIMUM"] == 12

    for name in ("quality.png", "convergence.png", "gantt.png"):
        assert (BATCH / name).is_file(), name
    print("    quality.png / convergence.png / gantt.png 三张图都存在")

    verification = json.loads((BATCH / "verification.json").read_text(encoding="utf-8"))
    for key, value in verification.items():
        print(f"    verification.json: {key} = {value}")
    print("    注：tests_passed=107 是**该批次**记录的数；当前工作树用")
    print("    python -m pytest --collect-only -q 收集到 127 条（Day 5/6 之后新增了测试）。")
    print("    两个数都对，但属于不同时点，引用时必须带上出处。")

    if NOTES.is_dir():
        days = sorted(NOTES.glob("Week_*/Day*.md"))
        weeks = sorted(NOTES.glob("week*.md"))
        print(f"    笔记核对：{len(days)} 篇 Day 笔记 + {len(weeks)} 篇周报（{NOTES.name}）")
    else:
        print(f"    笔记目录未找到（{NOTES}），跳过计数")
    print()


def section_two(results: list[dict[str, str]], summary: list[dict[str, str]]) -> None:
    print("== 2. 修正后的月度结果摘要（读 summary.csv，三个 seed 均值） ==")
    algorithms = ["lpt", "random", "first", "best", "multistart", "sa"]
    references = {}
    objectives = {}
    for row in results:
        references.setdefault(
            row["instance"], (float(row["reference"]), row["reference_type"])
        )
        objectives.setdefault(row["instance"], row["objective_name"])
    print(
        f"  {'实例':<14}{'目标':<6}{'参考':>7}  {'参考类型':<11}"
        + "".join(f"{name:>11}" for name in algorithms)
    )
    rows_by_key = {
        (item["instance"], item["group"], item["algorithm"]): item for item in summary
    }
    for instance in sorted(references):
        reference, kind = references[instance]
        cells = "".join(
            f"{fmt(float(rows_by_key[(instance, 'main', name)]['mean'])):>11}"
            for name in algorithms
        )
        print(
            f"  {instance:<14}{OBJECTIVE_LABEL[objectives[instance]]:<6}"
            f"{fmt(reference):>7}  {kind:<11}{cells}"
        )
    print()

    print("  optimum 与 best-known 的区别：")
    enumerated = {}
    for instance, objective in (
        ("tiny_single", "total_tardiness"),
        ("tiny_parallel", "makespan"),
    ):
        reference, kind = references[instance]
        parsed = load_json_instance(BATCH / "instances" / f"{instance}.json")
        value, _, count = exhaustive_optimum(parsed, objective)
        enumerated[instance] = (value, count)
        assert kind == "optimum" and value == reference, instance
        print(
            f"    {instance:<14}{OBJECTIVE_LABEL[objective]:<5}枚举 {count} 个组合 → optimum = {fmt(value)}"
            f"（与 results.csv 的参考一致，属于可证明的最优）"
        )
    print("    其余四个实例的参考是本批次全部成功运行的最小值，只能标 best-known：")
    print("      single_12 = 250、parallel_12 = 43、parallel_24 = 90、routes_12 = 40")
    print("    它们没有最优性证明：换一批数据、多跑几个 seed，参考值本身就会变。")
    print()

    print("  口径提醒（引用结果时必须一起说）：")
    print("    - 实例：六个合成实例，规模小，不代表工业规模。")
    print("    - 目标：tiny_single 与 single_12 是 ΣT，其余四个是 Cmax；两种目标不互相比较。")
    print("    - 预算：150 次「解码 + 独立验证 + 目标计算」，包含初始化、拒绝与 no-op。")
    print("    - 排名：只在「本批六种方法」内比较，排第一不等于数学最优。")
    print()


def section_three(results: list[dict[str, str]]) -> None:
    print("== 3. 复现命令清单（在项目目录 projects/01_scheduling_core 下运行） ==")
    print("  1. 重跑整批（新目录必须不存在或为空，不覆盖已有实验）：")
    print("     python examples/m1w4d1_benchmark.py --output artifacts/my_run")
    print("  2. 逐次复现已保存的批次（核对目标、状态、评价数、候选、排程与完整 trace）：")
    print("     python examples/m1w4d4_reproduce.py artifacts/month1_refactored")
    print("  3. 全量测试：")
    print("     python -m pytest -q")
    print()
    metadata = json.loads((BATCH / "metadata.json").read_text(encoding="utf-8"))
    print("  本批次的版本证据（metadata.json 记录）：")
    print(
        f"    python={metadata['python']}  platform={metadata['platform']}  "
        f"created_utc={metadata['created_utc']}"
    )
    print(f"    git_commit={metadata['git_commit'][:7]}  working_tree_dirty={metadata['working_tree_dirty']}")
    print(f"    source_sha256={metadata['source_sha256'][:16]}...  config_sha256={metadata['config_sha256'][:16]}...")
    print("  复现脚本的第一道闸门是 source_sha256：源码版本对不上，它直接拒绝执行，")
    print("  而不是给出一批「看起来一样」的数字。所以复现要用记录里的那版源码，")
    print("  不能默认「现在的代码也能复现当初的批次」。")
    print()


def section_four() -> None:
    print("== 4. 诚实局限清单（这些不是待办，是当前的边界） ==")
    limits = (
        "追加式 decoder 有表示偏置：它把工序依次追加到机器末尾，不会插入已有空隙，"
        "所以一部分可行排程永远搜不到。",
        "First/Best 先扫描排列邻域，再扫描机器指派邻域；小预算可能根本走不到指派邻域，"
        "排名里混着「邻域扫描顺序」而不只是算法本身。",
        "SA 允许 no-op（原地 swap/insert 或指派到同一台机器），仍计入一次评价，"
        "所以接受率不能当作有效探索率：接受里包含大量目标值不变的动作。",
        "生成器产出的实例全部是「所有机器都能做所有工序」，机器资格受限的情形没有被覆盖。",
        "三个 seed、六个合成实例只支持教学观察；没有统计显著性声明，也没有置信区间。",
        "参数（T0=10、cooling=0.98）是教学默认值，没有在独立留出集上验证过；"
        "敏感性结果只说明「本批数据上不同设置有差异」，不构成推荐配置。",
    )
    for index, text in enumerate(limits, start=1):
        print(f"  {index}. {text}")
    print()
    print("  另外两条口径上的限制：")
    print("    - best-known gap 只是「与本批最好记录的相对差异」，不是求解器证明的 gap。")
    print("    - 本月没有做邻域消融，也没有做更大规模实例，这些列为后续工作。")
    print()


def section_five() -> None:
    print("== 5. 接口的复用性与本月的边界 ==")
    print("  这些接口是为复用而设计的（不需要重新发明）：")
    print("    - 同一个 Instance 模型：Job / Operation / Machine，输入不可变、可被多算法公平复用。")
    print("    - 同一个 Schedule 与 Candidate 表示：order + assignments 仍然是解的载体。")
    print("    - 同一个独立验证器：validate_schedule 不调用 decoder，任何方法都要过同一道闸门。")
    print("    - 同一套 Objective：Cmax / ΣCj / ΣTj / ΣwjCj / Lmax 由同一个模块计算。")
    print("    - 同一批输入与同一批基线结果：新方法要在这批数据上对比，而不是换一批数据自证。")
    print()
    print("  本月没有做的（能力边界，不是缺陷而是分阶段推进）：")
    print("    - 没有 MILP / CP-SAT：给不出 bound，也报不出真实的求解器 gap。")
    print("    - status 词表只有搜索侧状态：BASELINE / BUDGET / LOCAL_OPTIMUM，")
    print("      没有 OPTIMAL / INFEASIBLE / TIME_LIMIT 这类求解器状态。")
    print("    - 参考口径只有 best-known：它只是「与本批最好记录的差异」，")
    print("      不是求解器证明的 gap，更不能写成 optimum。")
    print("    - 规模与资格分布有限：更大的实例、更一般的机器资格才有区分度。")
    print()


def section_six() -> None:
    print("== 6. 闭卷自测建议（答不出就回到对应日笔记，不必重搭工程） ==")
    for index, item in enumerate(
        (
            "重写两任务相邻交换证明，说清 ΣCj 与 ΣwjCj 的差别。",
            "手推一条 decoder 轨迹：给定 order 与 assignments，写出每道工序的起止时刻。",
            "解释一个验证器错误：例如 precedence 与 overlap 分别在检查什么。",
            "从一条 trace.csv 解释一次 SA 接受：Δ、T 与接受概率的关系。",
            "复现一条结果：从 results.csv 的 run_id 一路回到 run JSON 与 trace，数字对得上。",
        ),
        start=1,
    ):
        print(f"  {index}. {item}")
    print("  周报里的「待学习练习」不假装已经由你完成；没做就是没做。")
    print()


def main() -> None:
    results = read_csv(BATCH / "results.csv")
    summary = read_csv(BATCH / "summary.csv")
    print("=== Month 1 月度复盘 ===")
    print()
    section_one(results)
    section_two(results, summary)
    section_three(results)
    section_four()
    section_five()
    section_six()
    print("== 7. 结论 ==")
    print("  这个月的成果不是「某方法赢了」，而是一套可核对的工作方式：")
    print("  问题语言、不可变输入、独立验证、统一目标、可复现批次、明确标注的参考口径。")
    print("  全部断言通过。")


if __name__ == "__main__":
    main()
