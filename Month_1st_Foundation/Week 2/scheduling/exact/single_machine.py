"""Single-machine Big-M models with separate functions for each scheduling goal."""

from math import isclose, isfinite
from ortools.linear_solver import pywraplp
from ..models import Job, ScheduledJob, Schedule
from .. import metrics


def _build_model(jobs, time_limit_ms, big_m):
    if type(time_limit_ms) is not int or time_limit_ms <= 0:
        raise ValueError("time_limit_ms must be a positive integer")
    if len({job.job_id for job in jobs}) != len(jobs):
        raise ValueError("job IDs must be unique")
    if big_m is not None and (
        isinstance(big_m, bool) or not isinstance(big_m, (int, float))
        or not isfinite(big_m) or big_m <= 0
    ):
        raise ValueError("big_m must be a positive finite number")
    # 1. 创建 Solver
    solver = pywraplp.Solver.CreateSolver("CBC")
    if solver is None:
        raise RuntimeError("CBC backend is unavailable in this OR-Tools installation")

    solver.SetTimeLimit(time_limit_ms)


    # 2. 创建变量，S, y
    n_jobs = len(jobs)
    # 所有任务释放后串行加工，给出一个安全的完工时间上界。
    horizon = max((job.release_time for job in jobs), default=0) + sum(job.processing_time for job in jobs)
    if not isfinite(horizon):
        raise ValueError("time horizon must be finite")
    start = {}
    for i, job in enumerate(jobs):
        start[i] = solver.NumVar(job.release_time, horizon - job.processing_time, f"start_{i}")

    order = {}
    for i in range(n_jobs-1):
        for j in range(i+1, n_jobs):
            order[i, j] = solver.BoolVar( f"y_{i}_{j}" )

    # 4. 每对 Job 的顺序约束
    M = horizon if big_m is None else big_m
    for i in range(n_jobs-1):
        for j in range(i+1, n_jobs):
            y = order[i, j]
            solver.Add(start[i] + jobs[i].processing_time <= start[j] + (1 - y) * M)
            solver.Add(start[j] + jobs[j].processing_time <= start[i] + y * M)

    return solver, start, horizon


def _solve_and_extract(solver, start, jobs, algorithm, measure):
    # 6. solve
    status = solver.Solve()
    if status == pywraplp.Solver.INFEASIBLE:
        raise RuntimeError(
            "Single-machine scheduling problem is infeasible."
        )
    if status == pywraplp.Solver.UNBOUNDED:
        raise RuntimeError(
            "Single-machine scheduling problem is unbounded."
        )
    if status != pywraplp.Solver.OPTIMAL:
        status_name = {
            pywraplp.Solver.FEASIBLE: "FEASIBLE (optimality not proven)",
            pywraplp.Solver.NOT_SOLVED: "NOT_SOLVED",
            pywraplp.Solver.ABNORMAL: "ABNORMAL",
        }.get(status, str(status))
        raise RuntimeError(
            f"Solver failed to find an optimal solution. "
            f"Status: {status_name}"
        )

    # 7. 读取结果
    # 数值求解可能产生 1e-12 量级的相邻重叠。仅修正容差内的误差，
    # 不对开始时刻取整，也不掩盖实质重叠或提前释放。
    n_jobs = len(jobs)
    scheduled_jobs = []
    current_time = 0.0
    for i in sorted(range(n_jobs), key=lambda i: start[i].solution_value()):
        job = jobs[i]
        raw_start = start[i].solution_value()
        s = max(raw_start, current_time, job.release_time)
        if s - raw_start > 1e-6:
            raise RuntimeError("solver schedule violates release time or non-overlap")
        scheduled_jobs.append(ScheduledJob(job, 0, s, s + job.processing_time))
        current_time = s + job.processing_time

    schedule = Schedule(scheduled_jobs, algorithm=algorithm)
    schedule.validate()
    if not isclose(measure(schedule), solver.Objective().Value(), rel_tol=1e-7, abs_tol=1e-6):
        raise RuntimeError("extracted schedule does not match the solver value")
    return schedule


def _add_tardiness(solver, start, jobs, horizon):
    delays = []
    for i, job in enumerate(jobs):
        upper = max(0, horizon - job.due_date) if job.due_date is not None else 0
        delay = solver.NumVar(0, upper, f"tardiness_{i}")
        if job.due_date is not None:
            solver.Add(delay >= start[i] + job.processing_time - job.due_date)
        delays.append(delay)
    return delays


def solve_single_machine_makespan(
    jobs: list[Job], time_limit_ms: int = 30_000, *, big_m: float | None = None,
) -> Schedule:
    """Minimize maximum completion time; due dates and weights are not optimized."""
    solver, start, horizon = _build_model(jobs, time_limit_ms, big_m)
    cmax = solver.NumVar(0, horizon, "cmax")
    for i, job in enumerate(jobs):
        solver.Add(cmax >= start[i] + job.processing_time)
    solver.Minimize(cmax)
    return _solve_and_extract(solver, start, jobs, "single_machine_makespan", metrics.makespan)


def solve_single_machine_total_completion(
    jobs: list[Job], time_limit_ms: int = 30_000, *, big_m: float | None = None,
) -> Schedule:
    """Minimize the sum of completion times."""
    solver, start, _ = _build_model(jobs, time_limit_ms, big_m)
    solver.Minimize(solver.Sum(start[i] + job.processing_time for i, job in enumerate(jobs)))
    return _solve_and_extract(solver, start, jobs, "single_machine_total_completion",
                              metrics.total_completion_time)


def solve_single_machine_total_tardiness(
    jobs: list[Job], time_limit_ms: int = 30_000, *, big_m: float | None = None,
) -> Schedule:
    """Minimize total tardiness; jobs without due dates contribute zero."""
    solver, start, horizon = _build_model(jobs, time_limit_ms, big_m)
    delays = _add_tardiness(solver, start, jobs, horizon)
    solver.Minimize(solver.Sum(delays))
    return _solve_and_extract(solver, start, jobs, "single_machine_total_tardiness",
                              metrics.total_tardiness)


def solve_single_machine_weighted_tardiness(
    jobs: list[Job], time_limit_ms: int = 30_000, *, big_m: float | None = None,
) -> Schedule:
    """Minimize weighted tardiness; zero-weight jobs carry no delay penalty."""
    solver, start, horizon = _build_model(jobs, time_limit_ms, big_m)
    delays = _add_tardiness(solver, start, jobs, horizon)
    solver.Minimize(solver.Sum(job.weight * delays[i] for i, job in enumerate(jobs)))
    return _solve_and_extract(solver, start, jobs, "single_machine_weighted_tardiness",
                              metrics.weighted_tardiness)
