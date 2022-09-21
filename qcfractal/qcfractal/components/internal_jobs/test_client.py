from __future__ import annotations

import socket
import threading
import time
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from qcfractal.components.internal_jobs.socket import InternalJobSocket
from qcportal import PortalRequestError
from qcportal.internal_jobs import InternalJobStatusEnum

if TYPE_CHECKING:
    from qcfractal.db_socket import SQLAlchemySocket
    from qcportal.client import PortalClient


# Add in another function to the internal_jobs socket for testing
def dummmy_internal_job(self, iterations: int, session, job_status):
    for i in range(iterations):
        time.sleep(1.0)
        job_status.update_progress(100 * ((i + 1) / iterations))
        print("Dummy internal job counter ", i)

        if job_status.cancelled():
            return "Internal job cancelled"

    return "Internal job finished"


# And another one for errors
def dummmy_internal_job_error(self, session, job_status):
    raise RuntimeError("Expected error")


setattr(InternalJobSocket, "dummy_job", dummmy_internal_job)
setattr(InternalJobSocket, "dummy_job_error", dummmy_internal_job_error)


def test_internal_jobs_client_error(snowflake_client: PortalClient, storage_socket: SQLAlchemySocket):
    id_1 = storage_socket.internal_jobs.add(
        "dummy_job_error", datetime.utcnow(), "internal_jobs.dummy_job_error", {}, None, unique_name=False
    )

    # Faster updates for testing
    storage_socket.internal_jobs._update_frequency = 1

    time_0 = datetime.utcnow()
    end_event = threading.Event()
    th = threading.Thread(target=storage_socket.internal_jobs._run_loop, args=(end_event,))
    th.start()
    time.sleep(3)
    time_1 = datetime.utcnow()
    end_event.set()
    th.join()

    job_1 = snowflake_client.get_internal_job(id_1)
    assert job_1.status == InternalJobStatusEnum.error
    assert job_1.progress < 100
    assert time_0 < job_1.ended_date < time_1
    assert time_0 < job_1.last_updated < time_1
    assert job_1.result == "Expected error"


def test_internal_jobs_client_cancel_waiting(snowflake_client: PortalClient, storage_socket: SQLAlchemySocket):
    id_1 = storage_socket.internal_jobs.add(
        "dummy_job", datetime.utcnow(), "internal_jobs.dummy_job", {"iterations": 10}, None, unique_name=False
    )

    snowflake_client.cancel_internal_job(id_1)

    job_1 = snowflake_client.get_internal_job(id_1)
    assert job_1.status == InternalJobStatusEnum.cancelled
    assert job_1.result is None
    assert job_1.started_date is None
    assert job_1.progress == 0


def test_internal_jobs_client_cancel_running(snowflake_client: PortalClient, storage_socket: SQLAlchemySocket):
    id_1 = storage_socket.internal_jobs.add(
        "dummy_job", datetime.utcnow(), "internal_jobs.dummy_job", {"iterations": 10}, None, unique_name=False
    )

    # Faster updates for testing
    storage_socket.internal_jobs._update_frequency = 1

    end_event = threading.Event()
    th = threading.Thread(target=storage_socket.internal_jobs._run_loop, args=(end_event,))
    th.start()
    time.sleep(4)

    try:
        job_1 = snowflake_client.get_internal_job(id_1)
        assert job_1.status == InternalJobStatusEnum.running
        assert job_1.progress > 10

        snowflake_client.cancel_internal_job(id_1)
        time.sleep(6)

        job_1 = snowflake_client.get_internal_job(id_1)
        assert job_1.status == InternalJobStatusEnum.cancelled
        assert job_1.progress < 50
        assert job_1.result == "Internal job cancelled"

    finally:
        end_event.set()
        th.join()


def test_internal_jobs_client_delete_waiting(snowflake_client: PortalClient, storage_socket: SQLAlchemySocket):
    id_1 = storage_socket.internal_jobs.add(
        "dummy_job", datetime.utcnow(), "internal_jobs.dummy_job", {"iterations": 10}, None, unique_name=False
    )

    snowflake_client.delete_internal_job(id_1)

    with pytest.raises(PortalRequestError, match="Internal job.*not found"):
        snowflake_client.get_internal_job(id_1)


def test_internal_jobs_client_delete_running(snowflake_client: PortalClient, storage_socket: SQLAlchemySocket):
    id_1 = storage_socket.internal_jobs.add(
        "dummy_job", datetime.utcnow(), "internal_jobs.dummy_job", {"iterations": 10}, None, unique_name=False
    )

    # Faster updates for testing
    storage_socket.internal_jobs._update_frequency = 1

    end_event = threading.Event()
    th = threading.Thread(target=storage_socket.internal_jobs._run_loop, args=(end_event,))
    th.start()
    time.sleep(4)

    try:
        job_1 = snowflake_client.get_internal_job(id_1)
        assert job_1.status == InternalJobStatusEnum.running
        assert job_1.progress > 10

        snowflake_client.delete_internal_job(id_1)
        time.sleep(6)

        with pytest.raises(PortalRequestError, match="Internal job.*not found"):
            snowflake_client.get_internal_job(id_1)

    finally:
        end_event.set()
        th.join()


def test_internal_jobs_client_query(snowflake_client: PortalClient, storage_socket: SQLAlchemySocket):

    time_0 = datetime.utcnow()
    id_1 = storage_socket.internal_jobs.add(
        "dummy_job", datetime.utcnow(), "internal_jobs.dummy_job", {"iterations": 1}, None, unique_name=False
    )
    time_1 = datetime.utcnow()

    # Faster updates for testing
    storage_socket.internal_jobs._update_frequency = 1

    end_event = threading.Event()
    th = threading.Thread(target=storage_socket.internal_jobs._run_loop, args=(end_event,))
    th.start()
    time.sleep(4)
    time_2 = datetime.utcnow()

    try:
        job_1 = snowflake_client.get_internal_job(id_1)
        assert job_1.status == InternalJobStatusEnum.complete

    finally:
        end_event.set()
        th.join()

    # Add one that will be waiting
    id_2 = storage_socket.internal_jobs.add(
        "dummy_job", datetime.utcnow(), "internal_jobs.dummy_job", {"iterations": 1}, None, unique_name=False
    )

    time_3 = datetime.utcnow()

    # Now do some queries
    result = snowflake_client.query_internal_jobs(job_id=id_1)
    r = list(result)
    assert result.current_meta.n_found == 1
    assert len(r) == 1
    assert r[0].id == id_1

    result = snowflake_client.query_internal_jobs(name="dummy_job", status=["complete"])
    r = list(result)
    assert result.current_meta.n_found == 1
    assert len(r) == 1
    assert r[0].id == id_1

    result = snowflake_client.query_internal_jobs(name="dummy_job", status="waiting")
    r = list(result)
    assert result.current_meta.n_found == 1
    assert len(r) == 1
    assert r[0].id == id_2

    result = snowflake_client.query_internal_jobs(name="dummy_job", added_after=time_0)
    r = list(result)
    assert result.current_meta.n_found == 2
    assert len(r) == 2
    assert {r[0].id, r[1].id} == {id_1, id_2}

    result = snowflake_client.query_internal_jobs(name="dummy_job", added_after=time_1, added_before=time_3)
    r = list(result)
    assert result.current_meta.n_found == 1
    assert len(r) == 1
    assert r[0].id == id_2

    result = snowflake_client.query_internal_jobs(name="dummy_job", last_updated_after=time_2)
    r = list(result)
    assert result.current_meta.n_found == 0
    assert len(r) == 0

    result = snowflake_client.query_internal_jobs(name="dummy_job", last_updated_before=time_2)
    r = list(result)
    assert result.current_meta.n_found == 1
    assert len(r) == 1
    assert r[0].id == id_1

    result = snowflake_client.query_internal_jobs(runner_hostname=socket.gethostname())
    assert result.current_meta.n_found >= 2

    # Empty query - all
    # This should be at least two - other services were probably added by the socket
    result = snowflake_client.query_internal_jobs()
    assert result.current_meta.n_found >= 2

    # Should also have a bunch
    result = snowflake_client.query_internal_jobs(scheduled_before=datetime.utcnow())
    assert result.current_meta.n_found >= 2

    # nothing scheduled 10 days from now
    result = snowflake_client.query_internal_jobs(scheduled_after=datetime.utcnow() + timedelta(days=10))
    assert result.current_meta.n_found == 0

    # Some queries for non-existent stuff
    result = snowflake_client.query_internal_jobs(name="abcd")
    assert result.current_meta.n_found == 0

    # Some queries for non-existent stuff
    result = snowflake_client.query_internal_jobs(status="error")
    assert result.current_meta.n_found == 0