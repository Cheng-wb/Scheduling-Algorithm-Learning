"""单机、不可抢占、允许释放时间的两两排序 Big-M 模型。"""

from math import isclose, isfinite

from ..models import Job, ScheduledJob, Schedule
from ortools.linear_solver import pywraplp

def solve_single_machine_milp(
        jobs: list[Job],
        time_limit_ms: int = 30_000,
        objective: str = "makespan",
        *,
        big_m: float | None = None,
) -> Schedule:
    """返回已证明最优的排程。big_m 覆盖值仅用于建模敏感性实验。

    默认 M=H 安全；自定义 M 太小时，求解的可能是错误收紧的模型。
    交期、权重不参与这两个目标。
    """

    valid_objectives = {
    "makespan",
    "total_completion_time",
    }

    if objective not in valid_objectives:
        raise ValueError(
            f"Unsupported objective: {objective}. "
            f"Expected one of {sorted(valid_objectives)}."
        )


    if type(time_limit_ms) is not int or time_limit_ms <= 0:
        raise ValueError("time_limit_ms must be a positive integer")
    if len({job.job_id for job in jobs}) != len(jobs):
        raise ValueError("job IDs must be unique")
    if big_m is not None and (
        isinstance(big_m, bool) or not isinstance(big_m, (int, float))
        or not isfinite(big_m) or big_m <= 0
    ):
        raise ValueError("big_m must be a positive finite number")
    if not jobs:
        return Schedule([], algorithm=f"single_machine_milp_{objective}")

    # 1. 创建 Solver
    solver = pywraplp.Solver.CreateSolver("CBC")
    if solver is None:
        raise RuntimeError("SCIP backend is unavailable in this OR-Tools installation")

    solver.SetTimeLimit(time_limit_ms)


    # 2. 创建变量，S, y
    n_jobs = len(jobs)
    # 所有任务释放后串行加工，给出一个安全的完工时间上界。
    horizon = max(job.release_time for job in jobs) + sum(job.processing_time for job in jobs)
    if not isfinite(horizon):
        raise ValueError("time horizon must be finite")
    start = {}
    for i, job in enumerate(jobs):
        start[i] = solver.NumVar(job.release_time, horizon - job.processing_time, f"start_{i}")

    order = {}
    for i in range(n_jobs-1):
        for j in range(i+1, n_jobs):
            order[i, j] = solver.BoolVar( f"y_{i}_{j}" )

    # 3. 每个 Job 的完成时间 <= cmax
    if objective == "makespan":
        cmax = solver.NumVar(0.0, horizon, "cmax")
        for i, job in enumerate(jobs):
            solver.Add(start[i] + job.processing_time <= cmax)

    # 4. 每对 Job 的顺序约束
    M = horizon if big_m is None else big_m
    for i in range(n_jobs-1):
        for j in range(i+1, n_jobs):
            y = order[i, j]
            solver.Add(start[i] + jobs[i].processing_time <= start[j] + (1 - y) * M)
            solver.Add(start[j] + jobs[j].processing_time <= start[i] + y * M)

    # 5. 选择优化目标
    if objective == "makespan":
        solver.Minimize(cmax)
    elif objective == "total_completion_time":
        solver.Minimize(
            solver.Sum(
                start[i] + jobs[i].processing_time
                for i in range(n_jobs)
            )
        )

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

    schedule = Schedule(scheduled_jobs, algorithm=f"single_machine_milp_{objective}")
    schedule.validate()
    actual_objective = (
        scheduled_jobs[-1].completion_time if objective == "makespan"
        else sum(item.completion_time for item in scheduled_jobs)
    )
    if not isclose(actual_objective, solver.Objective().Value(), rel_tol=1e-7, abs_tol=1e-6):
        raise RuntimeError("extracted schedule does not match the solver objective")
    return schedule


def solve_single_machine_makespan(
    jobs: list[Job], time_limit_ms: int = 30_000, objective: str = "makespan",
) -> Schedule:
    """保留原调用入口；新代码使用支持两个目标的 solve_single_machine_milp。"""
    return solve_single_machine_milp(jobs, time_limit_ms, objective)
