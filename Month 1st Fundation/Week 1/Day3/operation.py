from dataclasses import dataclass

@dataclass
class Operation:
    operation_id: str
    machine_id: str
    processing_time: int

    