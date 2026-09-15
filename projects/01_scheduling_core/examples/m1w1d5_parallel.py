"""LPT 并行机手算例与可直接用于甘特图的 JSON 数据。"""

import json
import sys
from dataclasses import asdict
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scheduling_core.models import Instance, Job, Machine, Operation
from scheduling_core.objective import makespan
from scheduling_core.rules import parallel_lpt
from scheduling_core.schedule_validation import validate_schedule


def main() -> None:
    instance = Instance(
        tuple(Job(f"J{i}", (f"O{i}",)) for i in range(3)),
        tuple(
            Operation(f"O{i}", f"J{i}", p, ("M0", "M1"))
            for i, p in enumerate([4, 3, 2])
        ),
        (Machine("M0", "M0"), Machine("M1", "M1")),
    )
    schedule = parallel_lpt(instance)
    validate_schedule(instance, schedule)
    assert makespan(instance, schedule) == 5
    print(json.dumps(asdict(schedule), indent=2))


if __name__ == "__main__":
    main()
