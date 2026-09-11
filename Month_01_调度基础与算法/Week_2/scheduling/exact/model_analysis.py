"""模型分析：LP 松弛与限时求解信息，不把分数解当作排程。"""

from time import perf_counter
from ortools.linear_solver import pywraplp
from .single_machine import _build_model


def solve_parallel_relaxation(jobs, machines):
    if type(machines) is not int or machines<=0:
        raise ValueError('machines must be a positive integer')
    if any(j.release_time!=0 for j in jobs) or len({j.job_id for j in jobs})!=len(jobs):
        raise ValueError('requires unique jobs released at zero')
    solver=pywraplp.Solver.CreateSolver('GLOP')
    if solver is None:
        raise RuntimeError('GLOP backend unavailable')
    x={(i,k):solver.NumVar(0,1,f'x_{i}_{k}') for i in range(len(jobs)) for k in range(machines)}
    cmax=solver.NumVar(0,solver.infinity(),'cmax')
    for i in range(len(jobs)):
        solver.Add(sum(x[i,k] for k in range(machines))==1)
    for k in range(machines):
        solver.Add(sum(j.processing_time*x[i,k] for i,j in enumerate(jobs))<=cmax)
    solver.Minimize(cmax)
    status=solver.Solve()
    if status!=pywraplp.Solver.OPTIMAL:
        raise RuntimeError(f'LP status={status}')
    return {'bound':solver.Objective().Value(),
            'fractions':[[x[i,k].solution_value() for k in range(machines)] for i in range(len(jobs))]}


def analyze_total_completion(jobs, *, time_limit_ms=1000, big_m=None):
    start_time=perf_counter()
    solver,starts,_=_build_model(jobs,time_limit_ms,big_m)
    solver.Minimize(solver.Sum(starts[i]+job.processing_time for i,job in enumerate(jobs)))
    status=solver.Solve()
    names={solver.OPTIMAL:'OPTIMAL',solver.FEASIBLE:'FEASIBLE',solver.INFEASIBLE:'INFEASIBLE',
           solver.UNBOUNDED:'UNBOUNDED',solver.ABNORMAL:'ABNORMAL',solver.NOT_SOLVED:'NOT_SOLVED'}
    has_solution=status in (solver.OPTIMAL,solver.FEASIBLE)
    return dict(status=names.get(status,str(status)), objective=solver.Objective().Value() if has_solution else None,
                bound=solver.Objective().BestBound() if status in (solver.OPTIMAL,solver.FEASIBLE,solver.NOT_SOLVED) else None,
                runtime=perf_counter()-start_time, nodes=solver.nodes())
