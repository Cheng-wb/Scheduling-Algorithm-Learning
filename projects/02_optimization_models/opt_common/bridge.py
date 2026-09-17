"""复用 M1 的调度领域模型：把 ``01_scheduling_core`` 加入 ``sys.path`` 后重导出。

M2 不重新定义 Instance / Schedule / 独立验证器 / Objective —— 这些在 M1 已经
建立并有测试，M2 的精确模型必须与它们共用同一套语义，否则「MILP 的解」和
「启发式的解」就不是在同一个问题上比较。

唯一的新增职责是路径装配：本模块在导入时把兄弟项目 ``01_scheduling_core``
放到 ``sys.path`` 最前面（幂等），之后 M2 的任何模块都可以直接
``from opt_common.bridge import Instance, validate_schedule, ...``。
"""

from __future__ import annotations

import sys
from pathlib import Path

M1_ROOT = Path(__file__).resolve().parents[2] / "01_scheduling_core"
M2_ROOT = Path(__file__).resolve().parents[1]

for _root in (M1_ROOT, M2_ROOT):
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

# --- M1 领域模型与结果结构 ------------------------------------------------
from scheduling_core.models import Instance, Job, Machine, Operation  # noqa: E402
from scheduling_core.schedule import Schedule, ScheduledOperation  # noqa: E402
from scheduling_core.solution import Candidate, validate_candidate  # noqa: E402
from scheduling_core.validation import (  # noqa: E402
    InstanceValidationError,
    validate_instance,
)
from scheduling_core.schedule_validation import (  # noqa: E402
    schedule_errors,
    validate_schedule,
)

# --- M1 目标评估器 --------------------------------------------------------
from scheduling_core.objective import (  # noqa: E402
    job_completion_times,
    makespan,
    max_lateness,
    total_completion_time,
    total_flow_time,
    total_tardiness,
    weighted_completion_time,
)

# --- M1 输入生成与读写 ----------------------------------------------------
from scheduling_io.generator import generate_instance  # noqa: E402
from scheduling_io.parser import (  # noqa: E402
    load_csv_instance,
    load_json_instance,
    save_json_instance,
)

# --- M1 基线规则（M2 用作 warm start 与对照） ------------------------------
from scheduling_algorithms.rules import (  # noqa: E402
    edd,
    lpt,
    parallel_lpt,
    spt,
    wspt,
)

M2_OBJECTIVES = {
    "makespan": makespan,
    "total_tardiness": total_tardiness,
    "weighted_completion_time": weighted_completion_time,
    "total_completion_time": total_completion_time,
    "total_flow_time": total_flow_time,
    "max_lateness": max_lateness,
}

__all__ = [
    "M1_ROOT",
    "M2_ROOT",
    "Instance",
    "Job",
    "Machine",
    "Operation",
    "Schedule",
    "ScheduledOperation",
    "Candidate",
    "validate_candidate",
    "InstanceValidationError",
    "validate_instance",
    "schedule_errors",
    "validate_schedule",
    "job_completion_times",
    "makespan",
    "max_lateness",
    "total_completion_time",
    "total_flow_time",
    "total_tardiness",
    "weighted_completion_time",
    "M2_OBJECTIVES",
    "generate_instance",
    "load_csv_instance",
    "load_json_instance",
    "save_json_instance",
    "edd",
    "lpt",
    "parallel_lpt",
    "spt",
    "wspt",
]
