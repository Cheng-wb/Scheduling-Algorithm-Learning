from random import Random

from models.job import Job


def example_jobs() -> list[Job]:
    return [Job("J1", 8, due_date=20), Job("J2", 3, due_date=10),
            Job("J3", 5, due_date=12), Job("J4", 2, due_date=18),
            Job("J5", 6, due_date=15)]


def homework_jobs(seed: int) -> list[Job]:
    rng = Random(seed)
    return [Job(f"J{i}", rng.randint(1, 20), due_date=rng.randint(10, 80))
            for i in range(1, 11)]


def neighborhood_jobs() -> list[Job]:
    """用于比较一层邻域的六任务实例，任务均在零时刻释放。"""
    return [Job("J1", 8, due_date=12), Job("J2", 3, due_date=7),
            Job("J3", 6, due_date=20), Job("J4", 2, due_date=15),
            Job("J5", 7, due_date=14), Job("J6", 4, due_date=10)]


def restart_jobs(seed: int = 42) -> list[Job]:
    """20 个任务；数据种子与搜索种子分开控制。"""
    return comparison_jobs(20, seed)


def comparison_jobs(n_jobs: int, seed: int = 42) -> list[Job]:
    """规模实验使用相同属性区间；相同种子的较小实例是较大实例的前缀。"""
    if type(n_jobs) is not int or n_jobs < 0:
        raise ValueError("n_jobs must be a non-negative integer")
    rng = Random(seed)
    return [Job(f"J{i}", rng.randint(1, 20), due_date=rng.randint(20, 150))
            for i in range(1, n_jobs + 1)]
