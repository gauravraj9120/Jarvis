"""System tools: file explorer, app launcher, security utilities, and developer console."""

from __future__ import annotations

import hashlib
import os
import secrets
import shutil
import string
import subprocess
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.storage import BASE_DIR, get_config


def _resolve_browse_path(requested: str | None) -> Path:
    cfg = get_config()
    root = Path(cfg.get("workspace_root") or BASE_DIR).resolve()
    if not requested:
        return root
    candidate = Path(requested).resolve()
    if not candidate.exists():
        return root
    return candidate


def list_directory(path_str: str | None = None) -> dict[str, Any]:
    """List files and folders at a local path."""
    target = _resolve_browse_path(path_str)
    if target.is_file():
        target = target.parent

    entries: list[dict[str, Any]] = []
    try:
        items = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        for item in items[:200]:
            try:
                stat = item.stat()
                entries.append(
                    {
                        "name": item.name,
                        "path": str(item),
                        "is_dir": item.is_dir(),
                        "size": 0 if item.is_dir() else stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime).strftime(
                            "%Y-%m-%d %H:%M"
                        ),
                        "ext": item.suffix.lower(),
                    }
                )
            except OSError:
                continue
    except OSError as exc:
        return {"path": str(target), "parent": str(target.parent), "entries": [], "error": str(exc)}

    parent = str(target.parent) if target.parent != target else str(target)
    return {"path": str(target), "parent": parent, "entries": entries}


def read_file_preview(path_str: str, max_bytes: int = 24000) -> dict[str, Any]:
    """Read a text preview of a file."""
    target = Path(path_str).resolve()
    if not target.exists() or not target.is_file():
        return {"ok": False, "error": "File not found."}
    if target.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".exe", ".dll", ".zip"}:
        return {
            "ok": True,
            "name": target.name,
            "path": str(target),
            "binary": True,
            "size": target.stat().st_size,
            "content": f"[Binary file: {target.name} ({target.stat().st_size:,} bytes)]",
        }
    try:
        raw = target.read_bytes()[:max_bytes]
        text = raw.decode("utf-8", errors="replace")
        truncated = target.stat().st_size > max_bytes
        return {
            "ok": True,
            "name": target.name,
            "path": str(target),
            "binary": False,
            "size": target.stat().st_size,
            "truncated": truncated,
            "content": text,
        }
    except OSError as exc:
        return {"ok": False, "error": str(exc)}


def launch_shortcut(target: str) -> dict[str, Any]:
    """Launch a quick shortcut application or URL safely on Windows."""
    key = target.strip().lower()
    creation = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    if key in ("vscode", "code", "vs code"):
        code_exe = shutil.which("code") or shutil.which("code.cmd")
        if code_exe:
            subprocess.Popen([code_exe, str(BASE_DIR)], creationflags=creation)
            return {"ok": True, "message": f"Launched VS Code at {BASE_DIR}."}
        return {"ok": False, "message": "VS Code CLI ('code') was not found in PATH."}

    if key in ("browser", "chrome", "web"):
        webbrowser.open("https://www.google.com")
        return {"ok": True, "message": "Opened default web browser."}

    if key in ("github",):
        webbrowser.open("https://github.com")
        return {"ok": True, "message": "Opened GitHub in browser."}

    if key in ("youtube",):
        webbrowser.open("https://www.youtube.com")
        return {"ok": True, "message": "Opened YouTube in browser."}

    if key in ("terminal", "powershell", "cmd"):
        if sys.platform == "win32":
            wt = shutil.which("wt")
            if wt:
                subprocess.Popen([wt, "-d", str(BASE_DIR)])
            else:
                subprocess.Popen(
                    ["cmd", "/c", "start", "powershell", "-NoExit", "-WorkingDirectory", str(BASE_DIR)]
                )
            return {"ok": True, "message": f"Launched Terminal in {BASE_DIR}."}
        return {"ok": False, "message": "Terminal launch is configured for Windows."}

    if key in ("python", "repl"):
        if sys.platform == "win32":
            subprocess.Popen(["cmd", "/c", "start", "cmd", "/k", sys.executable])
            return {"ok": True, "message": "Launched interactive Python shell."}
        return {"ok": False, "message": "Python launch is configured for Windows."}

    if key in ("explorer", "files_os"):
        if sys.platform == "win32":
            os.startfile(str(BASE_DIR))  # type: ignore[attr-defined]
            return {"ok": True, "message": f"Opened File Explorer at {BASE_DIR}."}

    if key in ("notepad",):
        subprocess.Popen(["notepad.exe"])
        return {"ok": True, "message": "Launched Notepad."}

    if key in ("calc", "calculator"):
        subprocess.Popen(["calc.exe"])
        return {"ok": True, "message": "Launched Calculator."}

    return {"ok": False, "message": f"Unknown shortcut '{target}'."}


def run_dev_command(command: str, mode: str = "shell") -> dict[str, Any]:
    """Execute a developer command or Python snippet inside the workspace."""
    cmd = command.strip()
    if not cmd:
        return {"ok": False, "stdout": "", "stderr": "Command cannot be empty.", "exit_code": 1}

    blocked = ("format ", "del /s", "rd /s", "rmdir /s", "shutdown", "restart-computer")
    lower = cmd.lower()
    if any(token in lower for token in blocked):
        return {
            "ok": False,
            "stdout": "",
            "stderr": "Blocked potentially destructive system command.",
            "exit_code": 1,
        }

    try:
        if mode == "python":
            proc = subprocess.run(
                [sys.executable, "-c", cmd],
                cwd=str(BASE_DIR),
                capture_output=True,
                text=True,
                timeout=12,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        else:
            shell_command = (
                ["powershell", "-NoProfile", "-Command", cmd]
                if sys.platform == "win32"
                else ["/bin/sh", "-lc", cmd]
            )
            proc = subprocess.run(
                shell_command,
                cwd=str(BASE_DIR),
                capture_output=True,
                text=True,
                timeout=12,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        return {
            "ok": proc.returncode == 0,
            "stdout": proc.stdout[:12000],
            "stderr": proc.stderr[:6000],
            "exit_code": proc.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "stdout": "",
            "stderr": "Command timed out after 12 seconds.",
            "exit_code": 124,
        }
    except Exception as exc:
        return {"ok": False, "stdout": "", "stderr": str(exc), "exit_code": 1}


def generate_password(length: int = 16, symbols: bool = True) -> dict[str, Any]:
    """Generate a cryptographically strong password."""
    length = max(8, min(64, length))
    alphabet = string.ascii_letters + string.digits + ("!@#$%^&*()-_=+" if symbols else "")
    pwd = "".join(secrets.choice(alphabet) for _ in range(length))
    return {"password": pwd, "length": length}


def compute_hashes(text: str) -> dict[str, str]:
    """Compute common cryptographic digests for security/dev inspection."""
    data = text.encode("utf-8")
    return {
        "md5": hashlib.md5(data).hexdigest(),
        "sha1": hashlib.sha1(data).hexdigest(),
        "sha256": hashlib.sha256(data).hexdigest(),
        "sha512": hashlib.sha512(data).hexdigest(),
    }


def trigger_media_key(action: str) -> dict[str, Any]:
    """Send Windows virtual media/volume key events safely."""
    if sys.platform != "win32":
        return {"ok": False, "message": "Media keys are only supported on Windows."}

    import ctypes

    vk_map = {
        "volume_up": (0xAF, "Volume increased."),
        "volume_down": (0xAE, "Volume decreased."),
        "mute": (0xAD, "Audio mute toggled."),
        "play_pause": (0xB3, "Toggled media playback."),
        "next_track": (0xB0, "Skipped to next track."),
        "prev_track": (0xB1, "Returned to previous track."),
    }
    entry = vk_map.get(action)
    if not entry:
        return {"ok": False, "message": f"Unknown media action '{action}'."}

    vk, msg = entry
    KEYEVENTF_KEYUP = 0x0002
    steps = 3 if action in ("volume_up", "volume_down") else 1
    for _ in range(steps):
        ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
    return {"ok": True, "message": msg}
