"""FastAPI server for the J.A.R.V.I.S. Futuristic HUD."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.assistant import process_command
from backend.storage import (
    BASE_DIR,
    add_task,
    delete_note,
    delete_task,
    get_config,
    list_notes,
    list_tasks,
    save_note,
    update_config,
    update_task,
)
from backend.telemetry import (
    get_active_connections,
    get_system_snapshot,
    get_top_processes,
)
from backend.tools_api import (
    compute_hashes,
    generate_password,
    launch_shortcut,
    list_directory,
    read_file_preview,
    run_dev_command,
)

STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="J.A.R.V.I.S. HUD API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Pydantic Request Models ----------

class TaskCreate(BaseModel):
    title: str
    priority: str = "medium"
    category: str = "General"


class TaskPatch(BaseModel):
    title: str | None = None
    completed: bool | None = None
    priority: str | None = None
    category: str | None = None


class NoteSave(BaseModel):
    id: str | None = None
    title: str
    content: str


class CommandRequest(BaseModel):
    message: str


class ShortcutRequest(BaseModel):
    target: str


class DevExecRequest(BaseModel):
    command: str
    mode: str = "shell"


class HashRequest(BaseModel):
    text: str


class ConfigPatch(BaseModel):
    user_name: str | None = None
    city: str | None = None
    country: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    quote: str | None = None
    voice_enabled: bool | None = None
    voice_rate: float | None = None
    voice_pitch: float | None = None
    wake_word_enabled: bool | None = None
    wake_word: str | None = None
    ai_provider: str | None = None
    ai_model: str | None = None
    ai_api_key: str | None = None
    workspace_root: str | None = None


# ---------- Weather Helper ----------

_WMO_DESCRIPTIONS = {
    0: ("Clear Sky", "sun"),
    1: ("Mainly Clear", "sun"),
    2: ("Partly Cloudy", "cloud-sun"),
    3: ("Overcast", "cloud"),
    45: ("Foggy", "cloud"),
    48: ("Rime Fog", "cloud"),
    51: ("Light Drizzle", "rain"),
    61: ("Light Rain", "rain"),
    63: ("Moderate Rain", "rain"),
    65: ("Heavy Rain", "rain"),
    80: ("Rain Showers", "rain"),
    95: ("Thunderstorm", "storm"),
}


def _geocode_city(city_name: str) -> tuple[float, float] | None:
    """Resolve a city name to (latitude, longitude) using Open-Meteo geocoding."""
    clean = city_name.split(",")[0].strip()
    if not clean:
        return None
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(clean)}&count=1&language=en&format=json"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "JARVIS-HUD/1.0"})
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        results = data.get("results") or []
        if results:
            return (round(float(results[0]["latitude"]), 4), round(float(results[0]["longitude"]), 4))
    except Exception:
        return None
    return None


@app.get("/api/health")
def api_health() -> dict[str, Any]:
    return {"status": "online", "system": "J.A.R.V.I.S."}


@app.get("/api/telemetry")
def api_telemetry() -> dict[str, Any]:
    return get_system_snapshot()


@app.get("/api/weather")
def api_weather() -> dict[str, Any]:
    cfg = get_config()
    lat = cfg.get("latitude", 23.2599)
    lon = cfg.get("longitude", 77.4126)
    city = cfg.get("city", "Bhopal, MP")
    country = cfg.get("country", "India")
    if city.strip().lower() != "bhopal, mp" and lat == 23.2599 and lon == 77.4126:
        coords = _geocode_city(city)
        if coords:
            lat, lon = coords
            update_config({"latitude": lat, "longitude": lon})
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        "&current=temperature_2m,weather_code,wind_speed_10m,relative_humidity_2m"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "JARVIS-HUD/1.0"})
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        cur = data.get("current", {})
        code = int(cur.get("weather_code", 0))
        desc, icon = _WMO_DESCRIPTIONS.get(code, ("Clear Sky", "sun"))
        return {
            "temp_c": round(float(cur.get("temperature_2m", 22))),
            "condition": desc,
            "icon": icon,
            "humidity": cur.get("relative_humidity_2m"),
            "wind_kmh": cur.get("wind_speed_10m"),
            "city": city,
            "country": country,
            "live": True,
        }
    except Exception:
        return {
            "temp_c": 22,
            "condition": "Clear Sky",
            "icon": "sun",
            "humidity": 48,
            "wind_kmh": 8.4,
            "city": city,
            "country": country,
            "live": False,
        }


# ---------- Assistant ----------

@app.post("/api/assistant/command")
def api_assistant_command(body: CommandRequest) -> dict[str, Any]:
    return process_command(body.message)


# ---------- Tasks (Today's Plan) ----------

@app.get("/api/tasks")
def api_list_tasks() -> list[dict[str, Any]]:
    return list_tasks()


@app.post("/api/tasks")
def api_add_task(body: TaskCreate) -> dict[str, Any]:
    if not body.title.strip():
        raise HTTPException(status_code=400, detail="Task title cannot be empty.")
    return add_task(body.title, body.priority, body.category)


@app.patch("/api/tasks/{task_id}")
def api_patch_task(task_id: str, body: TaskPatch) -> dict[str, Any]:
    updated = update_task(
        task_id,
        title=body.title,
        completed=body.completed,
        priority=body.priority,
        category=body.category,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    return updated


@app.delete("/api/tasks/{task_id}")
def api_delete_task(task_id: str) -> dict[str, bool]:
    if not delete_task(task_id):
        raise HTTPException(status_code=404, detail="Task not found.")
    return {"ok": True}


# ---------- Notes ----------

@app.get("/api/notes")
def api_list_notes() -> list[dict[str, Any]]:
    return list_notes()


@app.post("/api/notes")
def api_save_note(body: NoteSave) -> dict[str, Any]:
    return save_note(body.title, body.content, body.id)


@app.delete("/api/notes/{note_id}")
def api_delete_note(note_id: str) -> dict[str, bool]:
    if not delete_note(note_id):
        raise HTTPException(status_code=404, detail="Note not found.")
    return {"ok": True}


# ---------- Shortcuts, Files, Security, Dev ----------

@app.post("/api/shortcuts/launch")
def api_launch_shortcut(body: ShortcutRequest) -> dict[str, Any]:
    return launch_shortcut(body.target)


@app.get("/api/files/list")
def api_files_list(path: str | None = Query(default=None)) -> dict[str, Any]:
    return list_directory(path)


@app.get("/api/files/read")
def api_files_read(path: str = Query(...)) -> dict[str, Any]:
    return read_file_preview(path)


@app.get("/api/security/overview")
def api_security_overview() -> dict[str, Any]:
    return {
        "connections": get_active_connections(limit=25),
        "processes": get_top_processes(limit=18),
    }


@app.get("/api/security/password")
def api_security_password(length: int = Query(default=16), symbols: bool = Query(default=True)) -> dict[str, Any]:
    return generate_password(length=length, symbols=symbols)


@app.post("/api/security/hash")
def api_security_hash(body: HashRequest) -> dict[str, str]:
    return compute_hashes(body.text)


@app.post("/api/dev/exec")
def api_dev_exec(body: DevExecRequest) -> dict[str, Any]:
    return run_dev_command(body.command, mode=body.mode)


# ---------- Config / Settings ----------

@app.get("/api/config")
def api_get_config() -> dict[str, Any]:
    cfg = get_config()
    masked = dict(cfg)
    key = masked.get("ai_api_key", "")
    masked["has_api_key"] = bool(key)
    if key:
        masked["ai_api_key"] = f"{key[:4]}••••{key[-4:]}" if len(key) > 8 else "••••"
    return masked


@app.patch("/api/config")
def api_patch_config(body: ConfigPatch) -> dict[str, Any]:
    current = get_config()
    patch = body.model_dump(exclude_none=True)
    # Don't overwrite actual key with masked placeholder
    if "ai_api_key" in patch and "••••" in str(patch["ai_api_key"]):
        patch.pop("ai_api_key")

    # Auto-geocode when city changes and user left lat/lon unchanged
    if "city" in patch and patch["city"].strip().lower() != str(current.get("city", "")).strip().lower():
        lat_unchanged = patch.get("latitude") is None or patch.get("latitude") == current.get("latitude")
        lon_unchanged = patch.get("longitude") is None or patch.get("longitude") == current.get("longitude")
        if lat_unchanged and lon_unchanged:
            coords = _geocode_city(patch["city"])
            if coords:
                patch["latitude"], patch["longitude"] = coords

    updated = update_config(patch)
    masked = dict(updated)
    key = masked.get("ai_api_key", "")
    masked["has_api_key"] = bool(key)
    if key:
        masked["ai_api_key"] = f"{key[:4]}••••{key[-4:]}" if len(key) > 8 else "••••"
    return masked


# ---------- Static Frontend ----------

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def serve_index() -> FileResponse:
    return FileResponse(str(STATIC_DIR / "index.html"))
