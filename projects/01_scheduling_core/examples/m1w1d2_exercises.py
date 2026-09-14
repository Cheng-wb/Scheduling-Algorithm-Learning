"""Day 2 实验作业（M1W1D2）：练习 1、练习 2 的实例构造。

对应学习笔记：Month_01_基础系统与框架设计/Week_1/Day2.md（第 29、30 节）。

运行方式（在 projects/01_scheduling_core 目录下）：
    python -m examples.m1w1d2_exercises
也可以直接运行本文件（包括 IDE 的“运行 Python 文件”）：
    python examples/m1w1d2_exercises.py
直接运行时自动定位项目目录，无需安装包或手动设置环境变量。
"""

import sys
from pathlib import Path

# 直接运行时，Python 默认只搜索脚本所在的 examples 目录。
# 根据文件位置自动加入项目目录，不依赖终端的当前工作目录。
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scheduling_core.models import Instance, Job, Machine, Operation


def exercise_1() -> Instance:
    """练习 1：单机调度实例。

    M1；J1: p=3 due=8、J2: p=1 due=4、J3: p=5 due=12，每个 Job 单工序
    （J1→O1、J2→O2、J3→O3）。要求：1 个 Machine、3 个 Operation、
    3 个 Job、完整 Instance。
    """
    # 1 台机器
    m1 = Machine(id="M1", name="Machine 1")

    # 3 个 Operation，每个 Job 单工序
    o1 = Operation(id="O1", job_id="J1", processing_time=3, eligible_machine_ids=("M1",))
    o2 = Operation(id="O2", job_id="J2", processing_time=1, eligible_machine_ids=("M1",))
    o3 = Operation(id="O3", job_id="J3", processing_time=5, eligible_machine_ids=("M1",))

    # 3 个 Job
    j1 = Job(id="J1", operation_ids=("O1",), due_date=8)
    j2 = Job(id="J2", operation_ids=("O2",), due_date=4)
    j3 = Job(id="J3", operation_ids=("O3",), due_date=12)

    return Instance(jobs=(j1, j2, j3), operations=(o1, o2, o3), machines=(m1,))


def exercise_2() -> Instance:
    """练习 2：两台机器。

    M1, M2
    J1: O1 p=3 {M1}; O2 p=2 {M2}
    J2: O3 p=4 {M1, M2}

    思考：更接近 JSP 还是 FJSP？
    答案：更接近 FJSP（柔性作业车间调度）。因为 O3 的
    ``eligible_machine_ids`` 包含两台机器 {M1, M2}，即同一道工序
    可以从多台可选机器中挑一台加工；而 JSP 中每道工序的加工机器是
    唯一确定的。只要存在"多机可选"的工序，就进入 FJSP 范畴。
    """
    # 两台机器
    m1 = Machine(id="M1", name="Machine 1")
    m2 = Machine(id="M2", name="Machine 2")

    # 3 个 Operation（注意 eligible_machine_ids 的区别：
    # 单元素也要写成 (...,) 才是 tuple）
    o1 = Operation(id="O1", job_id="J1", processing_time=3, eligible_machine_ids=("M1",))
    o2 = Operation(id="O2", job_id="J1", processing_time=2, eligible_machine_ids=("M2",))
    o3 = Operation(id="O3", job_id="J2", processing_time=4, eligible_machine_ids=("M1", "M2"))

    # 2 个 Job
    j1 = Job(id="J1", operation_ids=("O1", "O2"))
    j2 = Job(id="J2", operation_ids=("O3",))

    # 组装 Instance
    return Instance(jobs=(j1, j2), operations=(o1, o2, o3), machines=(m1, m2))


if __name__ == "__main__":
    inst1 = exercise_1()
    print("练习 1 所有 Job ID：", [job.id for job in inst1.jobs])

    inst2 = exercise_2()
    print("练习 2 所有 Job ID：", [job.id for job in inst2.jobs])
