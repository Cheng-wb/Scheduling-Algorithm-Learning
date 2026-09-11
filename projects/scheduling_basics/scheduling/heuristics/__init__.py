"""单机派工规则与并行机列表调度接口。"""

from .parallel_machine import greedy_list_scheduling, list_schedule, lpt_list_scheduling

from .rules import edd_key, fcfs_key, lpt_key, spt_key, wspt_key
from .single_machine import (
    edd,
    fcfs,
    lpt,
    schedule_by_rule,
    schedule_dynamic_rule,
    schedule_static_rule,
    spt,
    wspt,
)

__all__ = [
    "greedy_list_scheduling",
    "list_schedule",
    "lpt_list_scheduling",
    "edd",
    "edd_key",
    "fcfs",
    "fcfs_key",
    "lpt",
    "lpt_key",
    "schedule_by_rule",
    "schedule_dynamic_rule",
    "schedule_static_rule",
    "spt",
    "spt_key",
    "wspt",
    "wspt_key",
]
