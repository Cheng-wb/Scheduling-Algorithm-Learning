"""搜索实验的目标：最小化总延期。"""

from .evaluate import evaluate
from scheduling.schedule import Schedule


def objective(schedule: Schedule) -> float:
    return evaluate(schedule)["total_tardiness"]
