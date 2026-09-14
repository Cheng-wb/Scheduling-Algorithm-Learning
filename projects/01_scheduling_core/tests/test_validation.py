"""validation.py 的单元测试：合法实例通过、非法实例被拒绝。"""

import pytest

from scheduling_core.models import Instance, Job, Machine, Operation
from scheduling_core.validation import InstanceValidationError, validate_instance


def _machine(id="M1"):
    return Machine(id=id, name=f"Machine {id}")


def _operation(id, job_id, processing_time=3, eligible_machine_ids=("M1",)):
    return Operation(
        id=id,
        job_id=job_id,
        processing_time=processing_time,
        eligible_machine_ids=eligible_machine_ids,
    )


def _job(id, operation_ids, release_time=0, due_date=None, weight=1.0):
    return Job(
        id=id,
        operation_ids=operation_ids,
        release_time=release_time,
        due_date=due_date,
        weight=weight,
    )


def test_valid_instance_passes():
    inst = Instance(
        jobs=(_job("J1", ("O1",), due_date=8),),
        operations=(_operation("O1", "J1"),),
        machines=(_machine("M1"),),
    )
    validate_instance(inst)


def test_reject_duplicate_machine_id():
    inst = Instance(
        jobs=(_job("J1", ("O1",)),),
        operations=(_operation("O1", "J1"),),
        machines=(_machine("M1"), _machine("M1")),
    )
    with pytest.raises(InstanceValidationError):
        validate_instance(inst)


def test_reject_duplicate_job_id():
    inst = Instance(
        jobs=(_job("J1", ("O1",)), _job("J1", ("O2",))),
        operations=(_operation("O1", "J1"), _operation("O2", "J1")),
        machines=(_machine("M1"),),
    )
    with pytest.raises(InstanceValidationError):
        validate_instance(inst)


def test_reject_duplicate_operation_id():
    inst = Instance(
        jobs=(_job("J1", ("O1",)),),
        operations=(_operation("O1", "J1"), _operation("O1", "J1")),
        machines=(_machine("M1"),),
    )
    with pytest.raises(InstanceValidationError):
        validate_instance(inst)


@pytest.mark.parametrize("processing_time", [0, -1, -10])
def test_reject_non_positive_processing_time(processing_time):
    inst = Instance(
        jobs=(_job("J1", ("O1",)),),
        operations=(_operation("O1", "J1", processing_time=processing_time),),
        machines=(_machine("M1"),),
    )
    with pytest.raises(InstanceValidationError):
        validate_instance(inst)


def test_reject_negative_release_time():
    inst = Instance(
        jobs=(_job("J1", ("O1",), release_time=-1),),
        operations=(_operation("O1", "J1"),),
        machines=(_machine("M1"),),
    )
    with pytest.raises(InstanceValidationError):
        validate_instance(inst)


@pytest.mark.parametrize("weight", [0, -1])
def test_reject_non_positive_weight(weight):
    inst = Instance(
        jobs=(_job("J1", ("O1",), weight=weight),),
        operations=(_operation("O1", "J1"),),
        machines=(_machine("M1"),),
    )
    with pytest.raises(InstanceValidationError):
        validate_instance(inst)


def test_reject_negative_due_date():
    inst = Instance(
        jobs=(_job("J1", ("O1",), due_date=-1),),
        operations=(_operation("O1", "J1"),),
        machines=(_machine("M1"),),
    )
    with pytest.raises(InstanceValidationError):
        validate_instance(inst)


def test_reject_unknown_job():
    inst = Instance(
        jobs=(_job("J1", ("O1",)),),
        operations=(_operation("O1", "J2"),),
        machines=(_machine("M1"),),
    )
    with pytest.raises(InstanceValidationError):
        validate_instance(inst)


def test_reject_unknown_machine():
    inst = Instance(
        jobs=(_job("J1", ("O1",)),),
        operations=(_operation("O1", "J1", eligible_machine_ids=("M99",)),),
        machines=(_machine("M1"),),
    )
    with pytest.raises(InstanceValidationError):
        validate_instance(inst)


def test_reject_empty_eligible_machines():
    inst = Instance(
        jobs=(_job("J1", ("O1",)),),
        operations=(_operation("O1", "J1", eligible_machine_ids=()),),
        machines=(_machine("M1"),),
    )
    with pytest.raises(InstanceValidationError):
        validate_instance(inst)


def test_reject_unknown_operation_in_job():
    inst = Instance(
        jobs=(_job("J1", ("O1", "O99")),),
        operations=(_operation("O1", "J1"),),
        machines=(_machine("M1"),),
    )
    with pytest.raises(InstanceValidationError):
        validate_instance(inst)


def test_reject_operation_job_id_mismatch():
    # J1.operation_ids 含 O1，但 O1.job_id 指向 J2 → 正向不一致
    inst = Instance(
        jobs=(_job("J1", ("O1",)), _job("J2", ())),
        operations=(_operation("O1", "J2"),),
        machines=(_machine("M1"),),
    )
    with pytest.raises(InstanceValidationError):
        validate_instance(inst)


def test_reject_operation_missing_from_job():
    # O1.job_id 指向 J1，但 J1.operation_ids 不含 O1 → 反向不一致
    inst = Instance(
        jobs=(_job("J1", ("O2",)),),
        operations=(_operation("O1", "J1"), _operation("O2", "J1")),
        machines=(_machine("M1"),),
    )
    with pytest.raises(InstanceValidationError):
        validate_instance(inst)
