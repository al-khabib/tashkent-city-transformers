import os
import signal
import sys
from typing import Optional


# Support launching from either project root or the server directory.
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from server.app import app
from server.app import close_runtime_resources


def _kill_child_processes() -> None:
    """Best-effort kill of child processes (including possible Ollama subprocesses)."""
    try:
        import subprocess

        output = subprocess.check_output(["pgrep", "-P", str(os.getpid())], text=True).strip()
        if not output:
            return
        for pid_text in output.splitlines():
            pid_text = pid_text.strip()
            if not pid_text:
                continue
            try:
                os.kill(int(pid_text), signal.SIGKILL)
            except ProcessLookupError:
                continue
            except Exception:
                pass
    except Exception:
        # Keep shutdown path robust even if pgrep is unavailable.
        pass


def graceful_shutdown(signum: int, _frame: Optional[object]) -> None:
    print("\nBackend shutting down immediately...", flush=True)
    close_runtime_resources()
    _kill_child_processes()
    # Immediate process exit to avoid waiting for in-flight CPU-bound tasks.
    os._exit(128 + signum)


if __name__ == "__main__":
    import uvicorn

    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)

    try:
        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=8000,
            timeout_graceful_shutdown=0,
        )
        server = uvicorn.Server(config)
        # Keep OS-level signal handling in this module to guarantee Ctrl+C behavior.
        server.install_signal_handlers = lambda: None  # type: ignore[method-assign]
        server.run()
    except KeyboardInterrupt:
        graceful_shutdown(signal.SIGINT, None)
        sys.exit(130)
