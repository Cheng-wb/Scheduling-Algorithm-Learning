"""M1W2D5 随机实例生成器：参数表、规模对照、局部 RNG 与 JSON/CSV 往返。

本脚本只做四件事：
1. 打印 generate_instance 的参数表、抽取区间与交期公式；
2. 用同一个 seed 生成 jobs=6 与 jobs=24，对照总加工时间的缩放；
3. 证明生成器使用局部 Random(seed)，调用它不扰动全局 random 状态；
4. 用 OS 临时目录演示 JSON 与 CSV 三表往返（只打印，不写入 artifacts/）。
所有输出由固定 seed 决定，可重复运行得到相同结果。
"""

import json
import random
import sys
import tempfile
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scheduling_algorithms.rules import parallel_makespan_lower_bound
from scheduling_core.models import Instance
from scheduling_io.parser import (
    load_csv_instance,
    load_json_instance,
    save_json_instance,
)
from scheduling_io.generator import generate_instance


def summarize(instance: Instance) -> dict[str, int | float]:
    times = [op.processing_time for op in instance.operations]
    return {
        "jobs": len(instance.jobs),
        "machines": len(instance.machines),
        "operations": len(instance.operations),
        "total_p": sum(times),
        "max_p": max(times),
        "mean_p": round(sum(times) / len(times), 2),
        "lower_bound": parallel_makespan_lower_bound(instance),
    }


def locality_check(seed: int) -> tuple[list[float], list[float]]:
    """先记录全局 RNG 的下三个数，再在中间调用生成器，对比是否被扰动。"""
    random.seed(12345)
    before = [random.random() for _ in range(3)]
    random.seed(12345)
    generate_instance(seed, jobs=8, machines=2)
    after = [random.random() for _ in range(3)]
    return before, after


def main() -> None:
    print("== 1. 生成器参数表 ==")
    for name, meaning, default in (
        ("seed", "实例种子，与算法种子分开", "必填"),
        ("jobs", "作业数", "12"),
        ("machines", "同质机器数", "3"),
        ("operations_per_job", "每个作业链长度", "1"),
        ("release_max", "释放时刻均匀整数范围上界", "10"),
        ("due_factor", "交期相对自身总工时的系数", "1.5"),
    ):
        print(f"  {name:20} {meaning:24} 默认 {default}")
    print("  加工时间 p ~ randint(1, 20)；权重 w ~ randint(1, 5)；release ~ randint(0, release_max)")
    print("  交期 due = release + int(sum(p) * due_factor)；所有工序默认可上全部机器")

    print("\n== 2. 同一 seed、不同规模 ==")
    size_seed = 7
    for jobs in (6, 12, 24):
        stats = summarize(generate_instance(size_seed, jobs=jobs, machines=3))
        print(
            f"  seed={size_seed} jobs={stats['jobs']:2d} machines={stats['machines']} "
            f"total_p={stats['total_p']:3d} max_p={stats['max_p']:2d} "
            f"mean_p={stats['mean_p']:5} lower_bound={stats['lower_bound']:3d}"
        )
    small = summarize(generate_instance(size_seed, jobs=6, machines=3))
    large = summarize(generate_instance(size_seed, jobs=24, machines=3))
    print(
        f"  总工时 {small['total_p']} -> {large['total_p']}，"
        f"约 {large['total_p'] / small['total_p']:.2f} 倍；"
        "目标更大只是问题更大，不代表算法更差"
    )

    print("\n== 3. 交期公式与全机器资格 ==")
    default_instance = generate_instance(0)
    for job in default_instance.jobs[:3]:
        own = sum(
            op.processing_time
            for op in default_instance.operations
            if op.job_id == job.id
        )
        print(
            f"  {job.id}: r={job.release_time} sum_p={own} "
            f"due={job.due_date} = {job.release_time} + int({own}*1.5)"
        )
    print(f"  实例 {default_instance.jobs[0].id} 的工序资格："
          f"{default_instance.operations[0].eligible_machine_ids}")

    print("\n== 4. 局部 RNG：调用生成器不扰动全局状态 ==")
    before, after = locality_check(99)
    print(f"  调用前 random.random() -> {before}")
    print(f"  调用后 random.random() -> {after}")
    print(f"  序列相同 -> {before == after}")
    assert before == after
    assert generate_instance(3, jobs=6) == generate_instance(3, jobs=6)
    print("  同 seed 两次生成的结果相等 -> True")

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        print("\n== 5. JSON 往返 ==")
        payload = root / "instance.json"
        sample = generate_instance(1)
        save_json_instance(sample, payload)
        restored = load_json_instance(payload)
        print(f"  写入 {payload.name}，读回后 Instance 相等 -> {restored == sample}")
        first_job = json.loads(payload.read_text(encoding="utf-8"))["jobs"][0]
        print(f"  JSON 中第一条 job -> {first_job}")
        assert restored == sample

        print("\n== 6. CSV 三表往返 ==")
        (root / "machines.csv").write_text(
            "id,name\nM0,Machine 0\nM1,Machine 1\n", encoding="utf-8"
        )
        (root / "jobs.csv").write_text(
            "id,operation_ids,release_time,due_date,weight\n"
            "J0,O0|O1,2,,2\n"
            "J1,O2,0,9,1\n",
            encoding="utf-8",
        )
        (root / "operations.csv").write_text(
            "id,job_id,processing_time,eligible_machine_ids\n"
            "O0,J0,3,M0|M1\n"
            "O1,J0,2,M0|M1\n"
            "O2,J1,4,M1\n",
            encoding="utf-8",
        )
        csv_instance = load_csv_instance(root)
        for job in csv_instance.jobs:
            print(
                f"  {job.id}: operation_ids={job.operation_ids} "
                f"r={job.release_time} due={job.due_date} w={job.weight}"
            )
        for op in csv_instance.operations:
            print(
                f"  {op.id}: job={op.job_id} p={op.processing_time} "
                f"eligible={op.eligible_machine_ids}"
            )
        print(f"  J0 的空交期被读成 None -> {csv_instance.jobs[0].due_date is None}")
        print(f"  总加工时间 = {sum(op.processing_time for op in csv_instance.operations)}")
        assert csv_instance.jobs[0].due_date is None
        assert csv_instance.operations[0].eligible_machine_ids == ("M0", "M1")

    print("\n全部断言通过。")


if __name__ == "__main__":
    main()
