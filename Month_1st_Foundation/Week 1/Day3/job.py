from dataclasses import dataclass
from operation import Operation

@dataclass
class Job:
    job_id: str
    operations: list[Operation]

    def total_processing_time(self):
        return sum(op.processing_time for op in self.operations)

    