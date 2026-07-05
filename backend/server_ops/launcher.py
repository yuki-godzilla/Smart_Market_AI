from __future__ import annotations

import argparse
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Sequence
from urllib.error import URLError
from urllib.request import urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOCK_PATH = PROJECT_ROOT / "data" / "ops" / "server_ops" / "streamlit.lock"
STOP_REQUEST_PATH = PROJECT_ROOT / "data" / "ops" / "server_ops" / "streamlit.stop"
HOST = "127.0.0.1"
PORT = 8501
EXIT_ALREADY_RUNNING = 10
EXIT_INTERRUPTED = 130
RESILIENT_RESTART_DELAY_SECONDS = 2.0


class ServerLockUnavailable(RuntimeError):
    pass


def is_port_listening(host: str = HOST, port: int = PORT) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
        client.settimeout(0.25)
        return client.connect_ex((host, port)) == 0


def is_smai_healthy(host: str = HOST, port: int = PORT) -> bool:
    try:
        with urlopen(f"http://{host}:{port}/_stcore/health", timeout=1.0) as response:
            return response.status == 200 and response.read().strip().lower() == b"ok"
    except (OSError, URLError):
        return False


@contextmanager
def server_lock(path: Path = LOCK_PATH) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    acquired = False
    try:
        try:
            handle.seek(0)
            if handle.read(1) == b"":
                handle.seek(0)
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            if sys.platform == "win32":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ServerLockUnavailable from exc
        acquired = True
        yield
    finally:
        if acquired:
            try:
                handle.seek(0)
                if sys.platform == "win32":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        handle.close()


def streamlit_command(browser_address: str) -> list[str]:
    return [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "ui/app.py",
        "--server.address",
        "0.0.0.0",
        "--server.port",
        str(PORT),
        "--server.headless",
        "true",
        "--server.runOnSave",
        "false",
        "--browser.serverAddress",
        browser_address,
    ]


def streamlit_creation_flags(*, resilient: bool) -> int:
    if sys.platform != "win32" or not resilient:
        return 0
    return getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(
        subprocess, "CREATE_NO_WINDOW", 0
    )


def wait_for_streamlit(process: subprocess.Popen[bytes], *, resilient: bool) -> int:
    while True:
        try:
            return process.wait()
        except KeyboardInterrupt:
            if resilient:
                returncode = process.poll()
                if returncode is not None:
                    return returncode
                print(
                    "[SMAI] Ignored a console interrupt in resilient server mode.",
                    file=sys.stderr,
                )
                continue
            print("[SMAI] Console interrupt received; stopping Streamlit.", file=sys.stderr)
            try:
                process.terminate()
            except OSError:
                pass
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            return EXIT_INTERRUPTED


def wait_for_existing_server(timeout_seconds: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if is_smai_healthy():
            return True
        time.sleep(0.25)
    return is_smai_healthy()


def consume_supervisor_stop_request(path: Path = STOP_REQUEST_PATH) -> bool:
    """Consume an explicit request to stop the resilient launcher."""

    try:
        path.unlink()
    except FileNotFoundError:
        return False
    except OSError:
        return False
    return True


def supervise_streamlit(browser_address: str, *, resilient: bool) -> int:
    """Run Streamlit and keep it alive when the always-on policy is enabled."""

    while True:
        process = subprocess.Popen(
            streamlit_command(browser_address),
            cwd=PROJECT_ROOT,
            creationflags=streamlit_creation_flags(resilient=resilient),
        )
        returncode = wait_for_streamlit(process, resilient=resilient)
        if not resilient:
            return returncode
        if consume_supervisor_stop_request():
            print(
                "[SMAI] Streamlit stopped by an explicit service operation; "
                "leaving the resilient launcher.",
                file=sys.stderr,
                flush=True,
            )
            return returncode
        print(
            "[SMAI] Streamlit exited unexpectedly "
            f"(exit={returncode}); restarting in "
            f"{RESILIENT_RESTART_DELAY_SECONDS:g}s.",
            file=sys.stderr,
            flush=True,
        )
        time.sleep(RESILIENT_RESTART_DELAY_SECONDS)


def run_server(
    browser_address: str,
    *,
    maintenance_startup: bool = False,
    resilient: bool = False,
) -> int:
    try:
        lock_context = server_lock()
        with lock_context:
            if is_port_listening():
                if is_smai_healthy():
                    print("[SMAI] SMAI is already running on TCP 8501; reusing it.")
                    print(f"[SMAI] Open http://{browser_address}:{PORT}")
                    return EXIT_ALREADY_RUNNING
                print(
                    "[SMAI] TCP 8501 is already in use, but the listener did not "
                    "answer as SMAI. Stop that process or choose another port.",
                    file=sys.stderr,
                )
                return 2
            if maintenance_startup:
                result = subprocess.run(
                    [sys.executable, "-m", "backend.server_ops.maintenance", "startup"],
                    cwd=PROJECT_ROOT,
                    check=False,
                )
                if result.returncode != 0:
                    print(
                        "[SMAI] Maintenance startup state could not be recorded.",
                        file=sys.stderr,
                    )
                    return 3
            return supervise_streamlit(browser_address, resilient=resilient)
    except ServerLockUnavailable:
        if wait_for_existing_server():
            print("[SMAI] SMAI is already starting or running on TCP 8501.")
            print(f"[SMAI] Open http://{browser_address}:{PORT}")
            return EXIT_ALREADY_RUNNING
        print(
            "[SMAI] Another SMAI launcher owns the startup lock, but TCP 8501 "
            "did not become available.",
            file=sys.stderr,
        )
        return 4


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start one shared SMAI Streamlit server.")
    parser.add_argument("--browser-address", default="localhost")
    parser.add_argument("--maintenance-startup", action="store_true")
    parser.add_argument("--resilient", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    return run_server(
        args.browser_address,
        maintenance_startup=args.maintenance_startup,
        resilient=args.resilient,
    )


if __name__ == "__main__":
    raise SystemExit(main())
