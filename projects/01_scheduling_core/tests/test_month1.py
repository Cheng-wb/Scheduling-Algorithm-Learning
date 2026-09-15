"""跨模块验收：手算、独立穷举、破坏排程、预算和复现。"""

import csv
import json
from dataclasses import replace
from itertools import permutations, product

import pytest

from scheduling_core.generator import generate_instance
from scheduling_core.models import Instance, Job, Machine, Operation
from scheduling_core.objective import (
    makespan,
    total_completion_time,
    total_tardiness,
    weighted_completion_time,
)
from scheduling_core.oracle import exhaustive_optimum
from scheduling_core.parser import (
    load_csv_instance,
    load_json_instance,
    save_json_instance,
)
from scheduling_core.rules import edd, lpt, parallel_lpt, spt, wspt
from scheduling_core.schedule import Schedule, ScheduledOperation
from scheduling_core.schedule_validation import schedule_errors, validate_schedule
from scheduling_core.search import ALGORITHMS, SearchConfig, solve
from scheduling_core.solution import (
    Candidate,
    decode,
    insert,
    neighbors,
    reassign,
    swap,
)
from scheduling_core.validation import validate_instance


def single(p, r=None, d=None, w=None, m=1):
    n = len(p)
    machine_ids = tuple(f"M{i}" for i in range(m))
    return Instance(
        tuple(
            Job(
                f"J{i}",
                (f"O{i}",),
                (r or [0] * n)[i],
                (d or [None] * n)[i],
                (w or [1] * n)[i],
            )
            for i in range(n)
        ),
        tuple(
            Operation(f"O{i}", f"J{i}", value, machine_ids) for i, value in enumerate(p)
        ),
        tuple(Machine(mid, mid) for mid in machine_ids),
    )


# 10 个不同实例，预期值来自显式手算时间线，非用被测算法生成。
# p, r, d, w, rule, m, ordered ends, (Cmax, sum C, sum T, sum wC)
HAND_CASES = [
    ([2, 5], None, None, None, spt, 1, [("O0", 2), ("O1", 7)], (7, 9, 0, 9)),
    ([3, 1], None, [3, 9], None, edd, 1, [("O0", 3), ("O1", 4)], (4, 7, 0, 7)),
    (
        [2, 5, 4],
        None,
        None,
        [1, 5, 1],
        wspt,
        1,
        [("O1", 5), ("O0", 7), ("O2", 11)],
        (11, 23, 0, 43),
    ),
    (
        [4, 2, 3],
        None,
        None,
        None,
        lpt,
        1,
        [("O0", 4), ("O2", 7), ("O1", 9)],
        (9, 20, 0, 20),
    ),
    ([3, 1], [0, 5], [2, 5], None, spt, 1, [("O0", 3), ("O1", 6)], (6, 9, 2, 9)),
    ([10, 1], [0, 1], None, None, spt, 1, [("O0", 10), ("O1", 11)], (11, 21, 0, 21)),
    (
        [2, 2, 2],
        None,
        None,
        None,
        spt,
        1,
        [("O0", 2), ("O1", 4), ("O2", 6)],
        (6, 12, 0, 12),
    ),
    ([1, 3], None, [None, 2], None, edd, 1, [("O1", 3), ("O0", 4)], (4, 7, 1, 7)),
    (
        [4, 3, 2],
        None,
        None,
        None,
        parallel_lpt,
        2,
        [("O0", 4), ("O1", 3), ("O2", 5)],
        (5, 12, 0, 12),
    ),
    ([5], [4], [6], [2], spt, 1, [("O0", 9)], (9, 9, 3, 18)),
]


@pytest.mark.parametrize("p,r,d,w,rule,m,ends,metrics", HAND_CASES)
def test_ten_hand_calculations(p, r, d, w, rule, m, ends, metrics):
    instance = single(p, r, d, w, m)
    schedule = rule(instance)
    validate_schedule(instance, schedule)
    assert [(item.operation_id, item.end_time) for item in schedule.operations] == ends
    assert (
        tuple(
            fn(instance, schedule)
            for fn in (
                makespan,
                total_completion_time,
                total_tardiness,
                weighted_completion_time,
            )
        )
        == metrics
    )


@pytest.mark.parametrize("seed", range(5))
def test_five_independent_enumerations(seed):
    instance = generate_instance(seed, jobs=4, machines=2)
    optimum, schedule, count = exhaustive_optimum(instance)
    validate_schedule(instance, schedule)
    assert count == 384
    actual = min(
        makespan(instance, decode(instance, Candidate(order, assignment)))
        for order in permutations(op.id for op in instance.operations)
        for assignment in product(("M0", "M1"), repeat=4)
    )
    assert actual == optimum
    for algorithm in ALGORITHMS:
        result = solve(instance, SearchConfig(algorithm=algorithm, budget=30))
        assert result.objective >= optimum


@pytest.mark.parametrize(
    "order,assignments,expected",
    [
        (("A", "B", "C"), ("M0", "M1", "M0"), [("A", 2, 5), ("B", 5, 7), ("C", 5, 6)]),
        (("B", "C", "A"), ("M0", "M1", "M0"), [("C", 0, 1), ("A", 2, 5), ("B", 5, 7)]),
        (("B", "C", "A"), ("M0", "M0", "M1"), [("C", 0, 1), ("A", 2, 5), ("B", 5, 7)]),
    ],
)
def test_three_decoder_traces(order, assignments, expected):
    instance = route_instance()
    schedule = decode(instance, Candidate(order, assignments))
    assert [
        (item.operation_id, item.start_time, item.end_time)
        for item in schedule.operations
    ] == expected
    validate_schedule(instance, schedule)
    assert decode(instance, Candidate(order, assignments)) == schedule


def route_instance():
    return Instance(
        (Job("J0", ("A", "B"), 2), Job("J1", ("C",))),
        (
            Operation("A", "J0", 3, ("M0",)),
            Operation("B", "J0", 2, ("M0", "M1")),
            Operation("C", "J1", 1, ("M0", "M1")),
        ),
        (Machine("M0", "M0"), Machine("M1", "M1")),
    )


@pytest.mark.parametrize(
    "kind",
    [
        "precedence",
        "overlap",
        "illegal assignment",
        "missing",
        "duplicate",
        "release",
        "duration",
        "unknown operation",
        "invalid time type",
    ],
)
def test_independent_validator_corruption(kind):
    instance = route_instance()
    items = [
        ScheduledOperation("A", "M0", 2, 5),
        ScheduledOperation("B", "M1", 5, 7),
        ScheduledOperation("C", "M0", 5, 6),
    ]
    if kind == "precedence":
        items[1] = replace(items[1], start_time=2, end_time=4)
    elif kind == "overlap":
        items[2] = replace(items[2], start_time=3, end_time=4)
    elif kind == "illegal assignment":
        items[0] = replace(items[0], machine_id="M1")
    elif kind == "missing":
        items.pop()
    elif kind == "duplicate":
        items.append(items[0])
    elif kind == "release":
        items[0] = replace(items[0], start_time=0, end_time=3)
    elif kind == "duration":
        items[0] = replace(items[0], end_time=6)
    elif kind == "unknown operation":
        items[0] = replace(items[0], operation_id="X")
    else:
        items[0] = replace(items[0], start_time=float("nan"))
    assert any(
        kind in error for error in schedule_errors(instance, Schedule(tuple(items)))
    )
    with pytest.raises(ValueError):
        validate_schedule(instance, Schedule(tuple(items)))


def test_moves_and_boundaries():
    instance = route_instance()
    candidate = Candidate(("A", "B", "C"), ("M0", "M1", "M0"))
    assert insert(candidate, 0, 2).order == ("B", "C", "A")
    assert swap(swap(candidate, 0, 2), 0, 2) == candidate
    moved = list(neighbors(instance, candidate))
    assert len(set(moved)) == len(moved) and candidate not in moved
    for item in moved:
        validate_schedule(instance, decode(instance, item))
    with pytest.raises(IndexError):
        swap(candidate, -1, 0)
    with pytest.raises(ValueError):
        reassign(instance, candidate, 0, "M1")
    with pytest.raises(ValueError):
        decode(instance, replace(candidate, order=("A", "A", "C")))


@pytest.mark.parametrize("algorithm", ALGORITHMS)
@pytest.mark.parametrize("budget", [1, 2, 60])
def test_search_budget_reproducibility_and_incumbent(algorithm, budget):
    instance = generate_instance(40, jobs=6, machines=2, operations_per_job=2)
    config = SearchConfig(
        algorithm=algorithm, budget=budget, seed=9, restart_interval=7
    )
    result = solve(instance, config)
    replay = solve(instance, config)
    assert result.trace == replay.trace
    assert result.schedule == replay.schedule
    assert result.evaluations == len(result.trace) <= budget
    assert result.objective <= result.trace[0].best
    assert result.objective == makespan(instance, result.schedule)
    assert [point.best for point in result.trace] == sorted(
        (point.best for point in result.trace), reverse=True
    )
    if algorithm in ("random", "sa", "multistart"):
        assert result.evaluations == budget
    validate_schedule(instance, result.schedule)


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_singleton_and_empty_terminate(algorithm):
    for instance in (single([1]), Instance((), (), ())):
        result = solve(instance, SearchConfig(algorithm=algorithm, budget=8))
        assert result.evaluations <= 8
        validate_schedule(instance, result.schedule)


def test_ls_local_optimum_and_sa_accepts_worse():
    instance = single([1, 2])
    initial = Candidate(("O0", "O1"), ("M0", "M0"))
    for algorithm in ("first", "best"):
        result = solve(
            instance,
            SearchConfig(algorithm=algorithm, objective="weighted_completion_time"),
            initial,
        )
        assert result.status == "LOCAL_OPTIMUM" and result.objective == 4
    result = solve(
        instance,
        SearchConfig(
            algorithm="sa",
            objective="weighted_completion_time",
            temperature=1e6,
            budget=30,
        ),
    )
    assert any(point.accepted and point.proposed > point.best for point in result.trace)


def test_roundtrip_and_csv(tmp_path):
    instance = generate_instance(1)
    save_json_instance(instance, tmp_path / "input.json")
    assert load_json_instance(tmp_path / "input.json") == instance
    (tmp_path / "machines.csv").write_text("id,name\nM0,Machine\n", encoding="utf-8")
    (tmp_path / "jobs.csv").write_text(
        "id,operation_ids,release_time,due_date,weight\nJ0,O0,0,,2\n", encoding="utf-8"
    )
    (tmp_path / "operations.csv").write_text(
        "id,job_id,processing_time,eligible_machine_ids\nO0,J0,3,M0\n", encoding="utf-8"
    )
    loaded = load_csv_instance(tmp_path)
    validate_instance(loaded)
    assert loaded.jobs[0].due_date is None and loaded.operations[0].processing_time == 3


def test_invalid_inputs_and_rule_eligibility():
    instance = single([3], m=2)
    restricted = replace(
        instance,
        operations=(replace(instance.operations[0], eligible_machine_ids=("M1",)),),
    )
    with pytest.raises(ValueError, match="illegal assignment"):
        spt(restricted, machine_id="M0")
    for bad in (float("nan"), float("inf"), -1):
        with pytest.raises(ValueError):
            validate_instance(
                replace(instance, jobs=(replace(instance.jobs[0], weight=bad),))
            )
    with pytest.raises(ValueError):
        validate_instance(
            replace(
                instance,
                operations=(replace(instance.operations[0], processing_time=1.5),),
            )
        )
    with pytest.raises(ValueError):
        exhaustive_optimum(generate_instance(0, jobs=20))


def test_benchmark_failure_is_recorded(tmp_path, monkeypatch):
    from scheduling_core import benchmark

    config = {
        "instances": [
            {
                "name": "test",
                "generator": {"seed": 1, "jobs": 2},
                "objective": "makespan",
            }
        ],
        "seeds": [0],
        "algorithms": ["random", "sa"],
        "search": {"budget": 2},
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    original = benchmark.solve

    def fail_once(instance, settings):
        if settings.algorithm == "sa":
            raise RuntimeError("injected failure")
        return original(instance, settings)

    monkeypatch.setattr(benchmark, "solve", fail_once)
    monkeypatch.setattr(benchmark, "plot", lambda *args: None)
    output = tmp_path / "out"
    rows = benchmark.run(path, output)
    assert len(rows) == 2 and rows[1]["status"] == "FAILED"
    assert "injected failure" in rows[1]["failure_reason"]
    assert json.loads((output / "failures.json").read_text())[0]["gap"] is None
    with (output / "summary.csv").open() as stream:
        assert sum(int(row["failed"]) for row in csv.DictReader(stream)) == 1
