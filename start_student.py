import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable
BRIDGE_URL = "http://127.0.0.1:8765/health"


def normalize_teacher_url(raw_value: str) -> str:
    value = raw_value.strip()
    if not value:
        raise ValueError("Teacher host is required")
    if value.startswith("http://") or value.startswith("https://"):
        return value
    if ":" in value or "/" in value:
        return f"http://{value}"
    return f"http://{value}:8000"


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
    teacher_input = sys.argv[1] if len(sys.argv) > 1 else input("Teacher IP or URL: ")
    teacher_url = normalize_teacher_url(teacher_input)

    bridge_process = subprocess.Popen([PYTHON, "sync_client.py"], cwd=ROOT)

    try:
        bridge_ready = wait_for_url(BRIDGE_URL, 8)
        if not bridge_ready:
            print("Local bridge did not start cleanly. Check the terminal output.")
        else:
            print("Student mode is ready.")
            print(f"Opening {teacher_url}")
            webbrowser.open(teacher_url)

        print("Press Ctrl+C to stop the student session.")
        while True:
            if bridge_process.poll() is not None:
                print("The local bridge stopped. Closing session.")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping student session...")
    finally:
        if bridge_process.poll() is None:
            bridge_process.terminate()
        try:
            bridge_process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            bridge_process.kill()


if __name__ == "__main__":
    main()
