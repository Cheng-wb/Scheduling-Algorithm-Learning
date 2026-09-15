"""export.py 的单元测试：to_gantt_rows 与 write_gantt_csv。"""

from scheduling_core.models import Instance, Job, Machine, Operation
from scheduling_core.schedule import Schedule, ScheduledOperation
from scheduling_io.export import to_gantt_rows, write_gantt_csv


def _instance():
    m0 = Machine(id="M0", name="M0")
    m1 = Machine(id="M1", name="M1")
    o0 = Operation(
        id="O0", job_id="J0", processing_time=8, eligible_machine_ids=("M0", "M1")
    )
    o1 = Operation(
        id="O1", job_id="J1", processing_time=7, eligible_machine_ids=("M0", "M1")
    )
    j0 = Job(id="J0", operation_ids=("O0",))
    j1 = Job(id="J1", operation_ids=("O1",))
    return Instance(jobs=(j0, j1), operations=(o0, o1), machines=(m0, m1))


def _schedule():
    return Schedule(
        operations=(
            ScheduledOperation(
                operation_id="O0", machine_id="M0", start_time=0, end_time=8
            ),
            ScheduledOperation(
                operation_id="O1", machine_id="M1", start_time=0, end_time=7
            ),
        )
    )


def test_to_gantt_rows_six_fields():
    rows = to_gantt_rows(_instance(), _schedule())
    assert rows[0] == {
        "machine_id": "M0",
        "job_id": "J0",
        "operation_id": "O0",
        "start_time": 0,
        "end_time": 8,
        "duration": 8,
    }


def test_to_gantt_rows_sorted_by_machine_then_start():
    schedule = Schedule(
        operations=(
            ScheduledOperation(
                operation_id="O1", machine_id="M1", start_time=0, end_time=7
            ),
            ScheduledOperation(
                operation_id="O0", machine_id="M0", start_time=0, end_time=8
            ),
        )
    )
    rows = to_gantt_rows(_instance(), schedule)
    assert [r["machine_id"] for r in rows] == ["M0", "M1"]


def test_to_gantt_rows_resolves_job_id_from_operation():
    rows = to_gantt_rows(_instance(), _schedule())
    assert rows[1]["job_id"] == "J1"
    assert rows[1]["duration"] == 7


def test_write_gantt_csv_header_and_rows(tmp_path):
    path = tmp_path / "gantt.csv"
    write_gantt_csv(to_gantt_rows(_instance(), _schedule()), path)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "machine_id,job_id,operation_id,start_time,end_time,duration"
    assert lines[1] == "M0,J0,O0,0,8,8"
    assert lines[2] == "M1,J1,O1,0,7,7"
