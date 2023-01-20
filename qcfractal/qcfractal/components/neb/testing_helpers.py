from __future__ import annotations

from typing import TYPE_CHECKING, Tuple, Optional, Dict, List, Union, Any

import pydantic
from qcelemental.models import Molecule, FailedOperation, ComputeError, AtomicResult, OptimizationResult

from qcarchivetesting.helpers import read_record_data
from qcfractal.testing_helpers import run_service
from qcportal.neb import NEBSpecification, NEBKeywords
from qcportal.record_models import PriorityEnum, RecordStatusEnum
from qcportal.singlepoint import SinglepointProtocols, QCSpecification
from qcportal.utils import recursive_normalizer, hash_dict

if TYPE_CHECKING:
    from qcfractal.db_socket import SQLAlchemySocket
    from qcportal.managers import ManagerName


test_specs = [
    NEBSpecification(
        program="geometric",
        keywords=NEBKeywords(
            images=11,
            spring_constant=0.1,
            energy_weighted=5,
        ),
        singlepoint_specification=QCSpecification(
            program="psi4",
            keywords={"k": "value"},
            driver="deferred",
            method="b3lyp",
            basis="6-31g",
            protocols=SinglepointProtocols(wavefunction="all"),
        ),
    ),
    NEBSpecification(
        program="geometric",
        keywords=NEBKeywords(
            images=11,
            spring_constant=0.5,
            energy_weighted=10,
        ),
        singlepoint_specification=QCSpecification(
            program="psi4",
            keywords={"k": "value"},
            driver="deferred",
            method="CCSD(T)",
            basis="def2-tzvp",
            protocols=SinglepointProtocols(wavefunction="all"),
        ),
    ),
]


def compare_neb_specs(
    input_spec: Union[NEBSpecification, Dict[str, Any]],
    output_spec: Union[NEBSpecification, Dict[str, Any]],
) -> bool:
    if isinstance(input_spec, dict):
        input_spec = NEBSpecification(**input_spec)
    if isinstance(output_spec, dict):
        output_spec = NEBSpecification(**output_spec)

    return input_spec == output_spec


def generate_task_key(record):
    record_type = record["record_type"]

    if record_type == "optimization":
        mol_hash = record["initial_molecule"]["identifiers"]["molecule_hash"]
    else:
        mol_hash = record["molecule"]["identifiers"]["molecule_hash"]

    return record_type + "|" + mol_hash


def load_test_data(
    name: str,
) -> Tuple[NEBSpecification, List[Molecule], Dict[str, Union[AtomicResult, OptimizationResult]]]:
    test_data = read_record_data(name)

    return (
        pydantic.parse_obj_as(NEBSpecification, test_data["specification"]),
        pydantic.parse_obj_as(List[Molecule], test_data["initial_chain"]),
        pydantic.parse_obj_as(Dict[str, Union[AtomicResult, OptimizationResult]], test_data["results"]),
    )


def submit_test_data(
    storage_socket: SQLAlchemySocket,
    name: str,
    tag: Optional[str] = "*",
    priority: PriorityEnum = PriorityEnum.normal,
) -> Tuple[int, Dict[str, Any]]:

    input_spec, initial_chain, result = load_test_data(name)
    meta, record_ids = storage_socket.records.neb.add([initial_chain], input_spec, tag, priority, None, None)
    assert meta.success
    assert len(record_ids) == 1
    assert meta.n_inserted == 1

    return record_ids[0], result


def run_test_data(
    storage_socket: SQLAlchemySocket,
    manager_name: ManagerName,
    name: str,
    tag: Optional[str] = "*",
    priority: PriorityEnum = PriorityEnum.normal,
    end_status: RecordStatusEnum = RecordStatusEnum.complete,
):
    record_id, result = submit_test_data(storage_socket, name, tag, priority)

    record = storage_socket.records.get([record_id])[0]
    assert record["status"] == RecordStatusEnum.waiting

    if end_status == RecordStatusEnum.error:
        failed_op = FailedOperation(
            error=ComputeError(error_type="test_error", error_message="this is just a test error"),
        )
        result = {x: failed_op for x in result}

    finished, n_optimizations = run_service(storage_socket, manager_name, record_id, generate_task_key, result, 200)
    assert finished

    record = storage_socket.records.get([record_id], include=["status"])[0]
    assert record["status"] == end_status

    return record_id
