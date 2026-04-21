from __future__ import annotations

from celery import Celery
from celery.states import FAILURE, SUCCESS
from ojs import SyncClient
from ojs.transport.fake import FakeTransport

from ojs_celery.backend import OJSResultBackend


def test_sync_client_worker_operations_use_transport() -> None:
    transport = FakeTransport()
    client = SyncClient("http://unused", transport=transport)

    job = client.enqueue("email.send", ["user@example.com"], queue="emails")
    fetched = client.fetch(["emails"], count=1, visibility_timeout_ms=5000)

    assert [item.id for item in fetched] == [job.id]
    assert client.queue_stats("emails").active == 1

    response = client.ack(job.id, result={"message_id": "msg-1"})

    assert response == {"job_id": job.id, "state": "completed"}
    completed = client.get_job(job.id)
    assert completed.result == {"message_id": "msg-1"}
    assert completed.state == "completed"
    client.close()


def test_sync_client_nack_preserves_structured_error() -> None:
    transport = FakeTransport()
    client = SyncClient("http://unused", transport=transport)
    job = client.enqueue("email.send", [])
    client.fetch(["default"])

    response = client.nack(
        job.id,
        {
            "code": "celery_rejected",
            "message": "Rejected by Celery consumer",
            "retryable": False,
        },
    )

    assert response == {"job_id": job.id, "state": "discarded"}
    failed = client.get_job(job.id)
    assert failed.errors[-1]["code"] == "celery_rejected"
    assert failed.state == "discarded"
    client.close()


def test_result_backend_uses_ack_and_nack_operations() -> None:
    transport = FakeTransport()
    client = SyncClient("http://unused", transport=transport)
    app = Celery("test")
    backend = OJSResultBackend(app=app)
    backend._client = client

    succeeded = client.enqueue("task.success", [])
    backend._store_result(succeeded.id, {"ok": True}, SUCCESS)
    success_meta = backend._get_task_meta_for(succeeded.id)

    assert success_meta["status"] == SUCCESS
    assert success_meta["result"] == {"ok": True}

    failed = client.enqueue("task.failure", [])
    backend._store_result(failed.id, ValueError("invalid"), FAILURE, "trace")
    failure_meta = backend._get_task_meta_for(failed.id)

    assert failure_meta["status"] == FAILURE
    assert str(failure_meta["result"]) == "invalid"
    assert failure_meta["traceback"] == "trace"
    backend.cleanup()
