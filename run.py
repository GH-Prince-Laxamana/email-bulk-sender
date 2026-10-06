from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"

if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
    
VENV = ROOT / ".venv"

HOST = "127.0.0.1"
PORT = int(os.environ.get("BULKMAILER_PORT", "8000"))
GUARD_PORT = PORT + 1


def venv_python() -> Path:
    if os.name == "nt":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def ensure_venv() -> None:
    python = venv_python()

    if not python.exists():
        print("Creating virtual environment...")
        subprocess.check_call(
            [sys.executable, "-m", "venv", str(VENV)],
            cwd=ROOT,
        )

    subprocess.check_call(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "-r",
            str(ROOT / "requirements.txt"),
        ],
        cwd=ROOT,
    )

    if Path(sys.executable).resolve() != python.resolve():
        os.execv(str(python), [str(python), str(__file__), *sys.argv[1:]])


class SingleInstanceGuard:
    def __init__(self, port: int) -> None:
        self._port = port
        self._socket: socket.socket | None = None

    def acquire(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)

        try:
            sock.bind((HOST, self._port))
            sock.listen(1)
        except OSError as exc:
            sock.close()
            raise RuntimeError(
                "BulkMailer is already running, or its single-instance "
                f"guard port {self._port} is unavailable."
            ) from exc

        self._socket = sock

    def release(self) -> None:
        if self._socket is not None:
            self._socket.close()
            self._socket = None


def run() -> None:
    from app.api.app import create_app
    from app.config import data_dir, database_path
    from app.services.settings import SettingsService
    from app.storage.db import connect
    from app.storage.migrations import migrate
    from app.storage.secret_store import default_secret_store

    db_path = database_path()

    conn = connect(db_path)
    try:
        migrate(conn, db_path)
        from app.storage.repo import recover_after_crash

        recovered_recipients, paused_campaigns = recover_after_crash(conn)
    finally:
        conn.close()

    secret_store = default_secret_store(data_dir())
    settings_service = SettingsService(secret_store)

    token = __import__("secrets").token_urlsafe(32)

    app = create_app(
        token,
        settings_service,
    )

    guard = SingleInstanceGuard(GUARD_PORT)
    guard.acquire()

    browser_url = f"http://{HOST}:{PORT}/#token={token}"

    def open_browser_when_ready() -> None:
        for _ in range(100):
            try:
                with socket.create_connection(
                    (HOST, PORT),
                    timeout=0.2,
                ):
                    webbrowser.open(browser_url)
                    return
            except OSError:
                time.sleep(0.1)

    threading.Thread(
        target=open_browser_when_ready,
        name="browser-opener",
        daemon=True,
    ).start()

    print(f"BulkMailer running at http://{HOST}:{PORT}")
    if recovered_recipients or paused_campaigns:
        print(
            f"Recovered {recovered_recipients} interrupted recipient(s) "
            f"and paused {paused_campaigns} campaign(s)."
        )

    try:
        import uvicorn

        config = uvicorn.Config(
            app,
            host=HOST,
            port=PORT,
            log_level="info",
        )
        server = uvicorn.Server(config)
        server.run()
    finally:
        guard.release()


if __name__ == "__main__":
    try:
        ensure_venv()
        run()
    except KeyboardInterrupt:
        print("\nBulkMailer stopped.")
    except Exception as exc:
        print(f"BulkMailer could not start: {exc}", file=sys.stderr)
        raise
