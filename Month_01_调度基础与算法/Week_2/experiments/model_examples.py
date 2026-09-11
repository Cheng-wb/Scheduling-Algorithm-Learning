"""建模、松弛、求解状态和小实例枚举的实验。"""

from itertools import permutations, product
from math import isclose
from scheduling.models import Job
from scheduling.scheduler import schedule_sequence
from scheduling.evaluator import evaluate
from scheduling.validation import validate_schedule
from scheduling.exact.parallel_machine import solve_parallel_machine_milp
from scheduling.exact.single_machine import solve_single_machine_total_completion, solve_single_machine_total_tardiness
from scheduling.exact.model_analysis import solve_parallel_relaxation, analyze_total_completion
from experiments.tables import print_table


def formulation():
    print('Parameters: p=[3,3,3], m=2')
    print('Variables: x[i,k] binary; Cmax >= 0')
    print('Each job: sum_k x[i,k] = 1')
    print('Each machine: sum_i p[i]*x[i,k] <= Cmax')
    print('Objective: minimize Cmax; machine order is irrelevant to this load model.')


def relaxation():
    tasks=[Job(f'J{i}',3) for i in range(1,4)]
    lp=solve_parallel_relaxation(tasks,2)
    schedule=solve_parallel_machine_milp(tasks,2)
    validate_schedule(schedule,tasks)
    integer=evaluate(schedule)['makespan']
    print_table('Fractional assignments',['Job','M0','M1'],[(j.job_id,*[f'{v:.3f}' for v in row]) for j,row in zip(tasks,lp['fractions'])],text_columns=(0,))
    print_table('LP versus MILP',['LP bound','Integer optimum','Difference'],[(lp['bound'],integer,integer-lp['bound'])])
    if not (isclose(lp['bound'],4.5) and isclose(integer,6)):
        raise RuntimeError('relaxation example disagrees with hand calculation')


def solver_status():
    tasks=[Job(f'J{i}',p) for i,p in enumerate([3,7,2,8,4,6],1)]
    horizon=sum(j.processing_time for j in tasks)
    rows=[]
    for m,limit in [(horizon,1000),(horizon*100,1000),(horizon,1)]:
        r=analyze_total_completion(tasks,big_m=m,time_limit_ms=limit)
        rows.append((m,limit,r['status'],r['objective'] if r['objective'] is not None else 'N/A',
                     r['bound'] if r['bound'] is not None else 'N/A',f"{r['runtime']:.4f}"))
    print_table('Big-M and solver status',['M','Limit(ms)','Status','Incumbent','Bound','Time(s)'],rows,text_columns=(2,))
    print('A short limit may still prove optimality. Runtime and status can vary between runs.')


def enumeration():
    tasks=[Job('A',3,due_date=4),Job('B',2,due_date=7),Job('C',4,due_date=6),Job('D',1,due_date=3)]
    rows=[]
    for name,solver in [('total_completion_time',solve_single_machine_total_completion),('total_tardiness',solve_single_machine_total_tardiness)]:
        exact=min(evaluate(schedule_sequence([j.job_id for j in order],tasks))[name] for order in permutations(tasks))
        schedule=solver(tasks)
        validate_schedule(schedule,tasks)
        value=evaluate(schedule)[name]
        if not isclose(exact,value,abs_tol=1e-6): raise RuntimeError('enumeration and MILP disagree')
        rows.append((name,exact,value))
    exact=min(max(sum(j.processing_time for j,k in zip(tasks,assignment) if k==machine) for machine in range(2)) for assignment in product(range(2),repeat=len(tasks)))
    schedule=solve_parallel_machine_milp(tasks,2)
    validate_schedule(schedule,tasks)
    value=evaluate(schedule)['makespan']
    if not isclose(exact,value,abs_tol=1e-6): raise RuntimeError('parallel enumeration mismatch')
    rows.append(('parallel_makespan',exact,value))
    print_table('Enumeration cross-check',['Objective','Enumeration','MILP'],rows,text_columns=(0,))
