"""M3 领域核心：模型、输入校验、独立排程验证器与目标评估。

与 M1/M2 的关系：M3 **不复用** M1 的 ``Instance``（M1 的工时不依赖机器，容不下
FJSP 的 ``p_ij``），但完整沿用它的四条纪律——输入不可变、输入与结果分离、
独立验证器、确定性平局决胜。
"""

from fjsp_core.models import (
    Calendar,
    FJSPInstance,
    Job,
    Machine,
    Maintenance,
    Operation,
    Qualification,
    Schedule,
    ScheduledOperation,
    Setup,
    Worker,
)
from fjsp_core.objective import (
    Weights,
    job_completion_times,
    makespan,
    max_lateness,
    objective_breakdown,
    total_setup_time,
    total_tardiness,
    weighted_sum,
    weighted_tardiness,
    worker_load,
)
from fjsp_core.schedule_validation import schedule_errors, validate_schedule
from fjsp_core.validation import FJSPInstanceError, validate_instance

__all__ = [
    "Calendar",
    "FJSPInstance",
    "Job",
    "Machine",
    "Maintenance",
    "Operation",
    "Qualification",
    "Schedule",
    "ScheduledOperation",
    "Setup",
    "Worker",
    "Weights",
    "job_completion_times",
    "makespan",
    "max_lateness",
    "objective_breakdown",
    "total_setup_time",
    "total_tardiness",
    "weighted_sum",
    "weighted_tardiness",
    "worker_load",
    "schedule_errors",
    "validate_schedule",
    "FJSPInstanceError",
    "validate_instance",
]
