"""LPT 并行机手算例与可直接用于甘特图的结构化数据。"""

import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scheduling_core.models import Instance, Job, Machine, Operation
from scheduling_core.objective import makespan
from scheduling_core.schedule_validation import validate_schedule
from scheduling_algorithms.rules import parallel_lpt, parallel_makespan_lower_bound
from scheduling_io.export import to_gantt_rows, write_gantt_csv


def main() -> None:
    instance = Instance(
        tuple(Job(f"J{i}", (f"O{i}",)) for i in range(4)),
        tuple(
            Operation(f"O{i}", f"J{i}", p, ("M0", "M1"))
            for i, p in enumerate([8, 7, 6, 5])
        ),
        (Machine("M0", "M0"), Machine("M1", "M1")),
    )

    schedule = parallel_lpt(instance)
    validate_schedule(instance, schedule)

    value = makespan(instance, schedule)
    lower = parallel_makespan_lower_bound(instance)
    assert value == 13 and lower == 13

    rows = to_gantt_rows(instance, schedule)
    csv_path = Path(__file__).resolve().parent / "lpt_gantt.csv"
    write_gantt_csv(rows, csv_path)

    print(json.dumps({"makespan": value, "lower_bound": lower}, indent=2))
    print(json.dumps(rows, indent=2))
    print("wrote", csv_path.name)


if __name__ == "__main__":
    main()
