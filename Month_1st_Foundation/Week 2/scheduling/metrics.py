"""纯指标函数；直接调用时要求 Schedule 可行，可先调用 validate()。"""

from .models import Schedule, ScheduledJob

def _lateness_value(item: ScheduledJob) -> float:
    value = item.lateness
    return 0 if value is None else value

def _tardiness_value(item: ScheduledJob) -> float:
    value = item.tardiness
    return 0 if value is None else value


def makespan(schedule: Schedule) -> float:
    return max((item.completion_time for item in schedule.assignments), default=0)


def total_completion_time(schedule: Schedule) -> float:
    return sum(item.completion_time for item in schedule.assignments)


def total_tardiness(schedule: Schedule) -> float:
    return sum(_tardiness_value(item) for item in schedule.assignments)


def weighted_tardiness(schedule: Schedule) -> float:
    return sum(item.job.weight * _tardiness_value(item) for item in schedule.assignments)


def num_tardy_jobs(schedule: Schedule) -> int:
    return sum(_tardiness_value(item) > 0 for item in schedule.assignments)


def total_flow_time(schedule: Schedule) -> float:
    return sum(item.flow_time for item in schedule.assignments)


def total_waiting_time(schedule: Schedule) -> float:
    return sum(item.waiting_time for item in schedule.assignments)


def busy_time(schedule: Schedule) -> float:
    return sum(item.job.processing_time for item in schedule.assignments)


def total_idle_time(schedule: Schedule) -> float:
    """全部机器在共同窗口 [0, Cmax] 内的空闲时长之和。"""
    return max(0, schedule.machine_count * makespan(schedule) - busy_time(schedule))


def machine_utilization(schedule: Schedule) -> float:
    """共同窗口 [0, Cmax] 内所有可用机器的平均利用率。"""
    capacity = schedule.machine_count * makespan(schedule)
    return busy_time(schedule) / capacity if capacity else 0
