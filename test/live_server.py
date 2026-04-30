import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parent.parent


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class LiveServer:
    def __init__(
        self,
        startup_timeout: float = 20.0,
        health_timeout: float = 1.0,
        extra_env: dict[str, str] | None = None,
    ) -> None:
        self.port = find_free_port()
        self.base_url = f"http://127.0.0.1:{self.port}"
        self.process: subprocess.Popen[str] | None = None
        self._startup_timeout = startup_timeout
        self._health_timeout = health_timeout
        self._extra_env = extra_env or {}

    def start(self) -> None:
        command = [
            sys.executable,
            "-m",
            "uvicorn",
            "api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(self.port),
            "--log-level",
            "warning",
        ]
        self.process = subprocess.Popen(
            command,
            cwd=str(ROOT),
            env={**os.environ, **self._extra_env},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        timeout_at = time.time() + self._startup_timeout
        with httpx.Client(timeout=self._health_timeout) as client:
            while time.time() < timeout_at:
                if self.process.poll() is not None:
                    stdout, stderr = self.process.communicate(timeout=2)
                    raise RuntimeError(
                        f"Uvicorn exited early with code {self.process.returncode}\n"
                        f"STDOUT:\n{stdout}\nSTDERR:\n{stderr}"
                    )

                try:
                    response = client.get(f"{self.base_url}/api/health")
                    if response.status_code == 200:
                        return
                except Exception:
                    pass

                time.sleep(0.15)

        self.stop()
        raise TimeoutError("Timed out waiting for FastAPI server to become healthy")

    def stop(self) -> None:
        if self.process is None:
            return

        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)

        if self.process.stdout:
            self.process.stdout.close()
        if self.process.stderr:
            self.process.stderr.close()

        self.process = None
