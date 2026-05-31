"""Launcher that starts camera, backend, and servo as child processes.

All children are killed when this process exits (Ctrl+C, window close, or crash).
Uses a Windows Job Object so that even grandchildren are terminated.
"""

import os
import sys
import signal
import subprocess
import time
import ctypes
import ctypes.wintypes

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPTS_DIR)

# ── Windows Job Object ──────────────────────────────────────────────────
# Assign all child processes to a Job Object configured with
# JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE. When this process exits (for any
# reason), the OS closes the job handle and kills every process in the job.

kernel32 = ctypes.windll.kernel32

JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
JobObjectExtendedLimitInformation = 9
CREATE_SUSPENDED = 0x00000004
PROCESS_SET_QUOTA = 0x0100
PROCESS_TERMINATE = 0x0001


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [("ReadOperationCount", ctypes.c_ulonglong),
                ("WriteOperationCount", ctypes.c_ulonglong),
                ("OtherOperationCount", ctypes.c_ulonglong),
                ("ReadTransferCount", ctypes.c_ulonglong),
                ("WriteTransferCount", ctypes.c_ulonglong),
                ("OtherTransferCount", ctypes.c_ulonglong)]


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64),
                ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", ctypes.wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", ctypes.wintypes.DWORD),
                ("Affinity", ctypes.POINTER(ctypes.c_ulong)),
                ("PriorityClass", ctypes.wintypes.DWORD),
                ("SchedulingClass", ctypes.wintypes.DWORD)]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t)]


def create_job_object():
    """Create a Windows Job Object that kills children on close."""
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        return None

    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE

    kernel32.SetInformationJobObject(
        job,
        JobObjectExtendedLimitInformation,
        ctypes.byref(info),
        ctypes.sizeof(info),
    )
    return job


def assign_to_job(job, proc):
    """Assign a subprocess.Popen process to the job object."""
    handle = kernel32.OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, proc.pid)
    if handle:
        kernel32.AssignProcessToJobObject(job, handle)
        kernel32.CloseHandle(handle)


# ── Process management ──────────────────────────────────────────────────

children: list[subprocess.Popen] = []


def kill_children():
    """Terminate all child processes."""
    for p in reversed(children):
        if p.poll() is None:
            try:
                p.terminate()
                p.wait(timeout=3)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
    children.clear()


def main():
    os.chdir(PROJECT_DIR)
    python = sys.executable

    mock_mode = "--mock" in sys.argv[1:]

    job = create_job_object()

    print("=" * 60)
    print("  Printer Tracker — Starting all services")
    print("=" * 60)
    print()

    # 1. Camera server
    print("[1/3] Starting camera server on port 8766...")
    cam = subprocess.Popen(
        [python, "scripts/camera_server.py", "--camera", "0", "--port", "8766"],
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
    )
    children.append(cam)
    if job:
        assign_to_job(job, cam)
    time.sleep(2)

    # 2. Printer backend
    backend_flag = "--mock" if mock_mode else "--auto"
    print(f"[2/3] Starting printer backend on port 8765 ({backend_flag})...")
    backend = subprocess.Popen(
        [python, "-m", "backend.main", backend_flag],
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
    )
    children.append(backend)
    if job:
        assign_to_job(job, backend)
    time.sleep(6)

    # 3. Visual servo watcher (foreground — stdout/stderr pass through)
    servo_args = [
        python, "scripts/watch_servo.py", "--",
        "--printer-url", "http://127.0.0.1:8765",
        "--camera-url", "http://127.0.0.1:8766",
        "--step", "1.0",
        "--save-frames",
        "--timeout", "600",
        "--viz-port", "8767",
        "--z-height", "10",
    ]

    print("[3/3] Starting visual servo watcher on port 8767...")
    print()
    print("  Visualization:  http://127.0.0.1:8767")
    print("  Digital Twin:   http://127.0.0.1:8767/twin")
    print("  Camera feed:    http://127.0.0.1:8766")
    print()
    print("  Press Ctrl+C to stop all services.")
    print("=" * 60)
    print()

    servo = subprocess.Popen(servo_args)
    children.append(servo)
    if job:
        assign_to_job(job, servo)

    try:
        servo.wait()
    except KeyboardInterrupt:
        print("\n[launcher] Ctrl+C — shutting down all services...")
    finally:
        kill_children()
        if job:
            kernel32.CloseHandle(job)
        print("[launcher] All services stopped.")


if __name__ == "__main__":
    # Handle Ctrl+C gracefully
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    try:
        main()
    except KeyboardInterrupt:
        kill_children()
