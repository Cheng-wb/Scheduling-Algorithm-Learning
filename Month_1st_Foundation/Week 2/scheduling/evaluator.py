"""统一评价入口：校验排程并组织指标，公式由 metrics 实现。"""

from . import metrics
from .models import Schedule


def evaluate(schedule: Schedule) -> dict[str, float | int]:
    schedule.validate()
    return {
        "makespan": metrics.makespan(schedule),
        "total_completion_time": metrics.total_completion_time(schedule),
        "total_tardiness": metrics.total_tardiness(schedule),
        "weighted_tardiness": metrics.weighted_tardiness(schedule),
        "num_tardy_jobs": metrics.num_tardy_jobs(schedule),
        "total_waiting_time": metrics.total_waiting_time(schedule),
        "total_flow_time": metrics.total_flow_time(schedule),
        "busy_time": metrics.busy_time(schedule),
        "idle_time": metrics.total_idle_time(schedule),
        "utilization": metrics.machine_utilization(schedule),
    }
