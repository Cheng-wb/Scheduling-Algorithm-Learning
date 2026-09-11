"""运行四任务手工排程与六任务固定顺序排程。"""

from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scheduling.models import Job, Schedule, ScheduledJob
from scheduling.scheduler import schedule_sequence
from scheduling.evaluator import evaluate
from scheduling import metrics


def print_result(title: str, schedule: Schedule) -> None:
    result = evaluate(schedule)
    print(title)
    print(" -> ".join(item.job.job_id for item in schedule.assignments))
    print("Job   M   S   C   L   T  wT   W   F")
    for item in schedule.assignments:
        values = (
            item.job.job_id, item.machine_id, item.start_time, item.completion_time,
            item.lateness, item.tardiness,
            item.job.weight * item.tardiness,
            item.waiting_time, item.flow_time,
        )
        print(" ".join(f"{value:>3}" for value in values))
    for key, value in result.items():
        print(f"{key}: {value:.0%}" if key == "utilization" else f"{key}: {value}")
    print()


def main() -> None:
    # 四任务题目 - 直接用顺序构造
    jobs = [
        Job("J1", 4, due_date=6),
        Job("J2", 2, due_date=8),
        Job("J3", 5, due_date=10),
        Job("J4", 1, due_date=5),
    ]
    
    schedule_a = schedule_sequence(["J1", "J2", "J3", "J4"], jobs)
    schedule_a.algorithm = "manual_A"  # 覆盖算法标记
    
    schedule_b = schedule_sequence(["J4", "J1", "J2", "J3"], jobs)
    schedule_b.algorithm = "manual_B"
    
    print_result("Four jobs - A", schedule_a)
    print_result("Four jobs - B", schedule_b)
    
    # ... 六任务部分保持不变

    # 六任务题目通过构造器生成相同的数据结构，再交给同一评价器。
    jobs = [
        Job("J1", 3, release_time=0, due_date=7, weight=2),
        Job("J2", 6, release_time=0, due_date=15, weight=1),
        Job("J3", 2, release_time=2, due_date=8, weight=5),
        Job("J4", 5, release_time=0, due_date=10, weight=3),
        Job("J5", 1, release_time=4, due_date=9, weight=8),
        Job("J6", 4, release_time=1, due_date=14, weight=2),
    ]
    sequences = [
        ["J1", "J2", "J3", "J4", "J5", "J6"],
        ["J1", "J3", "J5", "J4", "J6", "J2"],
        ["J5", "J3", "J1", "J6", "J4", "J2"],
    ]
    for label, sequence in zip("ABC", sequences):
        print_result(f"Six jobs - {label}", schedule_sequence(sequence, jobs))


if __name__ == "__main__":
    main()
