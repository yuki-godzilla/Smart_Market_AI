from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Mapping, Sequence
from urllib.error import URLError
from urllib.request import urlopen

from backend.server_ops.maintenance import SERVICE_INTENT_PATH, read_service_intent
from backend.server_ops.network import (
    DEFAULT_MAIN_APPLICATION_PORT,
    main_application_settings,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOCK_PATH = PROJECT_ROOT / "data" / "ops" / "server_ops" / "streamlit.lock"
STOP_REQUEST_PATH = PROJECT_ROOT / "data" / "ops" / "server_ops" / "streamlit.stop"
HOST = "127.0.0.1"
PORT = DEFAULT_MAIN_APPLICATION_PORT
EXIT_ALREADY_RUNNING = 10
EXIT_INTERRUPTED = 130
RESILIENT_RESTART_DELAY_SECONDS = 2.0
RESILIENT_RESTART_MAX_DELAY_SECONDS = 60.0
RESILIENT_RESTART_STABLE_SECONDS = 300.0
NUMERICAL_THREAD_ENV_DEFAULTS = {
    "OPENBLAS_NUM_THREADS": "1",
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_MAX_THREADS": "4",
}


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


def streamlit_command(browser_address: str, *, port: int = PORT) -> list[str]:
    return [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "ui/app.py",
        "--server.address",
        "0.0.0.0",
        "--server.port",
        str(port),
        "--server.headless",
        "true",
        "--server.runOnSave",
        "false",
        "--browser.serverAddress",
        browser_address,
    ]


def streamlit_creation_flags(*, resilient: bool, visible_console: bool = False) -> int:
    if sys.platform != "win32" or not resilient:
        return 0
    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    if not visible_console:
        flags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return flags


def optimized_child_environment(
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Bound nested numerical pools while preserving explicit operator overrides."""

    child_environment = dict(os.environ if environ is None else environ)
    for name, value in NUMERICAL_THREAD_ENV_DEFAULTS.items():
        child_environment.setdefault(name, value)
    return child_environment


def resilient_restart_delay(consecutive_failures: int) -> float:
    """Return a bounded exponential delay for repeated unexpected exits."""

    exponent = max(0, consecutive_failures)
    return min(
        RESILIENT_RESTART_MAX_DELAY_SECONDS,
        RESILIENT_RESTART_DELAY_SECONDS * (2**exponent),
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


def wait_for_existing_server(
    timeout_seconds: float = 30.0,
    *,
    port: int = PORT,
) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if is_smai_healthy(port=port):
            return True
        time.sleep(0.25)
    return is_smai_healthy(port=port)


def consume_supervisor_stop_request(path: Path = STOP_REQUEST_PATH) -> bool:
    """Consume an explicit request to stop the resilient launcher."""

    try:
        path.unlink()
    except FileNotFoundError:
        return False
    except OSError:
        return False
    return True


def should_leave_resilient_launcher(
    *,
    stop_path: Path = STOP_REQUEST_PATH,
    intent_path: Path = SERVICE_INTENT_PATH,
) -> bool:
    """Return true when a stop/restart intent must suppress auto-restart."""

    request_consumed = consume_supervisor_stop_request(stop_path)
    intent = read_service_intent(intent_path)
    if intent is None:
        return request_consumed
    mode = intent.get("mode")
    status = intent.get("status")
    if mode == "unexpected_exit":
        return False
    if mode in {"manual_stop", "maintenance_restart"} and status in {
        "requested",
        "draining",
        "timed_out",
    }:
        return True
    # Unknown intent is fail-closed: leave the launcher stopped for inspection.
    return mode == "unknown" or status == "unknown" or request_consumed


def supervise_streamlit(
    browser_address: str,
    *,
    resilient: bool,
    visible_console: bool = False,
    port: int = PORT,
) -> int:
    """Run Streamlit and keep it alive when the always-on policy is enabled."""

    consecutive_failures = 0
    while True:
        started_at = time.monotonic()
        process = subprocess.Popen(
            streamlit_command(browser_address, port=port),
            cwd=PROJECT_ROOT,
            creationflags=streamlit_creation_flags(
                resilient=resilient,
                visible_console=visible_console,
            ),
            env=optimized_child_environment(),
        )
        returncode = wait_for_streamlit(process, resilient=resilient)
        if not resilient:
            return returncode
        if should_leave_resilient_launcher():
            print(
                "[SMAI] Streamlit stopped by an explicit service operation; "
                "leaving the resilient launcher.",
                file=sys.stderr,
                flush=True,
            )
            return returncode
        runtime_seconds = max(0.0, time.monotonic() - started_at)
        if runtime_seconds >= RESILIENT_RESTART_STABLE_SECONDS:
            consecutive_failures = 0
        delay_seconds = resilient_restart_delay(consecutive_failures)
        consecutive_failures += 1
        print(
            "[SMAI] Streamlit exited unexpectedly "
            f"(exit={returncode}); restarting in "
            f"{delay_seconds:g}s.",
            file=sys.stderr,
            flush=True,
        )
        time.sleep(delay_seconds)


def run_server(
    browser_address: str,
    *,
    maintenance_startup: bool = False,
    resilient: bool = False,
    visible_console: bool = False,
    port: int | None = None,
) -> int:
    resolved_port = port if port is not None else main_application_settings().port
    try:
        lock_context = server_lock()
        with lock_context:
            if is_port_listening(port=resolved_port):
                if is_smai_healthy(port=resolved_port):
                    print("[SMAI] SMAI is already running on " f"TCP {resolved_port}; reusing it.")
                    print(f"[SMAI] Open http://{browser_address}:{resolved_port}")
                    return EXIT_ALREADY_RUNNING
                print(
                    f"[SMAI] TCP {resolved_port} is already in use, but the listener did not "
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
            return supervise_streamlit(
                browser_address,
                resilient=resilient,
                visible_console=visible_console,
                port=resolved_port,
            )
    except ServerLockUnavailable:
        if wait_for_existing_server(port=resolved_port):
            print(f"[SMAI] SMAI is already starting or running on TCP {resolved_port}.")
            print(f"[SMAI] Open http://{browser_address}:{resolved_port}")
            return EXIT_ALREADY_RUNNING
        print(
            f"[SMAI] Another SMAI launcher owns the startup lock, but TCP {resolved_port} "
            "did not become available.",
            file=sys.stderr,
        )
        return 4


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start one shared SMAI Streamlit server.")
    parser.add_argument("--browser-address", default="localhost")
    parser.add_argument("--maintenance-startup", action="store_true")
    parser.add_argument("--resilient", action="store_true")
    parser.add_argument(
        "--visible-console",
        action="store_true",
        help="Keep the Windows Streamlit child attached to this console.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    return run_server(
        args.browser_address,
        maintenance_startup=args.maintenance_startup,
        resilient=args.resilient,
        visible_console=args.visible_console,
    )


if __name__ == "__main__":
    raise SystemExit(main())
