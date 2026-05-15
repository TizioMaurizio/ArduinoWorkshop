"""Auto-restart wrapper for visual_servo.py.

Watches the script file for modifications and restarts the subprocess
automatically.  Pass all visual_servo.py arguments after `--`.

Usage:
    python scripts/watch_servo.py -- --printer-url http://127.0.0.1:8765 ...
"""

import os
import sys
import signal
import subprocess
import time

SCRIPT = os.path.join(os.path.dirname(__file__), "visual_servo.py")
POLL_INTERVAL = 1.0  # seconds


def main():
    # Everything after "--" is forwarded to visual_servo.py
    if "--" in sys.argv:
        idx = sys.argv.index("--")
        child_args = sys.argv[idx + 1:]
    else:
        child_args = sys.argv[1:]

    cmd = [sys.executable, SCRIPT] + child_args
    last_mtime = os.path.getmtime(SCRIPT)
    proc = None

    def start():
        nonlocal proc
        print(f"\n{'='*60}")
        print(f"[watcher] Starting visual_servo.py  (mtime={time.ctime(last_mtime)})")
        print(f"{'='*60}\n", flush=True)
        proc = subprocess.Popen(cmd)

    def stop():
        nonlocal proc
        if proc and proc.poll() is None:
            print(f"\n[watcher] Stopping visual_servo.py (pid={proc.pid})...", flush=True)
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            print("[watcher] Stopped.", flush=True)
        proc = None

    start()

    try:
        while True:
            time.sleep(POLL_INTERVAL)
            try:
                mtime = os.path.getmtime(SCRIPT)
            except OSError:
                continue
            if mtime != last_mtime:
                last_mtime = mtime
                # Quick syntax check before restarting
                check = subprocess.run(
                    [sys.executable, "-c",
                     f"import ast; ast.parse(open(r'{SCRIPT}', encoding='utf-8').read()); print('Syntax OK')"],
                    capture_output=True, text=True
                )
                if check.returncode != 0:
                    print(f"\n[watcher] Syntax error — NOT restarting:\n{check.stderr}", flush=True)
                    continue
                print(f"\n[watcher] File changed — restarting...", flush=True)
                stop()
                start()
            # If child crashed, restart
            if proc and proc.poll() is not None:
                print(f"\n[watcher] Process exited (code={proc.returncode}) — restarting in 2s...", flush=True)
                time.sleep(2)
                last_mtime = os.path.getmtime(SCRIPT)
                start()
    except KeyboardInterrupt:
        print("\n[watcher] Ctrl+C — shutting down.", flush=True)
        stop()


if __name__ == "__main__":
    main()
