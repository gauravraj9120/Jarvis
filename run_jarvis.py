"""Launcher for the J.A.R.V.I.S. Futuristic HUD Application."""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

HOST = os.environ.get("JARVIS_HOST", "127.0.0.1")
PORT = int(os.environ.get("JARVIS_PORT", "8765"))


def _is_port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def _open_browser_when_ready(url: str) -> None:
    time.sleep(1.1)
    try:
        webbrowser.open(url)
    except Exception:
        pass


def main() -> None:
    url = f"http://{HOST}:{PORT}"
    if _is_port_open(HOST, PORT):
        print("=" * 56)
        print(f"  J.A.R.V.I.S. HUD is already online at: {url}")
        print("  Opening HUD in your browser...")
        print("=" * 56)
        if os.environ.get("JARVIS_NO_BROWSER") != "1":
            webbrowser.open(url)
        return

    print("=" * 56)
    print("  J.A.R.V.I.S. — Just A Rather Very Intelligent System")
    print(f"  HUD Interface Online at: {url}")
    print("  Press CTRL+C to shut down the core.")
    print("=" * 56)
    if os.environ.get("JARVIS_NO_BROWSER") != "1":
        threading.Thread(target=_open_browser_when_ready, args=(url,), daemon=True).start()
    uvicorn.run("backend.main:app", host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
