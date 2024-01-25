import tempfile
import argparse
import socket
from typing import Any
from worker import my_task, app
import time
import psutil
from pathlib import Path
import subprocess
import subprocess
import psutil



def list_tasks(hostname: str):
    print(f"Retrieving stats for node {hostname=}...")
    inspector = app.control.inspect(destination=[hostname])  # type: ignore[attr-defined]

    task_states = [
        "active",
        "scheduled",
        "reserved",
        "revoked",
    ]

    for state in task_states:
        print(f"Retrieving {state} tasks...")

        if not hasattr(inspector, state):
            raise ValueError(f"Unknown state {state}")

        tasks: dict[str, Any] = getattr(inspector, state)()

        if not tasks:
            continue

        for task in tasks[hostname]:
            print(f"\t {task['name']}: {task}")


def start_celery(stdout_filename: Path) -> subprocess.Popen:
    worker_file = Path(__file__).parent
    command = f"cd {worker_file} && poetry run celery -A worker worker --without-mingle --without-gossip --without-heartbeat --loglevel=debug --concurrency=1 --pool=prefork > {str(stdout_filename)} 2>&1"

    print(command)
    p = subprocess.Popen(command, shell=True)

    return p

def purge_celery_queue(hostname: str):
    print(f"Purging celery queue")
    inspector = app.control.purge()


def start_redis_cli_monitor(stdout_filename: str) -> str:

    
    get_redis_containers = subprocess.run(
        "docker ps | grep redis", shell=True, text=True, capture_output=True
    )

    if get_redis_containers.returncode != 0:
        raise ValueError("Could not find redis container")
    
    redis_container_id = get_redis_containers.stdout.split()[0]


    print("Starting redis-cli monitor")
    command = (
        f"docker exec -t {redis_container_id} redis-cli MONITOR > {str(stdout_filename)} 2>&1"
    )
    p = subprocess.Popen(command, shell=True)

    return p


def sleep_then_kill(pid: int, sleep_time: int):
    print(
        f"Waiting for {sleep_time} seconds before sending SIGKILL to process {pid}...",
        end="",
        flush=True,
    )
    time.sleep(sleep_time)
    psutil.Process(pid).kill()
    print(f"Sent SIGKILL")


def sleep_then_send_signal(pid: int, sleep_time: int, signal_name: str):
    signal_name_to_number = {
        "SIGTERM": 15,
        "SIGKILL": 9,
        "SIGQUIT": 3,
    }
    print(
        f"Waiting for {sleep_time} seconds before sending {signal_name} to process {pid}...",
        end="",
        flush=True,
    )
    time.sleep(sleep_time)
    psutil.Process(pid).send_signal(signal_name_to_number[signal_name])
    print(f"Sent {signal_name}")

def verify_no_other_celery_process_is_running():
    # use pgrep to find celery processes
    celery_processes = subprocess.run(
        "pgrep -a celery", shell=True, text=True, capture_output=True
    )

    if celery_processes.returncode != 1:
        entries = celery_processes.stdout.splitlines()
        assert len(entries) == 0, f"Found {len(entries)} celery processes running. Please kill them and try again."


def kill_remaining_celery_processes():
    print("Killing remaining celery processes")
    command = "pkill -9 'celery'"
    p = subprocess.run(command, shell=True, text=True, capture_output=True)
    print(p.stdout)
    print(p.stderr)

def main():

    argsparser = argparse.ArgumentParser()
    argsparser.add_argument("--signal", type=str)

    args = argsparser.parse_args()

    if not args.signal:
        raise ValueError("Please provide a signal to send to the celery process")
    
    signal_name: str = args.signal

    verify_no_other_celery_process_is_running()
    tempdir = tempfile.mkdtemp()
    celery_stdout = Path(tempdir) / "celery_worker_stdout.txt"
    redis_cli_stdout = Path(tempdir) / "redis_cli_stdout.txt"

    hostname, celery_parent_pid = start_celery_process(celery_stdout)

    start_redis_cli_monitor(redis_cli_stdout)

    my_task.delay()

    time.sleep(5)

    list_tasks(hostname)

    sleep_then_send_signal(celery_parent_pid, 10, signal_name.upper())

    # Wait for stdout to be written to file
    time.sleep(5)

    print(f"Celery stdout:\n {Path(celery_stdout).read_text()}")
    print(f"Redis-cli stdout:\n {Path(redis_cli_stdout).read_text()}")

    list_tasks(hostname)

    # Need to kill celery processes for the purge command to run successfully
    # See https://github.com/celery/celery/discussions/7168
    kill_remaining_celery_processes()
    purge_celery_queue(hostname)

def start_celery_process(celery_stdout: str):
    print("Starting celery worker process")
    hostname = "celery@" + socket.gethostname()

    poetry_process = start_celery(stdout_filename=celery_stdout)

    # Sleep to allow celery to start and fork itself as a child process
    time.sleep(3)


    [celery_parent_process] = psutil.Process(poetry_process.pid).children(
        recursive=False
    )
    [celery_child_process] = psutil.Process(celery_parent_process.pid).children(
        recursive=False
    )

    print("Celery parent process pid: ", celery_parent_process.pid)
    print("Celery child process pid: ", celery_child_process.pid)
    return hostname , celery_parent_process.pid


if __name__ == "__main__":
    main()
