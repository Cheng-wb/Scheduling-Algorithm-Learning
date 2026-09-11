"""使用局部随机数生成器，避免影响其他实验的随机状态。"""

from random import Random

from ..models import Job


def _check_range(name, bounds, minimum=None):
    if len(bounds) != 2 or any(type(value) is not int for value in bounds):
        raise ValueError(f"{name} must contain two integers")
    low, high = bounds
    if low > high or (minimum is not None and low < minimum):
        raise ValueError(f"invalid {name}: {bounds}")


def generate_jobs(
    n_jobs: int,
    processing_time_range: tuple[int, int],
    release_time_range: tuple[int, int] = (0, 0),
    due_date_range: tuple[int, int] | None = None,
    weight_range: tuple[int, int] = (1, 1),
    seed: int | None = None,
) -> list[Job]:
    """独立均匀抽取整数属性，区间包含两端；交期不保证可满足。"""
    if type(n_jobs) is not int or n_jobs < 0:
        raise ValueError("n_jobs must be a non-negative integer")
    _check_range("processing_time_range", processing_time_range, 1)
    _check_range("release_time_range", release_time_range, 0)
    _check_range("weight_range", weight_range, 0)
    if due_date_range is not None:
        _check_range("due_date_range", due_date_range)
    rng = Random(seed)
    return [
        Job(
            job_id=f"J{i}",
            processing_time=rng.randint(*processing_time_range),
            release_time=rng.randint(*release_time_range),
            due_date=None if due_date_range is None else rng.randint(*due_date_range),
            weight=rng.randint(*weight_range),
        )
        for i in range(1, n_jobs + 1)
    ]
