"""排程结果的最小表示（算法输出）。

注意：完整的 Schedule Validator（机器重叠、precedence 等）是 Week 2 的重点，
今天只定义排程结果的数据结构，不做可行性校验。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ScheduledOperation:
    """一道已排定工序：在指定机器上从 start_time 加工到 end_time。"""

    operation_id: str
    machine_id: str
    start_time: int
    end_time: int


@dataclass(frozen=True, slots=True)
class Schedule:
    """一个排程：由若干已排定工序组成。"""

    operations: tuple[ScheduledOperation, ...]
