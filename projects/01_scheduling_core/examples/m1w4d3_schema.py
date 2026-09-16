"""只读检查结果 schema：三种粒度、一次运行的重算、status 词表与 gap 复算。"""

import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scheduling_core.schedule import Schedule, ScheduledOperation
from scheduling_core.schedule_validation import schedule_errors, validate_schedule
from scheduling_algorithms.search import OBJECTIVES
from scheduling_io.parser import load_json_instance

ARTIFACTS = Path(__file__).resolve().parents[1] / "artifacts" / "month1_refactored"
CHECKED_RUN = "routes_12__main__sa__0"
STATUS_VOCABULARY = (
    ("BASELINE", "规则基线完成，未进入搜索循环"),
    ("BUDGET", "评价预算用尽，搜索被上限截断"),
    ("LOCAL_OPTIMUM", "邻域内已无严格改善的邻居，提前停机"),
    ("FAILED", "该次求解抛异常，结果行保留错误原因"),
)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def header_of(path: Path) -> list[str]:
    with path.open(encoding="utf-8", newline="") as stream:
        return next(csv.reader(stream))


def print_fields(label: str, names: list[str], note: str) -> None:
    print(f"{label}（{note}）")
    for index, name in enumerate(names, start=1):
        print(f"  {index:>2}. {name}")


def load_schedule(saved: dict) -> Schedule:
    return Schedule(
        tuple(
            ScheduledOperation(
                item["operation_id"],
                item["machine_id"],
                item["start_time"],
                item["end_time"],
            )
            for item in saved["schedule"]["operations"]
        )
    )


def main() -> None:
    results = read_rows(ARTIFACTS / "results.csv")
    summary = read_rows(ARTIFACTS / "summary.csv")
    metadata = json.loads((ARTIFACTS / "metadata.json").read_text(encoding="utf-8"))
    run_files = sorted((ARTIFACTS / "runs").glob("*.json"))
    trace_files = sorted((ARTIFACTS / "runs").glob("*.trace.csv"))
    assert len(results) == 162 and len(summary) == 54
    assert len(run_files) == 162 and len(trace_files) == 162

    print("=== 1. 三种粒度与字段清单 ===")
    print_fields(
        "粒度 1：results.csv",
        list(results[0]),
        f"{len(results)} 行，每次运行一行，批次层唯一入口",
    )
    print()
    print("粒度 2：runs/<run_id>.json（一次运行的配置、最好候选与完整排程）")
    for index, key in enumerate(("config", "candidate", "schedule"), start=1):
        print(f"  {index:>2}. {key}")
    print("     config     → " + ", ".join(json.loads(run_files[0].read_text(encoding="utf-8"))["config"]))
    print("     candidate  → order, assignments")
    print("     schedule   → operations[{operation_id, machine_id, start_time, end_time}]")
    print()
    print_fields(
        "粒度 3：runs/<run_id>.trace.csv",
        header_of(trace_files[0]),
        f"{len(trace_files)} 个文件，每次评价一行",
    )
    print()
    print("附：summary.csv（实例 × 组 × 算法，跨 seed 汇总）")
    print("    " + ", ".join(list(summary[0])))
    print("附：metadata.json（批次级环境与版本证据）")
    print("    " + ", ".join(metadata))
    print()
    print("三种粒度不能混进一张表：results.csv 是运行层，run JSON 是解层，trace 是过程层；")
    print("把逐评价的 trace 与逐运行的 results 拼在一起，行数就对不上了。")

    print()
    print("=== 2. 重开一条保存的运行，重新验证排程并重算目标 ===")
    row = next(item for item in results if item["run_id"] == CHECKED_RUN)
    instance_path = ARTIFACTS / "instances" / f"{row['instance']}.json"
    digest = hashlib.sha256(instance_path.read_bytes()).hexdigest()
    assert digest == row["input_sha256"]
    instance = load_json_instance(instance_path)
    saved = json.loads((ARTIFACTS / "runs" / f"{CHECKED_RUN}.json").read_text(encoding="utf-8"))
    schedule = load_schedule(saved)
    validate_schedule(instance, schedule)
    assert not schedule_errors(instance, schedule)
    objective = OBJECTIVES[row["objective_name"]]
    recomputed = float(objective(instance, schedule))
    recorded = float(row["objective"])
    assert recomputed == recorded
    assert len(schedule.operations) == len(instance.operations)
    assert len(saved["candidate"]["order"]) == len(instance.operations)
    assert len(saved["candidate"]["assignments"]) == len(instance.operations)
    load_by_machine: dict[str, int] = {}
    for item in schedule.operations:
        load_by_machine[item.machine_id] = load_by_machine.get(item.machine_id, 0) + (
            item.end_time - item.start_time
        )
    print(f"run_id            : {CHECKED_RUN}")
    print(f"输入              : instances/{row['instance']}.json，sha256 与结果行一致")
    print(f"参数              : " + ", ".join(f"{k}={v}" for k, v in saved["config"].items()))
    print(f"重算输入          : {len(instance.jobs)} 作业 / {len(instance.machines)} 机器 / {len(instance.operations)} 工序")
    print(f"重算排程          : {len(schedule.operations)} 道已排定工序，validate_schedule 无错误")
    print(f"机器负载          : " + ", ".join(f"{m}={load_by_machine[m]}" for m in sorted(load_by_machine)))
    print(f"重算目标({row['objective_name']}): {recomputed}")
    print(f"results.csv 记录   : {recorded}")
    print(f"两者相等           : {recomputed == recorded}；max(end_time) = {max(item.end_time for item in schedule.operations)}")
    print(f"复算函数           : {objective.__name__}（按 objective_name 反查指标函数，不重新求解）")

    print()
    print("=== 3. status 词表与本批次实际计数 ===")
    counts = Counter(item["status"] for item in results)
    for name, meaning in STATUS_VOCABULARY:
        print(f"  {name:<14} {counts.get(name, 0):>3}  {meaning}")
    assert sum(counts.values()) == len(results)
    assert counts.get("FAILED", 0) == 0
    print(f"  failures.json 内容: {json.loads((ARTIFACTS / 'failures.json').read_text(encoding='utf-8'))}")
    print("BASELINE/BUDGET/LOCAL_OPTIMUM 都不是最优性声明；本批次只有两个 tiny 实例的参考由枚举给出。")
    early = [item["run_id"] for item in results if item["status"] == "LOCAL_OPTIMUM"]
    print(f"LOCAL_OPTIMUM 出现在: {', '.join(sorted(early))}")

    print()
    print("=== 4. gap 公式 gap=(value-reference)/max(1,|reference|) 复算 ===")
    examples = ["tiny_single__main__lpt__0", "parallel_24__main__lpt__0"]
    for run_id in examples:
        item = next(row for row in results if row["run_id"] == run_id)
        value, reference = float(item["objective"]), float(item["reference"])
        recomputed_gap = (value - reference) / max(1.0, abs(reference))
        assert recomputed_gap == float(item["gap"])
        print(
            f"  {run_id:<28} ({value}-{reference})/max(1,{abs(reference)}) = "
            f"{recomputed_gap:<20} 记录值 {item['gap']}"
        )
    for item in results:
        if item["gap"]:
            value, reference = float(item["objective"]), float(item["reference"])
            assert (value - reference) / max(1.0, abs(reference)) == float(item["gap"])
    references = sorted({float(item["reference"]) for item in results})
    print(f"  全部 {len(results)} 行复算一致；reference 取值集合 = {references}")
    print("  本批次 reference 最小为 36，没有参考为 0 的行；代入 0 时 (value-0)/max(1,0)=value，退化为绝对差而不是百分比。")


if __name__ == "__main__":
    main()
