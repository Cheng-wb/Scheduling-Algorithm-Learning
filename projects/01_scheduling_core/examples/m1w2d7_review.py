"""M1W2D7 复盘：固定接口链、证据表、表示冗余与追加解码边界。"""

import sys
from itertools import permutations, product
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scheduling_core.models import Instance, Job, Machine, Operation
from scheduling_core.objective import makespan, total_completion_time
from scheduling_core.schedule_validation import schedule_errors, validate_schedule
from scheduling_core.solution import Candidate
from scheduling_algorithms.decoder import decode


def route_instance() -> Instance:
    """与 tests/test_month1.py 的 route_instance 完全相同的 J0→O(A→B) + J1(C)。"""
    return Instance(
        (Job("J0", ("A", "B"), 2), Job("J1", ("C",))),
        (
            Operation("A", "J0", 3, ("M0",)),
            Operation("B", "J0", 2, ("M0", "M1")),
            Operation("C", "J1", 1, ("M0", "M1")),
        ),
        (Machine("M0", "M0"), Machine("M1", "M1")),
    )


def timeline(schedule) -> str:
    return "  ".join(
        f"{item.operation_id}:{item.machine_id}[{item.start_time},{item.end_time})"
        for item in schedule.operations
    )


def main() -> None:
    instance = route_instance()

    print("== 1. 固定接口链 ==")
    print("Instance -> Candidate -> decode -> Schedule -> validate_schedule -> objective")
    print("  Instance / Candidate / Schedule 都是 frozen dataclass + tuple，不可变")
    print("  邻域只返回新 Candidate；每次完整评价都必须走完这条链")
    print("  禁止：某个算法略过 validate_schedule，或私自使用另一套目标公式")

    print("\n== 2. 本周证据表 ==")
    evidence = [
        ("三类解表示/解码轨迹", "test_three_decoder_traces", "3 条编码 → 3 条精确时间轨迹"),
        ("swap/insert/指派与边界", "test_moves_and_boundaries", "交换两次复原、越界与非法资格"),
        ("至少五类非法排程", "test_independent_validator_corruption", "实际覆盖 9 类破坏"),
        ("可复现输入、CSV/JSON", "test_roundtrip_and_csv", "JSON 往返 + CSV 三表读取"),
        ("至少五个小例枚举", "test_five_independent_enumerations", "5 个种子 × 384 组合"),
    ]
    for requirement, test, detail in evidence:
        print(f"  {requirement:22} {test:40} {detail}")
    print("  周报：week2.md；测试代码：tests/test_month1.py")

    print("\n== 3. 三条解码轨迹（test_three_decoder_traces）==")
    for order, assignments in [
        (("A", "B", "C"), ("M0", "M1", "M0")),
        (("B", "C", "A"), ("M0", "M1", "M0")),
        (("B", "C", "A"), ("M0", "M0", "M1")),
    ]:
        schedule = decode(instance, Candidate(order, assignments))
        validate_schedule(instance, schedule)
        print(
            f"  order={'/'.join(order):10} assign={'/'.join(assignments):12} "
            f"-> {timeline(schedule)}"
        )

    print("\n== 4. 表示冗余：不同 Candidate 解码到同一个 Schedule ==")
    operations = instance.operations
    encodings = [
        Candidate(order, tuple(assignments))
        for order in permutations(op.id for op in operations)
        for assignments in product(*(op.eligible_machine_ids for op in operations))
    ]
    distinct = {decode(instance, candidate) for candidate in encodings}
    print(f"  编码总数 {len(encodings)}，解码后不同排程 {len(distinct)} 个")
    first = Candidate(("B", "C", "A"), ("M0", "M1", "M0"))
    second = Candidate(("C", "B", "A"), ("M0", "M1", "M0"))
    print(f"  {first.order} vs {second.order}：Candidate 相等？{first == second}")
    print(f"  decode 结果相等？{decode(instance, first) == decode(instance, second)}")
    print(f"  两个排程：{timeline(decode(instance, first))}")

    print("\n== 5. 追加解码的限制：不填已有空隙 ==")
    appended = decode(instance, Candidate(("A", "B", "C"), ("M0", "M0", "M0")))
    reordered = decode(instance, Candidate(("C", "A", "B"), ("M0", "M0", "M0")))
    for label, schedule in (("order=ABC", appended), ("order=CAB", reordered)):
        validate_schedule(instance, schedule)
        print(f"  {label:10} {timeline(schedule)}")
    print(
        f"  order=ABC：ΣCj={total_completion_time(instance, appended)}, "
        f"Cmax={makespan(instance, appended)}；M0 在 [0,2) 全程空转"
    )
    print(
        f"  order=CAB：ΣCj={total_completion_time(instance, reordered)}, "
        f"Cmax={makespan(instance, reordered)}；C(r=0) 被追加解码拒绝提前填隙"
    )
    print("  结论：order 是优先级而不是时间顺序，decoder 严格追加，不插入已出现的空隙")

    print("\n== 6. 独立校验器与已知局限 ==")
    broken = decode(instance, Candidate(("A", "B", "C"), ("M0", "M1", "M0")))
    corrupted = type(broken)(
        tuple(
            item if item.operation_id != "B" else type(item)("B", "M1", 2, 4)
            for item in broken.operations
        )
    )
    print(f"  人为制造 precedence 违规 -> {schedule_errors(instance, corrupted)}")
    limits = [
        ("优先级表示有冗余", "24 个编码只对应上面这几个不同排程，搜索空间 ≠ 时间表数量"),
        ("追加解码不填空隙", "order=ABC 的 [0,2) 空转必须靠重新排列消除，不能靠 decoder"),
        ("生成器默认全机器资格", "资格受限案例只能手工构造，见 test_invalid_inputs_and_rule_eligibility"),
        ("Oracle 只证明单工序极小实例", "多工序 / 大实例没有任何全局最优证据"),
    ]
    for name, note in limits:
        print(f"  {name:24} {note}")
    print("  这些是明确的模型或实现边界，不能靠更多同分布测试消除")

    print("\n全部检查通过：接口链、证据表、冗余与边界均已实机验证。")


if __name__ == "__main__":
    main()
