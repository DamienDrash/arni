"""Restart Application Server (Uvicorn)."""
import os
import signal
import subprocess
import time

def kill_old_server():
    print("🔪 Killing old uvicorn processes...")
    try:
        pids = subprocess.check_output(["pgrep", "-f", "uvicorn"]).decode().split()
        for pid in pids:
            os.kill(int(pid), signal.SIGTERM)
    except subprocess.CalledProcessError:
        print("No old uvicorn found.")

def start_server():
    print("🚀 Starting new uvicorn server...")
    with open("uvicorn.log", "a") as log:
        subprocess.Popen(
            ["uvicorn", "app.gateway.main:app", "--host", "0.0.0.0", "--port", "8000"],
            stdout=log,
            stderr=log,
            preexec_fn=os.setpgrp # Detach from parent
        )
    print("✅ Server started in background. Check uvicorn.log")

if __name__ == "__main__":
    kill_old_server()
    time.sleep(2)
    start_server()
