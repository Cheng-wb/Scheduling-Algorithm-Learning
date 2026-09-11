"""机器标识；单机实验使用 M0。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Machine:
    machine_id: int = 0

    def __post_init__(self):
        if type(self.machine_id) is not int or self.machine_id < 0:
            raise ValueError("machine_id must be a non-negative integer")
