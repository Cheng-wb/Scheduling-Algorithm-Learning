"""相同并行机 Pm || Cmax 的分配型 MILP；所有任务必须在时刻 0 可用。"""

from math import isclose

from ortools.linear_solver import pywraplp
from ..models import Job, Schedule, ScheduledJob


def solve_parallel_machine_milp(
    jobs: list[Job],
    num_machines: int,
    time_limit_ms: int = 30_000,
) -> Schedule:
    """只返回已证明最优的排程；超时但仅有可行解时抛出异常。

    交期和权重不参与优化。同机任务按输入顺序串行展开。
    """
    if type(num_machines) is not int or num_machines <= 0:
        raise ValueError("num_machines must be a positive integer")
    if type(time_limit_ms) is not int or time_limit_ms <= 0:
        raise ValueError("time_limit_ms must be a positive integer")
    if len({job.job_id for job in jobs}) != len(jobs):
        raise ValueError("job IDs must be unique")
    if any(job.release_time != 0 for job in jobs):
        raise ValueError("this load model requires release_time == 0 for every job")
    if not jobs:
        return Schedule([], algorithm="parallel_machine_milp", machine_count=num_machines)

    # 1. 创建 solver
    solver = pywraplp.Solver.CreateSolver("CBC")
    if solver is None:
        raise RuntimeError("CBC backend is unavailable in this OR-Tools installation")
    solver.SetTimeLimit(time_limit_ms)

    # 2. 创建 x[i, j]
    n_jobs = len(jobs)
    x = {}
    for i in range(n_jobs):
        for j in range(num_machines):
            x[i, j] = solver.BoolVar(f"x_{i}_{j}")

    # 3. 创建 cmax
    cmax = solver.NumVar(0.0, solver.infinity(), "cmax")

    # 4. 每个 Job 分配一次
    for i in range(n_jobs):
        solver.Add(sum(x[i, j] for j in range(num_machines)) == 1)

    # 5. 每台机器 load <= cmax
    for j in range(num_machines):
        machine_load = sum(x[i, j] * jobs[i].processing_time for i in range(n_jobs))
        solver.Add(machine_load <= cmax)

    # 6. minimize cmax
    solver.Minimize(cmax)

    # 7. solve
    status = solver.Solve()

    # 8. 检查 status
    if status == pywraplp.Solver.INFEASIBLE:
        raise RuntimeError(
            "Parallel-machine scheduling problem is infeasible."
        )

    if status == pywraplp.Solver.UNBOUNDED:
        raise RuntimeError(
            "Parallel-machine scheduling problem is unbounded."
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

    # 9. 读取 x[i, j]
    machine_jobs = {j: [] for j in range(num_machines)}
    for i, job in enumerate(jobs):
        selected = [j for j in range(num_machines) if x[i, j].solution_value() > 0.5]
        if len(selected) != 1:
            raise RuntimeError(f"invalid solver assignment for {job.job_id}")
        machine_jobs[selected[0]].append(job)

    # 10. 构造 ScheduledJob
    scheduled_jobs = []
    for j in range(num_machines):
        current_time = 0
        for job in machine_jobs[j]:
            start_time = current_time
            completion_time = start_time + job.processing_time
            scheduled_jobs.append(ScheduledJob(job, j, start_time, completion_time))
            current_time = completion_time

    # 11. return Schedule
    schedule = Schedule(scheduled_jobs, algorithm="parallel_machine_milp",
                        machine_count=num_machines)
    schedule.validate()
    # 独立核对展开后的完工时刻与求解器目标一致。
    actual_cmax = max(item.completion_time for item in scheduled_jobs)
    if not isclose(actual_cmax, solver.Objective().Value(), rel_tol=1e-7, abs_tol=1e-7):
        raise RuntimeError("extracted schedule does not match the solver objective")

    return schedule
