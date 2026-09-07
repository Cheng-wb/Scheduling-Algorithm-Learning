from dataclasses import dataclass

@dataclass
class Machine:
    machine_id: str
    available_time: int = 0

    