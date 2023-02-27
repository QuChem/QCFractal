from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import pytest

from qcarchivetesting import load_molecule_data
from qcfractal.db_socket import SQLAlchemySocket
from qcfractal.testing_helpers import run_service
from qcportal.auth import UserInfo, GroupInfo
from qcportal.optimization import OptimizationSpecification, OptimizationProtocols
from qcportal.outputstore import OutputStore
from qcportal.record_models import RecordStatusEnum, PriorityEnum
from qcportal.singlepoint import QCSpecification, SinglepointProtocols
from qcportal.torsiondrive import TorsiondriveSpecification, TorsiondriveKeywords
from .testing_helpers import compare_torsiondrive_specs, test_specs, load_test_data, generate_task_key

if TYPE_CHECKING:
    from qcfractal.db_socket import SQLAlchemySocket
    from qcportal.managers import ManagerName


@pytest.mark.parametrize("spec", test_specs)
def test_torsiondrive_socket_add_get(storage_socket: SQLAlchemySocket, spec: TorsiondriveSpecification):
    hooh = load_molecule_data("peroxide2")
    td_mol_1 = load_molecule_data("td_C9H11NO2_1")
    td_mol_2 = load_molecule_data("td_C9H11NO2_2")

    time_0 = datetime.utcnow()
    meta, id = storage_socket.records.torsiondrive.add(
        [[hooh], [td_mol_1, td_mol_2]],
        spec,
        True,
        "tag1",
        PriorityEnum.low,
        None,
        None,
    )
    time_1 = datetime.utcnow()
    assert meta.success

    recs = storage_socket.records.torsiondrive.get(id, include=["*", "initial_molecules", "service"])

    assert len(recs) == 2
    for r in recs:
        assert r["record_type"] == "torsiondrive"
        assert r["status"] == RecordStatusEnum.waiting
        assert compare_torsiondrive_specs(spec, r["specification"])

        # Service queue entry should exist with the proper tag and priority
        assert r["service"]["tag"] == "tag1"
        assert r["service"]["priority"] == PriorityEnum.low

        assert time_0 < r["created_on"] < time_1
        assert time_0 < r["modified_on"] < time_1
        assert time_0 < r["service"]["created_on"] < time_1

    assert len(recs[0]["initial_molecules"]) == 1
    assert len(recs[1]["initial_molecules"]) == 2

    assert recs[0]["initial_molecules"][0]["identifiers"]["molecule_hash"] == hooh.get_hash()

    # Not necessarily in the input order
    hash1 = recs[1]["initial_molecules"][0]["identifiers"]["molecule_hash"]
    hash2 = recs[1]["initial_molecules"][1]["identifiers"]["molecule_hash"]
    assert {hash1, hash2} == {td_mol_1.get_hash(), td_mol_2.get_hash()}


def test_torsiondrive_socket_add_same_1(storage_socket: SQLAlchemySocket):
    spec = TorsiondriveSpecification(
        program="torsiondrive",
        keywords=TorsiondriveKeywords(
            dihedrals=[(8, 11, 15, 13)],
            grid_spacing=[15],
            dihedral_ranges=None,
            energy_decrease_thresh=None,
            energy_upper_limit=0.05,
        ),
        optimization_specification=OptimizationSpecification(
            program="optprog1",
            keywords={"k": "value"},
            protocols=OptimizationProtocols(),
            qc_specification=QCSpecification(
                program="prog2",
                driver="deferred",
                method="b3lyp",
                basis="6-31g",
                keywords={"k2": "values2"},
                protocols=SinglepointProtocols(wavefunction="all"),
            ),
        ),
    )

    hooh = load_molecule_data("peroxide2")
    meta, id1 = storage_socket.records.torsiondrive.add([[hooh]], spec, True, "*", PriorityEnum.normal, None, None)
    assert meta.n_inserted == 1
    assert meta.inserted_idx == [0]

    meta, id2 = storage_socket.records.torsiondrive.add([[hooh]], spec, True, "*", PriorityEnum.normal, None, None)
    assert meta.n_inserted == 0
    assert meta.n_existing == 1
    assert meta.existing_idx == [0]
    assert id1 == id2


def test_torsiondrive_socket_add_same_2(storage_socket: SQLAlchemySocket):
    # multiple molecule ordering, and duplicate molecules
    spec = TorsiondriveSpecification(
        program="torsiondrive",
        keywords=TorsiondriveKeywords(
            dihedrals=[(8, 11, 15, 13)],
            grid_spacing=[15],
            dihedral_ranges=None,
            energy_decrease_thresh=None,
            energy_upper_limit=0.05,
        ),
        optimization_specification=OptimizationSpecification(
            program="optprog1",
            keywords={"k": "value"},
            protocols=OptimizationProtocols(),
            qc_specification=QCSpecification(
                program="prog2",
                driver="deferred",
                method="b3lyp",
                basis="6-31g",
                keywords={"k2": "values2"},
                protocols=SinglepointProtocols(wavefunction="all"),
            ),
        ),
    )

    mol1 = load_molecule_data("td_C9H11NO2_0")
    mol2 = load_molecule_data("td_C9H11NO2_1")
    mol3 = load_molecule_data("td_C9H11NO2_2")
    meta, id1 = storage_socket.records.torsiondrive.add(
        [[mol1, mol2, mol3]],
        spec,
        True,
        "*",
        PriorityEnum.normal,
        None,
        None,
    )
    assert meta.n_inserted == 1
    assert meta.inserted_idx == [0]

    meta, id2 = storage_socket.records.torsiondrive.add(
        [[mol2, mol3, mol1, mol2], [mol3, mol2, mol1, mol1]],
        spec,
        True,
        "*",
        PriorityEnum.normal,
        None,
        None,
    )
    assert meta.n_inserted == 0
    assert meta.n_existing == 2
    assert meta.existing_idx == [0, 1]
    assert id2 == [id1[0], id1[0]]


def test_torsiondrive_socket_add_same_3(storage_socket: SQLAlchemySocket):
    # some modifications to the input specification
    spec1 = TorsiondriveSpecification(
        program="torsiondrive",
        keywords=TorsiondriveKeywords(
            dihedrals=[(8, 11, 15, 13)],
            grid_spacing=[15],
            dihedral_ranges=None,
            energy_decrease_thresh=None,
            energy_upper_limit=0.05,
        ),
        optimization_specification=OptimizationSpecification(
            program="optprog1",
            keywords={"k": "value"},
            protocols=OptimizationProtocols(),
            qc_specification=QCSpecification(
                program="prog2",
                driver="deferred",
                method="b3lyp",
                basis="6-31g",
                keywords={"k2": "values2"},
                protocols=SinglepointProtocols(wavefunction="all"),
            ),
        ),
    )

    spec2 = TorsiondriveSpecification(
        program="torsiondrive",
        keywords=TorsiondriveKeywords(
            dihedrals=[(8, 11, 15, 13)],
            grid_spacing=[15],
            dihedral_ranges=None,
            energy_decrease_thresh=None,
            energy_upper_limit=0.05,
        ),
        optimization_specification=OptimizationSpecification(
            program="optPROG1",
            keywords={"k": "value"},
            qc_specification=QCSpecification(
                program="prOG2",
                driver="deferred",
                method="b3LYP",
                basis="6-31g",
                keywords={"k2": "values2"},
                protocols=SinglepointProtocols(wavefunction="all", stdout=True),
            ),
        ),
    )

    mol1 = load_molecule_data("td_C9H11NO2_0")
    mol2 = load_molecule_data("td_C9H11NO2_1")
    mol3 = load_molecule_data("td_C9H11NO2_2")
    meta, id1 = storage_socket.records.torsiondrive.add(
        [[mol1, mol2, mol3]],
        spec1,
        True,
        "*",
        PriorityEnum.normal,
        None,
        None,
    )
    assert meta.n_inserted == 1
    assert meta.inserted_idx == [0]

    meta, id2 = storage_socket.records.torsiondrive.add(
        [[mol1, mol2, mol3]],
        spec2,
        True,
        "*",
        PriorityEnum.normal,
        None,
        None,
    )
    assert meta.n_inserted == 0
    assert meta.n_existing == 1
    assert meta.existing_idx == [0]
    assert id1 == id2


def test_torsiondrive_socket_add_different_1(storage_socket: SQLAlchemySocket):
    # Molecules are a subset of another
    spec = TorsiondriveSpecification(
        program="torsiondrive",
        keywords=TorsiondriveKeywords(
            dihedrals=[(8, 11, 15, 13)],
            grid_spacing=[15],
            dihedral_ranges=None,
            energy_decrease_thresh=None,
            energy_upper_limit=0.05,
        ),
        optimization_specification=OptimizationSpecification(
            program="optprog1",
            keywords={"k": "value"},
            protocols=OptimizationProtocols(),
            qc_specification=QCSpecification(
                program="prog2",
                driver="deferred",
                method="b3lyp",
                basis="6-31g",
                keywords={"k2": "values2"},
                protocols=SinglepointProtocols(wavefunction="all"),
            ),
        ),
    )

    mol1 = load_molecule_data("td_C9H11NO2_0")
    mol2 = load_molecule_data("td_C9H11NO2_1")
    mol3 = load_molecule_data("td_C9H11NO2_2")
    meta, id1 = storage_socket.records.torsiondrive.add(
        [[mol1, mol2, mol3]],
        spec,
        True,
        "*",
        PriorityEnum.normal,
        None,
        None,
    )
    assert meta.n_inserted == 1
    assert meta.inserted_idx == [0]

    meta, id2 = storage_socket.records.torsiondrive.add(
        [[mol1], [mol3, mol2], [mol2, mol3, mol1]],
        spec,
        True,
        "*",
        PriorityEnum.normal,
        None,
        None,
    )
    assert meta.n_inserted == 2
    assert meta.n_existing == 1
    assert meta.existing_idx == [2]
    assert meta.inserted_idx == [0, 1]
    assert id1[0] == id2[2]


@pytest.mark.parametrize(
    "test_data_name",
    [
        "td_C9H11NO2_mopac_pm6",
        "td_H2O2_mopac_pm6",
        "td_H2O2_psi4_pbe",
    ],
)
def test_torsiondrive_socket_run(
    storage_socket: SQLAlchemySocket, activated_manager_name: ManagerName, test_data_name: str
):
    input_spec_1, molecules_1, result_data_1 = load_test_data(test_data_name)

    storage_socket.groups.add(GroupInfo(groupname="group1"))
    storage_socket.users.add(UserInfo(username="submit_user", role="submit", groups=["group1"], enabled=True))

    meta_1, id_1 = storage_socket.records.torsiondrive.add(
        [molecules_1],
        input_spec_1,
        True,
        "test_tag",
        PriorityEnum.low,
        "submit_user",
        "group1",
    )
    assert meta_1.success

    time_0 = datetime.utcnow()
    finished, n_optimizations = run_service(
        storage_socket, activated_manager_name, id_1[0], generate_task_key, result_data_1, 1000
    )
    time_1 = datetime.utcnow()

    rec = storage_socket.records.torsiondrive.get(
        id_1,
        include=[
            "*",
            "compute_history.*",
            "compute_history.outputs",
            "optimizations.*",
            "optimizations.optimization_record",
            "service",
        ],
    )

    assert rec[0]["status"] == RecordStatusEnum.complete
    assert time_0 < rec[0]["modified_on"] < time_1
    assert len(rec[0]["compute_history"]) == 1
    assert len(rec[0]["compute_history"][-1]["outputs"]) == 1
    assert rec[0]["compute_history"][-1]["status"] == RecordStatusEnum.complete
    assert time_0 < rec[0]["compute_history"][-1]["modified_on"] < time_1
    assert rec[0]["service"] is None
    out = OutputStore(**rec[0]["compute_history"][-1]["outputs"]["stdout"])
    assert "Job Finished" in out.as_string

    assert len(rec[0]["optimizations"]) == n_optimizations