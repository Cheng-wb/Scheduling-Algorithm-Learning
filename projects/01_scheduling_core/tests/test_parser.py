"""parser.py 的单元测试：JSON → Instance。"""

import json

from scheduling_core.parser import load_json_instance


def _write_json(tmp_path, data):
    path = tmp_path / "instance.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_load_json_creates_instance(tmp_path):
    data = {
        "machines": [
            {"id": "M1", "name": "Machine 1"},
            {"id": "M2", "name": "Machine 2"},
        ],
        "jobs": [
            {
                "id": "J1",
                "operation_ids": ["O1", "O2"],
                "release_time": 0,
                "due_date": 10,
                "weight": 2.0,
            },
            {
                "id": "J2",
                "operation_ids": ["O3"],
                "release_time": 0,
                "due_date": 8,
                "weight": 1.0,
            },
        ],
        "operations": [
            {
                "id": "O1",
                "job_id": "J1",
                "processing_time": 3,
                "eligible_machine_ids": ["M1", "M2"],
            },
            {
                "id": "O2",
                "job_id": "J1",
                "processing_time": 2,
                "eligible_machine_ids": ["M2"],
            },
            {
                "id": "O3",
                "job_id": "J2",
                "processing_time": 4,
                "eligible_machine_ids": ["M1"],
            },
        ],
    }

    instance = load_json_instance(_write_json(tmp_path, data))

    assert len(instance.machines) == 2
    assert len(instance.jobs) == 2
    assert len(instance.operations) == 3


def test_defaults_when_fields_missing(tmp_path):
    data = {
        "machines": [{"id": "M1", "name": "Machine 1"}],
        "jobs": [{"id": "J1", "operation_ids": ["O1"]}],
        "operations": [
            {
                "id": "O1",
                "job_id": "J1",
                "processing_time": 3,
                "eligible_machine_ids": ["M1"],
            }
        ],
    }

    instance = load_json_instance(_write_json(tmp_path, data))
    job = instance.jobs[0]

    assert job.release_time == 0
    assert job.weight == 1.0
    assert job.due_date is None


def test_list_fields_become_tuples(tmp_path):
    data = {
        "machines": [{"id": "M1", "name": "Machine 1"}],
        "jobs": [{"id": "J1", "operation_ids": ["O1"]}],
        "operations": [
            {
                "id": "O1",
                "job_id": "J1",
                "processing_time": 3,
                "eligible_machine_ids": ["M1"],
            }
        ],
    }

    instance = load_json_instance(_write_json(tmp_path, data))

    assert isinstance(instance.jobs[0].operation_ids, tuple)
    assert isinstance(instance.operations[0].eligible_machine_ids, tuple)
