"""Persistent JSON storage for J.A.R.V.I.S. tasks, notes, and configuration."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

_LOCK = threading.Lock()

DEFAULT_CONFIG: dict[str, Any] = {
    "user_name": "Gaurav Kumar",
    "city": "Bhopal, MP",
    "country": "India",
    "latitude": 23.2599,
    "longitude": 77.4126,
    "quote": "Dream Big, Code Bigger...",
    "voice_enabled": True,
    "voice_rate": 1.02,
    "voice_pitch": 0.92,
    "wake_word_enabled": False,
    "wake_word": "hey jarvis",
    "ai_provider": "local",
    "ai_model": "gemini-2.5-flash",
    "ai_api_key": "",
    "workspace_root": str(BASE_DIR),
}

DEFAULT_TASKS: list[dict[str, Any]] = [
    {
        "id": "task-1",
        "title": "Learn FastAPI (Lesson 2)",
        "completed": False,
        "priority": "high",
        "category": "Learning",
        "created_at": "2026-11-27T09:00:00",
    },
    {
        "id": "task-2",
        "title": "Practice Python Interview Qs",
        "completed": False,
        "priority": "medium",
        "category": "Career",
        "created_at": "2026-11-27T09:05:00",
    },
    {
        "id": "task-3",
        "title": "Cyber Security Practice",
        "completed": False,
        "priority": "high",
        "category": "Security",
        "created_at": "2026-11-27T09:10:00",
    },
    {
        "id": "task-4",
        "title": "Build Portfolio Project",
        "completed": False,
        "priority": "medium",
        "category": "Dev",
        "created_at": "2026-11-27T09:15:00",
    },
]

DEFAULT_NOTES: list[dict[str, Any]] = [
    {
        "id": "note-1",
        "title": "J.A.R.V.I.S. Command Tips",
        "content": (
            "Try commands like:\n"
            "- 'What is my CPU and RAM usage?'\n"
            "- 'Open VS Code' or 'Open Terminal'\n"
            "- 'Add task Review FastAPI routers'\n"
            "- 'Search FastAPI middleware docs'\n"
            "- 'Tell me a joke' or 'System report'"
        ),
        "updated_at": "2026-11-27T09:00:00",
    }
]


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path, default: Any) -> Any:
    _ensure_data_dir()
    if not path.exists():
        _write_json(path, default)
        return json.loads(json.dumps(default))
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return json.loads(json.dumps(default))


def _write_json(path: Path, data: Any) -> None:
    _ensure_data_dir()
    tmp_path = path.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    tmp_path.replace(path)


def get_config() -> dict[str, Any]:
    with _LOCK:
        cfg = _read_json(DATA_DIR / "config.json", DEFAULT_CONFIG)
        merged = {**DEFAULT_CONFIG, **cfg}
        return merged


def update_config(patch: dict[str, Any]) -> dict[str, Any]:
    with _LOCK:
        cfg = _read_json(DATA_DIR / "config.json", DEFAULT_CONFIG)
        merged = {**DEFAULT_CONFIG, **cfg}
        for key, value in patch.items():
            if key in DEFAULT_CONFIG and value is not None:
                merged[key] = value
        _write_json(DATA_DIR / "config.json", merged)
        return merged


def list_tasks() -> list[dict[str, Any]]:
    with _LOCK:
        return _read_json(DATA_DIR / "tasks.json", DEFAULT_TASKS)


def add_task(title: str, priority: str = "medium", category: str = "General") -> dict[str, Any]:
    with _LOCK:
        tasks = _read_json(DATA_DIR / "tasks.json", DEFAULT_TASKS)
        task = {
            "id": f"task-{uuid.uuid4().hex[:8]}",
            "title": title.strip(),
            "completed": False,
            "priority": priority,
            "category": category,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        tasks.append(task)
        _write_json(DATA_DIR / "tasks.json", tasks)
        return task


def update_task(task_id: str, **fields: Any) -> dict[str, Any] | None:
    with _LOCK:
        tasks = _read_json(DATA_DIR / "tasks.json", DEFAULT_TASKS)
        for task in tasks:
            if task["id"] == task_id:
                for k, v in fields.items():
                    if v is not None and k in ("title", "completed", "priority", "category"):
                        task[k] = v
                _write_json(DATA_DIR / "tasks.json", tasks)
                return task
        return None


def delete_task(task_id: str) -> bool:
    with _LOCK:
        tasks = _read_json(DATA_DIR / "tasks.json", DEFAULT_TASKS)
        filtered = [t for t in tasks if t["id"] != task_id]
        if len(filtered) == len(tasks):
            return False
        _write_json(DATA_DIR / "tasks.json", filtered)
        return True


def list_notes() -> list[dict[str, Any]]:
    with _LOCK:
        return _read_json(DATA_DIR / "notes.json", DEFAULT_NOTES)


def save_note(title: str, content: str, note_id: str | None = None) -> dict[str, Any]:
    with _LOCK:
        notes = _read_json(DATA_DIR / "notes.json", DEFAULT_NOTES)
        now = datetime.now().isoformat(timespec="seconds")
        if note_id:
            for note in notes:
                if note["id"] == note_id:
                    note["title"] = title.strip() or "Untitled Note"
                    note["content"] = content
                    note["updated_at"] = now
                    _write_json(DATA_DIR / "notes.json", notes)
                    return note
        note = {
            "id": f"note-{uuid.uuid4().hex[:8]}",
            "title": title.strip() or "Untitled Note",
            "content": content,
            "updated_at": now,
        }
        notes.insert(0, note)
        _write_json(DATA_DIR / "notes.json", notes)
        return note


def delete_note(note_id: str) -> bool:
    with _LOCK:
        notes = _read_json(DATA_DIR / "notes.json", DEFAULT_NOTES)
        filtered = [n for n in notes if n["id"] != note_id]
        if len(filtered) == len(notes):
            return False
        _write_json(DATA_DIR / "notes.json", filtered)
        return True
