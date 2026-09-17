"""W4 诊断模块的测试：数值缩放与不可行冲突定位。

刻意全部使用**小实例 + 短时间上限**。``diagnose_infeasibility`` 的删除过滤会对
冲突集反复重解，实例一大、预算一高，总耗时就会失控——这个测试文件的速度本身
就是一条纪律。

期望值全部来自手算或已证事实，不由被测函数生成。
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from opt_common.bridge import generate_instance  # noqa: E402
from opt_models.diagnostics import (  # noqa: E402
    deadlines_with_slack,
    diagnose_infeasibility,
    rescale_instance,
    scaling_report,
)


# --- 数值缩放 ------------------------------------------------------------


def test_span_is_a_ratio_and_therefore_scale_invariant() -> None:
    """span 是「最大系数 / 最小非零系数」，缩放不该改变它。"""
    instance = generate_instance(82, jobs=6, machines=1)
    base = scaling_report(instance)
    for factor in (10.0, 100.0):
        scaled = scaling_report(rescale_instance(instance, factor))
        assert scaled.span == pytest.approx(base.span), "span 是比值，缩放不应改变它"
        # 绝对量级则确实随因子放大
        assert scaled.horizon == pytest.approx(base.horizon * factor, rel=1e-9)


def test_rescale_preserves_job_count_and_positive_times() -> None:
    instance = generate_instance(82, jobs=6, machines=1)
    scaled = rescale_instance(instance, 10.0)
    assert len(scaled.jobs) == len(instance.jobs)
    assert len(scaled.operations) == len(instance.operations)
    assert all(op.processing_time > 0 for op in scaled.operations)


def test_scaling_report_exposes_tight_and_big_m_spans() -> None:
    instance = generate_instance(82, jobs=6, machines=1)
    report = scaling_report(instance)
    assert report.tight_model_span == pytest.approx(report.span)
    # Week 2 的模块存在时，Big-M 数值必须被真的取到，而不是编一个
    if report.big_m:
        assert set(report.big_m) >= {"loose", "pair_max", "pair_min"}
        assert report.big_m_span > report.tight_model_span, (
            "松模型的系数跨度应当大于紧模型"
        )


def test_scaling_report_notes_are_present() -> None:
    report = scaling_report(generate_instance(82, jobs=6, machines=1))
    assert report.notes
    assert any("Big-M" in note for note in report.notes)


# --- 交期旋钮 ------------------------------------------------------------


def test_deadlines_with_slack_uses_the_documented_formula() -> None:
    """d_j = r_j + ceil(slack * p_j)，逐作业手算核对。"""
    instance = generate_instance(82, jobs=3, machines=1)
    deadlines = deadlines_with_slack(instance, 1.5)
    for job in instance.jobs:
        own = sum(
            op.processing_time for op in instance.operations if op.job_id == job.id
        )
        assert deadlines[job.id] == job.release_time + math.ceil(1.5 * own)


def test_deadlines_with_slack_rejects_non_positive() -> None:
    instance = generate_instance(82, jobs=3, machines=1)
    for slack in (0.0, -1.0):
        with pytest.raises(ValueError, match="slack must be positive"):
            deadlines_with_slack(instance, slack)


def test_smaller_slack_gives_tighter_deadlines() -> None:
    instance = generate_instance(82, jobs=4, machines=1)
    tight = deadlines_with_slack(instance, 0.5)
    loose = deadlines_with_slack(instance, 2.0)
    for job_id in tight:
        assert tight[job_id] <= loose[job_id]


# --- 不可行诊断 ----------------------------------------------------------


def test_zero_deadlines_are_infeasible_and_located() -> None:
    """每个作业交期为 0 时必然不可行；求解器应定位出冲突作业。"""
    instance = generate_instance(82, jobs=5, machines=1)
    deadlines = {job.id: 0 for job in instance.jobs}
    report = diagnose_infeasibility(instance, deadlines, time_limit=3.0)

    assert report.status == "INFEASIBLE"
    assert report.feasible is False
    assert report.reported_conflict, "应当给出充分冲突集"
    assert report.minimal_conflict, "删除过滤后应当给出极小冲突集"
    assert set(report.minimal_conflict) <= set(report.assumed_jobs)


def test_minimal_conflict_is_verified_irreducible() -> None:
    """IIS 的定义必须被真的验证过：整体不可行，去掉任一元素即可行。"""
    instance = generate_instance(82, jobs=5, machines=1)
    deadlines = {job.id: 0 for job in instance.jobs}
    report = diagnose_infeasibility(instance, deadlines, time_limit=3.0)

    assert report.verification.get("still_infeasible") is True
    assert report.verification.get("irreducible") is True


def test_generous_deadlines_are_feasible() -> None:
    """交期给得足够宽时，同一组假设应当可行，且返回的排程过独立验证。"""
    instance = generate_instance(82, jobs=4, machines=1)
    deadlines = deadlines_with_slack(instance, 10.0)
    report = diagnose_infeasibility(instance, deadlines, time_limit=3.0)

    assert report.status == "FEASIBLE"
    assert report.feasible is True
    assert report.minimal_conflict == ()
    assert report.schedule is not None
    from opt_common.bridge import validate_schedule

    validate_schedule(instance, report.schedule)


def test_report_is_serializable_and_self_describing() -> None:
    """报告里不能夹带求解器对象，否则写进 JSON 会炸。"""
    import json
    from dataclasses import asdict

    instance = generate_instance(82, jobs=4, machines=1)
    deadlines = {job.id: 0 for job in instance.jobs}
    report = diagnose_infeasibility(instance, deadlines, time_limit=3.0)

    payload = asdict(report)
    payload.pop("schedule", None)  # 排程是 frozen dataclass，单独序列化
    json.dumps(payload, ensure_ascii=False)  # 不应抛异常
    assert report.notes, "报告应带免责说明"
    assert report.solves >= 1


def test_diagnosis_is_bounded_by_the_time_limit() -> None:
    """求解次数有限、总耗时不失控——这正是上一个代理卡死的地方。"""
    instance = generate_instance(82, jobs=4, machines=1)
    deadlines = {job.id: 0 for job in instance.jobs}
    report = diagnose_infeasibility(instance, deadlines, time_limit=1.0)
    # 4 个作业 + 删除过滤，求解次数应该是作业数量的常数倍，不是爆炸式增长
    assert report.solves <= 4 * len(instance.jobs)
    assert report.solver_wall_time < 60.0


# --- 失败分支（week4.md 点名要覆盖的四条） --------------------------------


def test_missing_deadline_is_rejected_before_solving() -> None:
    """分支①：有作业不在假设集合里 → 直接 FAILED，并说明是哪个作业。"""
    instance = generate_instance(82, jobs=4, machines=1)
    partial = {job.id: 0 for job in instance.jobs[:2]}  # 故意只给前两个作业
    report = diagnose_infeasibility(instance, partial, time_limit=3.0)

    assert report.status == "FAILED"
    assert report.solves == 0, "假设集合不完整时不该浪费求解"
    assert "no deadline" in report.detail["failure_reason"]
    assert set(report.assumed_jobs) == set(partial)


def test_undecided_solver_is_reported_as_unknown_not_infeasible() -> None:
    """分支②：预算小到求解器无法判定 → UNKNOWN，且**不**声称有冲突集。

    这正是「解不出来」与「证明不可行」的区别：前者不能拿来当结论。
    """
    instance = generate_instance(70, jobs=20, machines=1)
    deadlines = {job.id: 0 for job in instance.jobs}
    report = diagnose_infeasibility(instance, deadlines, time_limit=0.001)

    assert report.status in ("UNKNOWN", "INFEASIBLE"), report.status
    if report.status == "UNKNOWN":
        assert report.minimal_conflict == ()
        assert "连「哪组约束冲突」都还不能断言" in report.detail["failure_reason"]
    else:
        # 求解器极快就判定了不可行也是合法结果；此时必须真的定位到冲突
        assert report.minimal_conflict


def test_feasible_case_reports_no_conflict_and_a_valid_schedule() -> None:
    """分支③：可行 → 不报冲突，并且返回的排程要过 M1 的独立验证器。"""
    from opt_common.bridge import schedule_errors

    instance = generate_instance(82, jobs=4, machines=1)
    report = diagnose_infeasibility(
        instance, deadlines_with_slack(instance, 10.0), time_limit=3.0
    )
    assert report.status == "FEASIBLE"
    assert report.reported_conflict == () and report.minimal_conflict == ()
    assert report.verification == {}, "可行时没有 IIS 可验证"
    assert report.schedule is not None
    assert schedule_errors(instance, report.schedule) == []


def test_assumptions_blamed_flag_exists_when_a_conflict_is_found() -> None:
    """分支④「不可行但归因不到假设」在当前 API 下不易构造，这里如实记录。

    ``diagnose_infeasibility`` 只有一组 `AddAssumption`（准时假设），要让硬约束
    自身不可行 —— 而那要求一个通不过 ``validate_instance`` 的实例。所以那条分支
    目前只能靠代码审查确认存在（``verification["assumptions_blamed"] = False``），
    这里不伪造一个用例来假装覆盖了它。
    """
    instance = generate_instance(82, jobs=4, machines=1)
    deadlines = {job.id: 0 for job in instance.jobs}
    report = diagnose_infeasibility(instance, deadlines, time_limit=3.0)
    # 走的是正常归因路径：找到了冲突，因此 assumptions_blamed 不为 False
    assert report.verification.get("assumptions_blamed") is not False
    assert report.minimal_conflict
