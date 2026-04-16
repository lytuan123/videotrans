from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import time
from pathlib import Path


def app_root() -> Path:
    return Path(__file__).resolve().parents[2]


def app_path() -> Path:
    return app_root() / "src" / "videotransdub" / "app.py"


def build_streamlit_command(port: int = 8501) -> list[str]:
    return [
        "streamlit",
        "run",
        str(app_path()),
        "--server.port",
        str(port),
        "--server.headless",
        "true",
        "--server.enableCORS",
        "false",
        "--server.enableXsrfProtection",
        "false",
    ]


def build_streamlit_env(base_env: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(base_env or os.environ)
    src_path = str(app_root() / "src")
    existing = env.get("PYTHONPATH", "")
    if existing:
        env["PYTHONPATH"] = os.pathsep.join([src_path, existing])
    else:
        env["PYTHONPATH"] = src_path
    return env


def start_streamlit(port: int = 8501) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        build_streamlit_command(port),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(app_root()),
        env=build_streamlit_env(),
    )


def create_cloudflare_tunnel(port: int = 8501, attempts: int = 30, delay_seconds: float = 1.0) -> str | None:
    if not shutil.which("cloudflared"):
        return None

    proc = subprocess.Popen(
        ["cloudflared", "tunnel", "--url", f"http://localhost:{port}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(app_root()),
    )
    for _ in range(attempts):
        time.sleep(delay_seconds)
        line = proc.stderr.readline().decode("utf-8", errors="ignore")
        match = re.search(r"(https://[a-z0-9-]+\.trycloudflare\.com)", line)
        if match:
            return match.group(1)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch VideoTransDub Streamlit UI")
    parser.add_argument("--port", type=int, default=int(os.environ.get("VIDEOTRANSDUB_PORT", "8501")))
    args = parser.parse_args()
    command = build_streamlit_command(args.port)
    os.execvpe(command[0], command, build_streamlit_env())


if __name__ == "__main__":
    raise SystemExit(main())
