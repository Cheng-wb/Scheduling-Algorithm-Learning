"""M3 Week 1 测试：Johnson / NEH / 析取图 / CP-SAT JSP / 标准格式 / 甘特导出。

**期望值全部来自手算或手写样例**，不由被测代码生成：

* ``tiny2x4_flow_shop`` 的 Johnson 排列与 12 的 makespan 是手算的（见下方时间线）；
* ``tiny3x3_flow_shop`` 的 NEH 排列与 10 的 makespan、瓶颈机对 Johnson 的 11 都是手算的；
* ``tiny3x3.jsp`` 的最优值 7 = ``max(机器负载)``，且手算给出了达到 7 的排程；
* ``tiny2x2.jsp`` / ``tiny3x3.jsp`` / ``tiny4x2.jsp`` 是手写的标准格式文件。

对拍纪律：每个方法返回的排程都要过 :func:`fjsp_core.validate_schedule` 这一条
**独立**检查路径；启发式的 ``best_bound`` 必须是 ``None``（不能拿目标值冒充下界）。
"""

from __future__ import annotations

import csv
import sys
from dataclasses import replace
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from fjsp_core import (
    Calendar,
    FJSPInstance,
    Job,
    Machine,
    Operation,
    Schedule,
    ScheduledOperation,
    Worker,
    makespan,
    schedule_errors,
    validate_schedule,
)
from fjsp_io.generator import generate_instance
from fjsp_io.standard import (
    StandardFormatError,
    format_standard_jsp,
    load_standard_jsp,
    parse_standard_jsp,
)
from fjsp_shop import flowshop
from fjsp_shop.gantt import (
    GANTT_FIELDS,
    GANTT_SORT_KEYS,
    machine_load_summary,
    render_ascii_gantt,
    to_gantt_rows,
    write_gantt_csv,
)
from fjsp_shop.graph import (
    analyze,
    build_graph,
    check_critical_path,
    critical_blocks,
    critical_path,
    graph_makespan,
    left_shift_schedule,
    path_length,
)
from fjsp_shop.jsp import PRIORITY_RULES, jsp_cpsat, jsp_priority

DATA = Path(__file__).resolve().parent / "data"


# ---------------------------------------------------------------------------
# 手算实例
# ---------------------------------------------------------------------------


def _flow_shop(rows: dict[str, tuple[int, ...]], machines: int) -> FJSPInstance:
    """按「订单 → 各机器工时」构造一条共用机器序列 M0..M{m-1} 的 flow shop。"""
    jobs: list[Job] = []
    operations: list[Operation] = []
    for job_id, times in rows.items():
        operation_ids = tuple(f"{job_id}_O{index}" for index in range(len(times)))
        jobs.append(Job(job_id, operation_ids))
        for index, minutes in enumerate(times):
            operations.append(
                Operation(
                    id=operation_ids[index],
                    job_id=job_id,
                    position=index,
                    machine_times=((f"M{index}", minutes),),
                )
            )
    return FJSPInstance(
        jobs=tuple(jobs),
        operations=tuple(operations),
        machines=tuple(Machine(f"M{i}", f"M{i}") for i in range(machines)),
    )


def tiny2x4_flow_shop() -> FJSPInstance:
    """4 订单 × 2 机器。Johnson 排列 (J2,J0,J3,J1)，手算 makespan = 12。

    ```text
    M0: J2[0,1) J0[1,3) J3[3,6) J1[6,10)
    M1: J2[1,6) J0[6,9) J3[9,11) J1[11,12)   ->  Cmax = 12
    ```
    """
    return _flow_shop(
        {"J0": (2, 3), "J1": (4, 1), "J2": (1, 5), "J3": (3, 2)}, machines=2
    )


def tiny3x3_flow_shop() -> FJSPInstance:
    """3 订单 × 3 机器。NEH 排列 (J2,J1,J0)，手算 makespan = 10。

    ```text
    M0: J2[0,1) J1[1,3) J0[3,6)
    M1: J2[1,4) J1[4,5) J0[6,8)
    M2: J2[4,5) J1[5,8) J0[8,10)             ->  Cmax = 10
    ```

    瓶颈机对是三台机器的负载最大者，本实例三台负载都是 6，平局按路线位置取
    (M0, M1)；在该机对上应用 Johnson 得到排列 (J2,J0,J1)，解码后 makespan = 11。
    """
    return _flow_shop({"J0": (3, 2, 2), "J1": (2, 1, 3), "J2": (1, 3, 1)}, machines=3)


def tiny3x3_job_shop() -> FJSPInstance:
    """手写标准格式文件 ``tests/data/tiny3x3.jsp`` 对应的实例。

    各订单路线不同（真正的 job shop）。最优值 = 7：机器负载上界为
    ``max(M0=5, M1=7, M2=6) = 7``，而下面的手算排程恰好达到 7。

    ```text
    M0: J0_O0[0,2) J2_O1[3,4) J1_O2[5,7)
    M1: J1_O0[0,2) J0_O1[2,5) J2_O2[5,7)
    M2: J2_O0[0,3) J1_O1[3,5) J0_O2[5,6)      ->  Cmax = 7
    ```
    """
    return load_standard_jsp(DATA / "tiny3x3.jsp")


def hand_made_tiny3x3_schedule() -> Schedule:
    """上面那段手算时间线，逐条写死。"""
    return Schedule(
        (
            ScheduledOperation("J0_O0", "M0", 0, 2),
            ScheduledOperation("J0_O1", "M1", 2, 5),
            ScheduledOperation("J0_O2", "M2", 5, 6),
            ScheduledOperation("J1_O0", "M1", 0, 2),
            ScheduledOperation("J1_O1", "M2", 3, 5),
            ScheduledOperation("J1_O2", "M0", 5, 7),
            ScheduledOperation("J2_O0", "M2", 0, 3),
            ScheduledOperation("J2_O1", "M0", 3, 4),
            ScheduledOperation("J2_O2", "M1", 5, 7),
        )
    )


# ---------------------------------------------------------------------------
# Johnson 规则
# ---------------------------------------------------------------------------


def test_johnson_two_machine_hand_solved() -> None:
    """手算：集合 A = {p1<p2} 按 p1 升序、集合 B = {p1>=p2} 按 p2 降序。"""
    instance = tiny2x4_flow_shop()
    result = flowshop.flow_johnson(instance, {"objective": "makespan"})
    assert result.status == "OPTIMAL", "两台机器、零释放时间时 Johnson 是精确算法"
    assert result.detail["applicability"] == "johnson_f2"
    assert result.detail["applies_directly"] is True
    assert result.detail["job_sequence"] == ["J2", "J0", "J3", "J1"]
    assert result.objective == 12.0
    validate_schedule(instance, result.schedule)

    by_id = result.schedule.by_operation()
    assert (by_id["J2_O0"].start_time, by_id["J2_O0"].end_time) == (0, 1)
    assert (by_id["J0_O0"].start_time, by_id["J0_O0"].end_time) == (1, 3)
    assert (by_id["J3_O0"].start_time, by_id["J3_O0"].end_time) == (3, 6)
    assert (by_id["J1_O0"].start_time, by_id["J1_O0"].end_time) == (6, 10)
    assert (by_id["J2_O1"].start_time, by_id["J2_O1"].end_time) == (1, 6)
    assert (by_id["J0_O1"].start_time, by_id["J0_O1"].end_time) == (6, 9)
    assert (by_id["J3_O1"].start_time, by_id["J3_O1"].end_time) == (9, 11)
    assert (by_id["J1_O1"].start_time, by_id["J1_O1"].end_time) == (11, 12)
    assert makespan(instance, result.schedule) == 12


def test_johnson_rejects_non_flow_shop() -> None:
    """各订单路线不同是 job shop，Johnson 不适用 —— 必须 FAILED，不能硬算。"""
    instance = tiny3x3_job_shop()
    result = flowshop.flow_johnson(instance, {})
    assert result.status == "FAILED"
    assert "flow shop" in result.detail["failure_reason"]
    assert result.best_bound is None and result.schedule is None


def test_johnson_rejects_flexible_instance() -> None:
    """有柔性的实例（一道工序多台合格机器）不是经典 flow shop。"""
    instance = generate_instance(7, jobs=4, machines=3, operations_per_job=3, flexibility=2)
    result = flowshop.flow_johnson(instance, {})
    assert result.status == "FAILED"
    assert "合格机器" in result.detail["failure_reason"]


def test_johnson_uses_bottleneck_pair_above_two_machines() -> None:
    """三台机器时 Johnson 不再精确：本实现退化为「瓶颈机对上的 Johnson」。"""
    instance = tiny3x3_flow_shop()
    result = flowshop.flow_johnson(instance, {"objective": "makespan"})
    assert result.status == "FEASIBLE", ">=3 台机器时不能声称最优"
    assert result.detail["applicability"] == "johnson_on_bottleneck_pair"
    assert result.detail["applies_directly"] is False
    assert result.detail["bottleneck_pair"] == ["M0", "M1"]
    assert result.detail["job_sequence"] == ["J2", "J0", "J1"]
    assert result.objective == 11.0, "手算：瓶颈机对 Johnson 排列 (J2,J0,J1) → Cmax = 11"
    validate_schedule(instance, result.schedule)


# ---------------------------------------------------------------------------
# NEH
# ---------------------------------------------------------------------------


def test_neh_three_machine_hand_checked() -> None:
    """手算 NEH：插入顺序 J0(7) → J1(6) → J2(5)，每步都插到最靠前的并列最优位置。"""
    instance = tiny3x3_flow_shop()
    result = flowshop.flow_neh(instance, {"objective": "makespan"})
    assert result.status == "FEASIBLE", "NEH 是启发式，不能声称最优"
    assert result.detail["job_sequence"] == ["J2", "J1", "J0"]
    assert result.detail["insertion_order"] == ["J0", "J1", "J2"]
    assert result.detail["insertion_positions"] == [0, 0, 0]
    assert result.detail["insertion_makespans"] == [7, 9, 10]
    assert result.objective == 10.0
    validate_schedule(instance, result.schedule)

    by_id = result.schedule.by_operation()
    assert (by_id["J2_O0"].start_time, by_id["J2_O0"].end_time) == (0, 1)
    assert (by_id["J1_O0"].start_time, by_id["J1_O0"].end_time) == (1, 3)
    assert (by_id["J0_O0"].start_time, by_id["J0_O0"].end_time) == (3, 6)
    assert (by_id["J0_O2"].start_time, by_id["J0_O2"].end_time) == (8, 10)


def test_neh_tie_keeps_the_earliest_position() -> None:
    """第三步三个候选位置里前两个都是 10：NEH 必须保留最靠前的那个。"""
    instance = tiny3x3_flow_shop()
    trace = flowshop.neh_insertion_trace(instance)
    assert trace[-1]["candidates"] == [10, 10, 11]
    assert trace[-1]["position"] == 0


def test_neh_beats_bottleneck_johnson_here() -> None:
    """本实例上 NEH(10) 严格优于瓶颈机对 Johnson(11) —— 一个实例上的观察。"""
    instance = tiny3x3_flow_shop()
    neh = flowshop.flow_neh(instance, {})
    johnson = flowshop.flow_johnson(instance, {})
    assert neh.objective == 10.0 < johnson.objective == 11.0


# ---------------------------------------------------------------------------
# 析取图：关键路径与关键块
# ---------------------------------------------------------------------------


def test_critical_path_length_equals_makespan_on_johnson_schedule() -> None:
    """手算的 Johnson 排程上，关键路径 = (J2_O0, J2_O1, J0_O1, J3_O1, J1_O1)，长度 12。"""
    instance = tiny2x4_flow_shop()
    schedule = flowshop.flow_johnson(instance, {}).schedule
    assert check_critical_path(instance, schedule) == 12
    assert graph_makespan(instance, schedule) == 12

    path = critical_path(instance, schedule)
    assert path == ("J2_O0", "J2_O1", "J0_O1", "J3_O1", "J1_O1")
    assert path_length(instance, schedule, path) == 12


def test_critical_path_length_equals_makespan_on_hand_schedule() -> None:
    """手写排程（不经过任何算法）也要满足最长路径 = makespan = 7。"""
    instance = tiny3x3_job_shop()
    schedule = hand_made_tiny3x3_schedule()
    validate_schedule(instance, schedule)
    assert makespan(instance, schedule) == 7
    assert check_critical_path(instance, schedule) == 7
    analysis = analyze(instance, schedule)
    assert analysis.is_left_shifted
    assert analysis.path_length == analysis.graph_length == analysis.makespan == 7
    # 关键路径上的每一对相邻工序都必须真的有弧相连
    graph = build_graph(instance, schedule)
    for tail, head in zip(analysis.path, analysis.path[1:]):
        assert graph.arc_between(tail, head) is not None


def test_critical_blocks_are_contiguous_on_one_machine() -> None:
    """关键块的定义：关键路径上同机器且在该机器上相邻的极大段。"""
    instance = tiny2x4_flow_shop()
    schedule = flowshop.flow_johnson(instance, {}).schedule
    blocks = critical_blocks(instance, schedule)
    assert blocks == (("J2_O0",), ("J2_O1", "J0_O1", "J3_O1", "J1_O1"))

    machine_of = {item.operation_id: item.machine_id for item in schedule.operations}
    item_of = schedule.by_operation()
    sequence_on: dict[str, list[str]] = {}
    for item in schedule.operations:
        sequence_on.setdefault(item.machine_id, []).append(item.operation_id)
    for machine_id, sequence in sequence_on.items():
        sequence.sort(key=lambda oid: (item_of[oid].start_time, oid))

    for block in blocks:
        machines = {machine_of[oid] for oid in block}
        assert len(machines) == 1, "一个关键块只能落在一台机器上"
        machine_id = machines.pop()
        order = sequence_on[machine_id]
        positions = [order.index(oid) for oid in block]
        assert positions == list(range(positions[0], positions[0] + len(block))), (
            "关键块内的工序必须在机器顺序里连续"
        )
        for earlier, later in zip(block, block[1:]):
            assert item_of[earlier].end_time == item_of[later].start_time, (
                "关键块内的工序之间不能有空隙（左移排程上这一点必须成立）"
            )


def test_critical_blocks_cover_the_critical_path() -> None:
    """关键块是路径的一个划分：拼起来正好是整条关键路径。"""
    instance = tiny3x3_job_shop()
    schedule = hand_made_tiny3x3_schedule()
    blocks = critical_blocks(instance, schedule)
    joined = tuple(operation_id for block in blocks for operation_id in block)
    assert joined == critical_path(instance, schedule)


def test_graph_detects_an_infeasible_schedule() -> None:
    """机器顺序与工艺路线互相矛盾时图有环 —— 有环就不存在「最长路径」。

    这里把 ``J1_O2`` 放到机器 ``M0`` 的**最前面**，于是机器弧 ``J1_O2 -> J0_O0`` 与
    路线弧 ``J0_O0 -> J0_O1 -> J0_O2``、机器弧 ``J0_O2 -> J1_O1``、路线弧
    ``J1_O1 -> J1_O2`` 首尾相接成环。这份「排程」同时违反先后顺序，独立验证器也会拒绝它。
    """
    instance = tiny3x3_job_shop()
    bad = Schedule(
        (
            ScheduledOperation("J0_O0", "M0", 2, 4),
            ScheduledOperation("J0_O1", "M1", 2, 5),
            ScheduledOperation("J0_O2", "M2", 3, 4),
            ScheduledOperation("J1_O0", "M1", 0, 2),
            ScheduledOperation("J1_O1", "M2", 4, 6),
            ScheduledOperation("J1_O2", "M0", 0, 2),
            ScheduledOperation("J2_O0", "M2", 0, 3),
            ScheduledOperation("J2_O1", "M0", 4, 5),
            ScheduledOperation("J2_O2", "M1", 5, 7),
        )
    )
    graph = build_graph(instance, bad)
    assert graph.has_cycle()
    assert graph.topological_order() is None
    with pytest.raises(ValueError, match="环"):
        graph.longest_path()
    assert schedule_errors(instance, bad), "同一份排程也必须被独立验证器拒绝"


def test_graph_reports_slack_instead_of_pretending() -> None:
    """人为把一道工序推迟后，最长路径严格小于 makespan —— 必须被点出来。"""
    instance = tiny3x3_job_shop()
    base = hand_made_tiny3x3_schedule()
    delayed = replace(
        base,
        operations=tuple(
            replace(item, start_time=item.start_time + 5, end_time=item.end_time + 5)
            if item.operation_id == "J0_O2"
            else item
            for item in base.operations
        ),
    )
    analysis = analyze(instance, delayed)
    assert analysis.slack == ("J0_O2",)
    assert not analysis.matches_makespan
    with pytest.raises(ValueError, match="不是左移"):
        check_critical_path(instance, delayed)


def test_left_shift_restores_the_theorem() -> None:
    """左移后 makespan 不变，排程仍然可行，且最长路径重新等于 makespan。"""
    instance = tiny3x3_job_shop()
    base = hand_made_tiny3x3_schedule()
    delayed = replace(
        base,
        operations=tuple(
            replace(item, start_time=item.start_time + 5, end_time=item.end_time + 5)
            if item.operation_id == "J0_O2"
            else item
            for item in base.operations
        ),
    )
    shifted = left_shift_schedule(instance, delayed)
    validate_schedule(instance, shifted)
    assert makespan(instance, shifted) <= makespan(instance, delayed)
    assert check_critical_path(instance, shifted) == makespan(instance, shifted)


def test_left_shift_declines_instances_it_cannot_handle() -> None:
    """带日历 / 维护 / 资源 / 锁定开工时刻时左移不适用，必须报错而不是硬做。"""
    base = tiny3x3_job_shop()
    schedule = hand_made_tiny3x3_schedule()
    with_calendar = replace(
        base, calendars=(Calendar("CAL", ((0, 100),)),)
    )
    with pytest.raises(ValueError, match="日历"):
        left_shift_schedule(with_calendar, schedule)
    with_worker = replace(base, workers=(Worker("W0", "W0", (), 1),))
    with pytest.raises(ValueError, match="次生资源"):
        left_shift_schedule(with_worker, schedule)


# ---------------------------------------------------------------------------
# CP-SAT
# ---------------------------------------------------------------------------


def test_jsp_cpsat_matches_hand_computed_optimum() -> None:
    """tiny3x3 的最优值是 7（= 最大机器负载，且有手算排程达到它）。"""
    instance = tiny3x3_job_shop()
    result = jsp_cpsat(instance, {"objective": "makespan", "time_limit": 10.0, "seed": 0})
    assert result.status == "OPTIMAL"
    assert result.objective == 7.0
    assert result.best_bound == 7.0
    assert result.gap == 0.0
    validate_schedule(instance, result.schedule)
    assert makespan(instance, result.schedule) == 7


def test_jsp_cpsat_is_deterministic_on_a_tiny_instance() -> None:
    """单线程 + 固定种子：同一实例两次求解给出同一个目标值与同一份排程。"""
    instance = tiny3x3_job_shop()
    spec = {"objective": "makespan", "time_limit": 10.0, "seed": 0}
    first = jsp_cpsat(instance, spec)
    second = jsp_cpsat(instance, spec)
    assert first.objective == second.objective
    assert sorted(
        (item.operation_id, item.machine_id, item.start_time) for item in first.schedule.operations
    ) == sorted(
        (item.operation_id, item.machine_id, item.start_time)
        for item in second.schedule.operations
    )


def test_jsp_cpsat_left_shifts_its_solution() -> None:
    """返回的解做过左移归一化，因此可以直接套 Day 3 的定理复核。"""
    instance = tiny3x3_job_shop()
    result = jsp_cpsat(instance, {"objective": "makespan", "time_limit": 10.0, "seed": 0})
    assert result.detail["left_shifted"] is True
    assert check_critical_path(instance, result.schedule) == 7


def test_jsp_cpsat_reports_a_bound_and_heuristics_do_not() -> None:
    """最关键的证据纪律：启发式的 best_bound 必须是 None，精确方法才有界。"""
    instance = tiny3x3_job_shop()
    for method in (flowshop.flow_johnson, flowshop.flow_neh, jsp_priority):
        result = method(instance, {"objective": "makespan"})
        if result.status == "FAILED":
            continue
        assert result.best_bound is None, f"{method.__name__} 不该提供下界"
        assert result.gap is None
    exact = jsp_cpsat(instance, {"objective": "makespan", "time_limit": 10.0, "seed": 0})
    assert exact.best_bound == exact.objective


def test_jsp_methods_decline_instances_with_unsupported_constraints() -> None:
    """日历 / 维护 / 换型 / 资源不在 Week 1 的模型里 —— 明确 FAILED，不猜。"""
    base = tiny3x3_job_shop()
    with_calendar = replace(base, calendars=(Calendar("CAL", ((0, 50),)),))
    for method in (jsp_priority, jsp_cpsat):
        result = method(with_calendar, {"objective": "makespan", "time_limit": 5.0})
        assert result.status == "FAILED"
        assert "不表达的约束" in result.detail["failure_reason"]


def test_jsp_cpsat_rejects_unknown_objective() -> None:
    instance = tiny3x3_job_shop()
    result = jsp_cpsat(instance, {"objective": "nonexistent"})
    assert result.status == "FAILED"
    assert "unknown objective" in result.detail["failure_reason"]


# ---------------------------------------------------------------------------
# 优先级派工
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rule", PRIORITY_RULES)
def test_priority_rules_are_valid_and_deterministic(rule: str) -> None:
    instance = tiny3x3_job_shop()
    spec = {"objective": "makespan", "priority": rule}
    first = jsp_priority(instance, spec)
    second = jsp_priority(instance, spec)
    assert first.status == "FEASIBLE"
    validate_schedule(instance, first.schedule)
    assert [
        (item.operation_id, item.machine_id, item.start_time) for item in first.schedule.operations
    ] == [
        (item.operation_id, item.machine_id, item.start_time) for item in second.schedule.operations
    ]


def test_priority_schedule_is_non_delay_and_left_shifted() -> None:
    """非延迟列表调度的直接后果：没有机器会在「有活可干」时空转。"""
    instance = tiny3x3_job_shop()
    result = jsp_priority(instance, {"objective": "makespan", "priority": "mwr"})
    assert result.detail["non_delay"] is True
    analysis = analyze(instance, result.schedule)
    assert analysis.is_left_shifted
    assert check_critical_path(instance, result.schedule) == result.objective


def test_priority_rejects_unknown_rule() -> None:
    instance = tiny3x3_job_shop()
    result = jsp_priority(instance, {"objective": "makespan", "priority": "etd"})
    assert result.status == "FAILED"
    assert "unknown priority rule" in result.detail["failure_reason"]


# ---------------------------------------------------------------------------
# 标准格式解析
# ---------------------------------------------------------------------------


def test_standard_parser_reads_the_hand_written_files() -> None:
    two = load_standard_jsp(DATA / "tiny2x2.jsp")
    assert [job.id for job in two.jobs] == ["J0", "J1"]
    assert [machine.id for machine in two.machines] == ["M0", "M1"]
    assert two.operation("J0_O0").machine_times == (("M0", 3),)
    assert two.operation("J1_O0").machine_times == (("M0", 4),)
    assert two.operation("J1_O1").machine_times == (("M1", 6),)
    assert two.meta["machine_id_base"] == 0
    assert two.meta["format"] == "or-library-jsp"

    three = load_standard_jsp(DATA / "tiny3x3.jsp")
    # 机器号是 0 基：第 2 行的第一对是「1 2」，即 M1 上 2 个时间单位
    assert three.operation("J1_O0").machine_times == (("M1", 2),)
    assert [three.operation(oid).machine_times[0][0] for oid in three.job("J2").operation_ids] == [
        "M2",
        "M0",
        "M1",
    ]

    four = load_standard_jsp(DATA / "tiny4x2.jsp")
    assert [four.operation(f"J{index}_O0").time_on("M0") for index in range(4)] == [2, 4, 1, 3]


@pytest.mark.parametrize("filename", ["tiny2x2.jsp", "tiny3x3.jsp", "tiny4x2.jsp"])
def test_standard_parser_round_trips(filename: str) -> None:
    """往返：文件 → 实例 → 文本 → 实例，两个实例必须完全相等。

    ``name=`` 要跟着传，否则 ``meta["source"]`` 从文件名变成默认值，实例就不相等了 ——
    这正是「证据要能回溯到磁盘上的哪一份文件」这条约定在数据里的体现。
    """
    first = load_standard_jsp(DATA / filename)
    text = format_standard_jsp(first)
    again = parse_standard_jsp(text, name=filename)
    assert again == first
    assert again.meta["source"] == filename
    assert format_standard_jsp(again) == text


def test_standard_parser_rejects_malformed_input() -> None:
    with pytest.raises(StandardFormatError, match="空文件"):
        parse_standard_jsp("\n\n# 只有注释\n")
    with pytest.raises(StandardFormatError, match="订单数 机器数"):
        parse_standard_jsp("2\n0 1 1 2\n")
    with pytest.raises(StandardFormatError, match="只有"):
        parse_standard_jsp("2 2\n0 1 1 2\n")
    with pytest.raises(StandardFormatError, match="应为 4 个"):
        parse_standard_jsp("2 2\n0 1 1 2\n0 1 1\n")
    with pytest.raises(StandardFormatError, match="越界"):
        parse_standard_jsp("1 2\n0 1 2 2\n")
    with pytest.raises(StandardFormatError, match="不是正数"):
        parse_standard_jsp("1 2\n0 1 1 0\n")


def test_standard_parser_agrees_with_the_generator_shape() -> None:
    """解析出来的实例与生成器造的 job shop 同形：每道工序只在一台机器上。"""
    instance = tiny3x3_job_shop()
    assert all(len(op.machine_times) == 1 for op in instance.operations)
    assert all(len(job.operation_ids) == 3 for job in instance.jobs)
    assert instance.total_operation_count == 9


# ---------------------------------------------------------------------------
# 甘特导出
# ---------------------------------------------------------------------------


def test_gantt_rows_have_six_fields_and_are_sorted() -> None:
    instance = tiny3x3_job_shop()
    schedule = hand_made_tiny3x3_schedule()
    rows = to_gantt_rows(instance, schedule)
    assert len(rows) == len(schedule.operations)
    for row in rows:
        assert tuple(row) == GANTT_FIELDS
        assert row["duration"] == row["end_time"] - row["start_time"]
        assert row["job_id"] == instance.operation(row["operation_id"]).job_id
    keys = [tuple(row[key] for key in GANTT_SORT_KEYS) for row in rows]
    assert keys == sorted(keys)
    assert rows[0]["machine_id"] == "M0"
    assert rows[0]["operation_id"] == "J0_O0"


def test_gantt_csv_round_trip(tmp_path: Path) -> None:
    instance = tiny3x3_job_shop()
    rows = to_gantt_rows(instance, hand_made_tiny3x3_schedule())
    path = tmp_path / "gantt.csv"
    write_gantt_csv(rows, path)
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == list(GANTT_FIELDS)
        read_back = list(reader)
    assert len(read_back) == len(rows)
    assert [row["operation_id"] for row in read_back] == [row["operation_id"] for row in rows]
    assert int(read_back[0]["duration"]) == rows[0]["duration"]


def test_ascii_gantt_stays_inside_gbk() -> None:
    """脚本 stdout 不设编码护栏，所以打印内容必须能编进 GBK。"""
    instance = tiny3x3_job_shop()
    lines = render_ascii_gantt(instance, hand_made_tiny3x3_schedule(), width=20)
    for line in lines:
        line.encode("gbk")


def test_machine_load_summary_is_consistent() -> None:
    instance = tiny3x3_job_shop()
    schedule = hand_made_tiny3x3_schedule()
    summary = machine_load_summary(instance, schedule)
    assert sum(row["busy_time"] for row in summary) == 18  # 9 道工序共 18 个时间单位
    assert sum(row["load_share"] for row in summary) == pytest.approx(1.0)
    assert [row["machine_id"] for row in summary] == ["M1", "M2", "M0"]
    for row in summary:
        assert row["busy_time"] + row["idle_in_span"] == row["span"]
        assert 0.0 <= row["utilization"] <= 1.0


# ---------------------------------------------------------------------------
# 全体：每个返回的排程都要过独立验证器
# ---------------------------------------------------------------------------


_INSTANCES = {
    "tiny2x4_flow": tiny2x4_flow_shop,
    "tiny3x3_flow": tiny3x3_flow_shop,
    "tiny3x3_job": tiny3x3_job_shop,
}

_METHODS = {
    "flow_johnson": lambda inst: flowshop.flow_johnson(inst, {"objective": "makespan"}),
    "flow_neh": lambda inst: flowshop.flow_neh(inst, {"objective": "makespan"}),
    "jsp_priority": lambda inst: jsp_priority(inst, {"objective": "makespan"}),
    "jsp_cpsat": lambda inst: jsp_cpsat(
        inst, {"objective": "makespan", "time_limit": 10.0, "seed": 0}
    ),
}

_COMBINATIONS = tuple(
    (instance_name, method_name)
    for instance_name in _INSTANCES
    for method_name in _METHODS
)


@pytest.mark.parametrize("instance_name,method_name", _COMBINATIONS)
def test_every_returned_schedule_passes_the_independent_validator(
    instance_name: str, method_name: str
) -> None:
    """一网打尽：12 个「实例 × 方法」组合，凡是返回了排程的组合都必须过独立验证器。

    ``flow_johnson`` / ``flow_neh`` 在 job shop 实例上是 FAILED（没有排程），
    这里显式断言这一点，而不是悄悄跳过。
    """
    instance = _INSTANCES[instance_name]()
    result = _METHODS[method_name](instance)

    if result.schedule is None:
        assert result.status in ("FAILED", "INFEASIBLE", "UNKNOWN")
        assert result.best_bound is None
        return

    validate_schedule(instance, result.schedule)
    cmax = float(makespan(instance, result.schedule))
    assert result.objective == cmax
    assert result.breakdown["cmax"] == cmax
    assert result.solve_time >= 0.0 and result.build_time >= 0.0
    assert result.method == method_name


def test_flow_methods_decline_the_job_shop_instance() -> None:
    """两个 flow shop 方法都必须拒绝 job shop 实例（没有排程，也不编一个出来）。"""
    instance = tiny3x3_job_shop()
    for method in (flowshop.flow_johnson, flowshop.flow_neh):
        result = method(instance, {"objective": "makespan"})
        assert result.status == "FAILED"
        assert result.schedule is None
        assert result.objective is None
        assert result.detail["failure_reason"]
