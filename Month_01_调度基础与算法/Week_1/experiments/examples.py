"""规则实验的固定实例与公共表格；算法仍在 scheduling 中。"""

from scheduling.models import Job
from scheduling.evaluator import evaluate
from scheduling.validation import validate_schedule
from scheduling.heuristics import fcfs, spt, edd, wspt
from scheduling.heuristics.parallel_machine import greedy_list_scheduling, lpt_list_scheduling
from scheduling.bounds import parallel_machine_lower_bound
from experiments.tables import print_table


def jobs():
    return [Job('J1',3,due_date=10,weight=2), Job('J2',6,due_date=15,weight=1),
            Job('J3',2,due_date=6,weight=5), Job('J4',7,due_date=20,weight=3),
            Job('J5',4,due_date=9,weight=4)]


def show(title, tasks, schedules):
    rows=[]
    for name,schedule in schedules:
        validate_schedule(schedule,tasks)
        m=evaluate(schedule)
        rows.append((name,m['makespan'],m['total_completion_time'],m['total_tardiness'],m['weighted_completion_time']))
        print_table(name, ['Job','Machine','Start','End'],
                    [(a.job.job_id,a.machine_id,a.start_time,a.completion_time) for a in schedule.assignments],text_columns=(0,))
    print_table(title,['Rule','Cmax','Sum C','Sum T','Sum wC'],rows,text_columns=(0,))


def models():
    print('1 || sum(T_j): single machine, non-preemptive, release=0')
    print_table('Instance',['Job','p','r','d','w'],[(j.job_id,j.processing_time,j.release_time,j.due_date,j.weight) for j in jobs()],text_columns=(0,))


def dispatching():
    tasks=jobs()
    show('Single-machine rules',tasks,[(n,f(tasks)) for n,f in [('FCFS',fcfs),('SPT',spt),('EDD',edd),('WSPT',wspt)]])


def release_times():
    tasks=[Job('Long',10,release_time=0,due_date=20),Job('Short',1,release_time=1,due_date=5)]
    show('Fixed SPT versus released-job SPT',tasks,[('Fixed SPT',spt(tasks,dynamic=False)),('Dynamic SPT',spt(tasks,dynamic=True))])


def parallel_rules():
    tasks=[Job(f'J{i}',p) for i,p in enumerate([3,7,2,8,4,6],1)]
    show('Two machines',tasks,[('Greedy',greedy_list_scheduling(tasks,2)),('LPT',lpt_list_scheduling(tasks,2))])


def bounds():
    tasks=[Job(f'J{i}',p) for i,p in enumerate([8,7,6,5,4],1)]
    lb=parallel_machine_lower_bound(tasks,2)
    print('Load lower bound:',lb)
    show('LPT counterexample',tasks,[('Greedy',greedy_list_scheduling(tasks,2)),('LPT',lpt_list_scheduling(tasks,2))])
    print('Feasible partition [8,7] / [6,5,4] has Cmax=15 and attains the bound; LPT has Cmax=17.')


def baselines():
    dispatching()
    release_times()
    parallel_rules()
    bounds()
