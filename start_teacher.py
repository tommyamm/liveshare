import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable
BRIDGE_URL = "http://127.0.0.1:8765/health"
EDITOR_URL = "http://127.0.0.1:8000/api/session"


def wait_for_url(url: str, timeout_seconds: float) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=0.5) as response:
                if response.status < 500:
                    return True
        except Exception:
            time.sleep(0.2)
    return False


def main() -> None:
    bridge_process = subprocess.Popen([PYTHON, "sync_client.py"], cwd=ROOT)
    server_process = subprocess.Popen([PYTHON, "sync_server.py"], cwd=ROOT)

    try:
        bridge_ready = wait_for_url(BRIDGE_URL, 8)
        editor_ready = wait_for_url(EDITOR_URL, 8)

        if not bridge_ready or not editor_ready:
            print("Startup did not finish cleanly. Check the windows above.")
        else:
            print("Teacher mode is ready.")
            print("Opening the local editor in your browser...")
            webbrowser.open("http://127.0.0.1:8000")

        print("Press Ctrl+C to stop the teacher session.")
        while True:
            if bridge_process.poll() is not None or server_process.poll() is not None:
                print("One of the background processes stopped. Closing session.")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping teacher session...")
    finally:
        for process in (bridge_process, server_process):
            if process.poll() is None:
                process.terminate()
        for process in (bridge_process, server_process):
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    main()
