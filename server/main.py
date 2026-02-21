import os
import signal
import sys


# Support launching from either project root or the server directory.
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from server.app import app


def kill_now(sig, frame):
    print("\n⚡ Force-killing Tashkent Grid Backend...")
    os._exit(0)


if __name__ == "__main__":
    import uvicorn

    signal.signal(signal.SIGINT, kill_now)
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        workers=1,
        timeout_graceful_shutdown=0,
    )
