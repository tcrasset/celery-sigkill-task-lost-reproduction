import time
import subprocess
import celery
from uuid import  uuid4

from celery import group, chord, Celery
from celery.result import AsyncResult
from typing import Any


app: Celery = Celery(
    "worker",
    backend="redis://127.0.0.1:6379/1",
    broker="redis://127.0.0.1:6379/0",
    result_extended=True,
    task_track_started=True,
    task_reject_on_worker_lost=True,
    task_acks_late=True,
    broker_connection_retry_on_startup=True
)


@app.task(bind=True, trail=True)
def my_task(task: Any, *args, **kwargs) -> None:
    import time
    time.sleep(1000)
    return "my_task"
