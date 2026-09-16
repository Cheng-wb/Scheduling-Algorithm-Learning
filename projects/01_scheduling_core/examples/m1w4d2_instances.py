"""只读检查已保存的六个基准实例：参数表、输入 SHA-256 与两种 seed 的分工。"""

import csv
import hashlib
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scheduling_core.models import Instance
from scheduling_io.generator import generate_instance
from scheduling_io.parser import load_json_instance

ARTIFACTS = Path(__file__).resolve().parents[1] / "artifacts" / "month1_refactored"
INSTANCES = ARTIFACTS / "instances"
SEED_DEMO_INSTANCE = "parallel_12"
SEED_DEMO_ALGORITHMS = ("lpt", "sa")


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def text_width(value: str) -> int:
    """终端列宽估算：CJK 字符占两列，其余占一列。"""
    return sum(2 if ord(char) > 0x2E7F else 1 for char in value)


def print_table(headers: list[str], rows: list[list[str]]) -> None:
    table = [headers, *rows]
    widths = [
        max(text_width(line[index]) for line in table) for index in range(len(headers))
    ]
    for line in table:
        cells = (
            cell + " " * (width - text_width(cell))
            for cell, width in zip(line, widths, strict=True)
        )
        print("  ".join(cells).rstrip())


def processing_times(instance: Instance) -> dict[str, list[int]]:
    by_job: dict[str, list[int]] = {}
    for operation in instance.operations:
        by_job.setdefault(operation.job_id, []).append(operation.processing_time)
    return by_job


def load_specs(config: dict) -> list[tuple[dict, Instance, Path]]:
    """读取并断言每个实例的作业数、机器数、工序数，与生成器参数一致。"""
    loaded = []
    for spec in config["instances"]:
        name, generator = spec["name"], spec["generator"]
        path = INSTANCES / f"{name}.json"
        instance = load_json_instance(path)
        per_job = {len(job.operation_ids) for job in instance.jobs}
        operations_per_job = generator.get("operations_per_job", 1)
        assert len(per_job) == 1, name
        assert len(instance.jobs) == generator["jobs"], name
        assert len(instance.machines) == generator["machines"], name
        assert per_job == {operations_per_job}, name
        assert len(instance.operations) == len(instance.jobs) * operations_per_job, name
        loaded.append((spec, instance, path))
    return loaded


def main() -> None:
    config = json.loads((ARTIFACTS / "config.json").read_text(encoding="utf-8"))
    rows = read_rows(ARTIFACTS / "results.csv")
    first_row = {row["instance"]: row for row in reversed(rows)}
    loaded = load_specs(config)

    print("=== 1. 实例参数表（输入见 instances/*.json，目标与参考取自 results.csv） ===")
    table = []
    for spec, instance, _ in loaded:
        name, generator = spec["name"], spec["generator"]
        row = first_row[name]
        assert row["objective_name"] == spec["objective"], name
        assert row["reference_type"] == (
            "optimum" if spec.get("exact") else "best-known"
        ), name
        table.append(
            [
                name,
                str(generator["seed"]),
                str(len(instance.jobs)),
                str(len(instance.machines)),
                str(generator.get("operations_per_job", 1)),
                str(len(instance.operations)),
                row["objective_name"],
                row["reference_type"],
                row["reference"],
            ]
        )
    print_table(
        [
            "实例",
            "输入seed",
            "作业",
            "机器",
            "每作业工序",
            "总工序",
            "目标",
            "参考类型",
            "参考值",
        ],
        table,
    )
    print()
    print("注意：routes_12 的 12 是总工序数（6 作业 × 2 工序），不是 12 个作业。")

    print()
    print("=== 2. 输入 JSON 的 SHA-256 与 results.csv 记录的 input_sha256 核对 ===")
    digest_table = []
    for spec, instance, path in loaded:
        name = spec["name"]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == first_row[name]["input_sha256"], name
        assert all(
            row["input_sha256"] == digest for row in rows if row["instance"] == name
        ), name
        assert generate_instance(**spec["generator"]) == instance, name
        digest_table.append([name, digest, first_row[name]["input_sha256"], "一致"])
    print_table(["实例", "sha256(instances/*.json)", "results.csv 记录", "核对"], digest_table)

    print()
    print("=== 3. 逐作业数据（r=release_time，d=due_date，w=weight，p=processing_time） ===")
    for spec, instance, _ in loaded:
        by_job = processing_times(instance)
        print(
            f"[{spec['name']}]  {len(instance.jobs)} 作业 / "
            f"{len(instance.machines)} 机器 / {len(instance.operations)} 工序"
        )
        for job in instance.jobs:
            times = by_job[job.id]
            shown = str(times[0]) if len(times) == 1 else str(tuple(times))
            print(
                f"  {job.id}  r={job.release_time:<2} d={job.due_date:<3} "
                f"w={job.weight:g}  p={shown}"
            )

    print()
    print("=== 4. 两种 seed 的分工（同一实例、同一 input_sha256，只改算法 seed） ===")
    demo_rows = [
        row
        for row in rows
        if row["instance"] == SEED_DEMO_INSTANCE
        and row["group"] == "main"
        and row["algorithm"] in SEED_DEMO_ALGORITHMS
    ]
    assert len(demo_rows) == 6, len(demo_rows)
    assert len({row["input_sha256"] for row in demo_rows}) == 1
    assert all(
        row["input_sha256"] == first_row[SEED_DEMO_INSTANCE]["input_sha256"]
        for row in demo_rows
    )
    print_table(
        ["算法", "算法seed", "run_id", "status", "objective", "evaluations"],
        [
            [
                row["algorithm"],
                row["seed"],
                row["run_id"],
                row["status"],
                row["objective"],
                row["evaluations"],
            ]
            for row in demo_rows
        ],
    )
    print()
    print("输入 seed 交给生成器，决定 p / r / d / w 与机器数：同一实例的 18 条主实验只有一个 input_sha256。")
    print("算法 seed 只交给 Random(seed)，决定搜索动作序列：lpt 三行完全相同，sa 三行的目标值不同。")
    print("所以改输入 seed = 换一道题，改算法 seed = 同一道题换一次随机搜索，二者不能互相代替。")
    print("只保存 seed 不够强：生成器一旦改动（采样区间、due_factor 等），同一个 seed 会生成另一道题，旧结果行就再也指不回原输入。")
    print("保存输入 JSON 并逐行记录 SHA-256 之后，即使生成器变化，仍可用这份 JSON 重算并核对 input_sha256。")


if __name__ == "__main__":
    main()
