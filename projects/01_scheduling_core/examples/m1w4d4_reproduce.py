"""用保存的输入与配置重算，核对每次成功运行的结果、排程和轨迹。"""

import argparse
import csv
import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scheduling_experiments.benchmark import ROOT, source_hash
from scheduling_io.parser import load_json_instance
from scheduling_algorithms.search import SearchConfig, solve


def reproduce(directory: Path) -> int:
    metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    if source_hash() != metadata["source_sha256"]:
        raise ValueError(
            "source hash differs from recorded run; use its original source version"
        )
    with (directory / "results.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    checked = 0
    for row in rows:
        if row["status"] == "FAILED":
            continue
        path = directory / "instances" / f"{row['instance']}.json"
        if hashlib.sha256(path.read_bytes()).hexdigest() != row["input_sha256"]:
            raise ValueError(f"input hash mismatch: {row['run_id']}")
        saved = json.loads(
            (directory / "runs" / f"{row['run_id']}.json").read_text(encoding="utf-8")
        )
        result = solve(load_json_instance(path), SearchConfig(**saved["config"]))
        actual = json.loads(
            json.dumps(
                {
                    "candidate": asdict(result.candidate),
                    "schedule": asdict(result.schedule),
                }
            )
        )
        if any(actual[key] != saved[key] for key in actual):
            raise ValueError(f"schedule/candidate mismatch: {row['run_id']}")
        if (
            result.objective != float(row["objective"])
            or result.evaluations != int(row["evaluations"])
            or result.status != row["status"]
        ):
            raise ValueError(f"result mismatch: {row['run_id']}")
        with (directory / "runs" / f"{row['run_id']}.trace.csv").open(
            encoding="utf-8", newline=""
        ) as stream:
            trace = list(csv.DictReader(stream))
        expected = [
            {
                key: "" if value is None else str(value)
                for key, value in asdict(point).items()
            }
            for point in result.trace
        ]
        if trace != expected:
            raise ValueError(f"trace mismatch: {row['run_id']}")
        checked += 1
    print(
        f"reproduced={checked}, recorded_failures={len(rows) - checked}; timing intentionally excluded"
    )
    return checked


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "directory",
        type=Path,
        nargs="?",
        default=ROOT / "artifacts" / "month1_refactored",
    )
    reproduce(parser.parse_args().directory)
