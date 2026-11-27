"""J.A.R.V.I.S. natural-language command router & optional LLM bridge."""

from __future__ import annotations

import ast
import json
import operator
import re
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime
from typing import Any

from backend.storage import add_task, get_config, list_tasks, update_task
from backend.telemetry import get_system_snapshot
from backend.tools_api import launch_shortcut, trigger_media_key

_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval_math(expr: str) -> float | None:
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        return None

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_OPS:
            return float(_SAFE_OPS[type(node.op)](_eval(node.left), _eval(node.right)))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_OPS:
            return float(_SAFE_OPS[type(node.op)](_eval(node.operand)))
        raise ValueError("Unsupported expression")

    try:
        return _eval(tree)
    except Exception:
        return None


def _call_optional_llm(message: str, cfg: dict[str, Any]) -> str | None:
    api_key = (cfg.get("ai_api_key") or "").strip()
    provider = (cfg.get("ai_provider") or "local").lower()
    if not api_key or provider == "local":
        return None

    user_name = cfg.get("user_name", "Gaurav Kumar")
    system_prompt = (
        f"You are J.A.R.V.I.S., a futuristic, concise, witty AI assistant serving {user_name}. "
        "Keep answers crisp (2-4 sentences unless code is asked)."
    )

    try:
        if provider == "gemini":
            model = cfg.get("ai_model") or "gemini-2.5-flash"
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{urllib.parse.quote(model)}:generateContent?key={urllib.parse.quote(api_key)}"
            )
            payload = {
                "contents": [
                    {"role": "user", "parts": [{"text": f"{system_prompt}\n\nUser: {message}"}]}
                ]
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            candidates = data.get("candidates") or []
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "").strip()
        elif provider == "openai":
            model = cfg.get("ai_model") or "gpt-4o-mini"
            url = "https://api.openai.com/v1/chat/completions"
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message},
                ],
                "max_tokens": 350,
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            choices = data.get("choices") or []
            if choices:
                return choices[0]["message"]["content"].strip()
    except (urllib.error.URLError, KeyError, IndexError, json.JSONDecodeError):
        return None
    return None


def process_command(raw_message: str) -> dict[str, Any]:
    """Process a user query or command and return reply + optional UI action."""
    msg = raw_message.strip()
    lower = msg.lower()
    cfg = get_config()
    name = cfg.get("user_name", "Gaurav Kumar")
    first_name = name.split()[0] if name else "Sir"

    # Strip wake word prefix if spoken
    wake_prefix = (cfg.get("wake_word") or "hey jarvis").lower()
    for prefix in (wake_prefix, "hey jarvis", "ok jarvis", "jarvis"):
        if lower.startswith(prefix):
            msg = msg[len(prefix) :].lstrip(" ,:.")
            lower = msg.lower()
            break

    if not msg:
        return {
            "reply": f"Yes, {first_name}? I am listening.",
            "action": None,
        }

    # Voice sleep / stop passive listening
    if any(k in lower for k in ("stop listening", "go to sleep", "sleep mode", "standby mode")):
        return {
            "reply": f"Entering standby mode, {first_name}. Click the microphone whenever you need me.",
            "action": {"type": "sleep_mic"},
        }

    # Media & Volume automation
    if any(k in lower for k in ("volume up", "increase volume", "awaz badhao", "volume badhao")):
        res = trigger_media_key("volume_up")
        return {"reply": res["message"], "action": None}
    if any(k in lower for k in ("volume down", "decrease volume", "awaz kam", "volume kam")):
        res = trigger_media_key("volume_down")
        return {"reply": res["message"], "action": None}
    if any(k in lower for k in ("mute", "unmute", "silent")):
        res = trigger_media_key("mute")
        return {"reply": res["message"], "action": None}
    if lower in {"pause", "resume", "play pause", "pause music", "resume music"}:
        res = trigger_media_key("play_pause")
        return {"reply": res["message"], "action": None}
    if any(k in lower for k in ("next song", "next track", "skip song")):
        res = trigger_media_key("next_track")
        return {"reply": res["message"], "action": None}

    # 1. Greetings & identity
    if lower in {
        "hi",
        "hello",
        "hey",
        "namaste",
        "good morning",
        "good afternoon",
        "good evening",
        "kaise ho",
        "kya haal hai",
        "how are you",
    }:
        hour = datetime.now().hour
        greet = "Good Morning" if hour < 12 else ("Good Afternoon" if hour < 17 else "Good Evening")
        return {
            "reply": f"{greet}, {name}. All core systems are online and running smoothly. How may I assist you?",
            "action": None,
        }

    if "who are you" in lower or "what is jarvis" in lower:
        return {
            "reply": (
                "I am J.A.R.V.I.S. — Just A Rather Very Intelligent System, "
                f"custom-engineered for {name}. I monitor telemetry, launch tools, manage your plan, and execute commands."
            ),
            "action": None,
        }

    # 2. Time & Date
    if re.search(r"\b(time|clock)\b", lower) and "uptime" not in lower:
        now = datetime.now()
        return {
            "reply": f"The current time is {now.strftime('%I:%M %p')} on {now.strftime('%A, %d %b %Y')}.",
            "action": None,
        }
    if re.search(r"\b(date|today|day)\b", lower) and "plan" not in lower and "task" not in lower:
        now = datetime.now()
        return {"reply": f"Today is {now.strftime('%A, %d %B %Y')}.", "action": None}

    # 3. System telemetry diagnostics
    if any(k in lower for k in ("system status", "cpu", "ram", "memory", "disk", "telemetry", "diagnostics", "uptime")):
        snap = get_system_snapshot()
        return {
            "reply": (
                f"System Diagnostics for {snap['host']['hostname']}: "
                f"CPU at {snap['cpu']['percent']}%, RAM at {snap['ram']['percent']}% "
                f"({snap['ram']['used_gb']}/{snap['ram']['total_gb']} GB), "
                f"Disk ({snap['disk']['drive']}) at {snap['disk']['percent']}%, "
                f"and uptime is {snap['host']['uptime']}."
            ),
            "action": None,
        }

    # 4. Navigation across HUD tabs
    tab_map = {
        "home": ("home", "Home Dashboard"),
        "dashboard": ("home", "Home Dashboard"),
        "files": ("files", "Files Explorer"),
        "file explorer": ("files", "Files Explorer"),
        "tools": ("tools", "Tools Suite"),
        "security": ("security", "Security Diagnostics"),
        "developer": ("developer", "Developer Console"),
        "dev console": ("developer", "Developer Console"),
        "settings": ("settings", "Settings"),
    }
    for trigger, (tab_id, label) in tab_map.items():
        if lower in {trigger, f"open {trigger}", f"go to {trigger}", f"show {trigger}", f"switch to {trigger}"}:
            return {
                "reply": f"Switching interface to {label}, {first_name}.",
                "action": {"type": "switch_tab", "tab": tab_id},
            }

    # 5. App shortcuts
    app_triggers = {
        "vs code": "vscode",
        "vscode": "vscode",
        "code": "vscode",
        "browser": "browser",
        "chrome": "browser",
        "terminal": "terminal",
        "powershell": "terminal",
        "python": "python",
        "github": "github",
        "youtube": "youtube",
        "notepad": "notepad",
        "calculator": "calc",
        "explorer": "explorer",
    }
    for phrase, shortcut in app_triggers.items():
        if re.search(rf"\b(open|launch|start)\s+{re.escape(phrase)}\b", lower):
            res = launch_shortcut(shortcut)
            return {"reply": res["message"], "action": None}

    # 6. Task / Today's Plan commands
    add_match = re.match(r"^(?:add task|new task|remind me to|add to plan)\s+(.+)$", msg, re.IGNORECASE)
    if add_match:
        title = add_match.group(1).strip()
        task = add_task(title)
        return {
            "reply": f"Added '{task['title']}' to Today's Plan.",
            "action": {"type": "refresh_tasks"},
        }

    done_match = re.match(r"^(?:complete task|finish task|done task|check)\s+(.+)$", msg, re.IGNORECASE)
    if done_match:
        target = done_match.group(1).strip().lower()
        for t in list_tasks():
            if target in t["title"].lower():
                update_task(t["id"], completed=True)
                return {
                    "reply": f"Marked '{t['title']}' as completed. Well done, {first_name}.",
                    "action": {"type": "refresh_tasks"},
                }
        return {"reply": f"I couldn't find a task matching '{target}'.", "action": None}

    if any(k in lower for k in ("today's plan", "todays plan", "my tasks", "list tasks", "show plan")):
        tasks = list_tasks()
        pending = [t["title"] for t in tasks if not t["completed"]]
        if not pending:
            return {"reply": "All tasks in Today's Plan are completed!", "action": None}
        return {
            "reply": f"You have {len(pending)} pending tasks: " + "; ".join(pending[:5]) + ".",
            "action": None,
        }

    # 7. Web / YouTube search
    search_match = re.match(r"^(?:search|google|look up|find)\s+(?:for\s+)?(.+)$", msg, re.IGNORECASE)
    if search_match:
        query = search_match.group(1).strip()
        url = f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}"
        webbrowser.open(url)
        return {"reply": f"Searching the web for '{query}'.", "action": None}

    yt_match = re.match(r"^(?:play|youtube)\s+(.+)$", msg, re.IGNORECASE)
    if yt_match:
        query = yt_match.group(1).strip()
        url = f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(query)}"
        webbrowser.open(url)
        return {"reply": f"Searching YouTube for '{query}'.", "action": None}

    # 8. Weather query
    if "weather" in lower or "temperature" in lower:
        return {
            "reply": f"Checking atmospheric conditions for {cfg.get('city', 'Bhopal, MP')} — look at the Quick Info panel on your HUD.",
            "action": {"type": "refresh_weather"},
        }

    # 9. Jokes
    if "joke" in lower:
        try:
            import pyjokes

            joke = pyjokes.get_joke()
        except Exception:
            joke = "Why do programmers prefer dark mode? Because light attracts bugs."
        return {"reply": joke, "action": None}

    # 10. Quick math evaluation
    math_clean = re.sub(r"^(?:calculate|compute|what is|eval)\s+", "", lower).replace("x", "*")
    if re.fullmatch(r"[\d\s+\-*/().%]+", math_clean) and any(ch.isdigit() for ch in math_clean):
        val = _safe_eval_math(math_clean)
        if val is not None:
            formatted = int(val) if val.is_integer() else round(val, 4)
            return {"reply": f"The result is {formatted}.", "action": None}

    # 11. Optional LLM fallback if configured
    llm_reply = _call_optional_llm(msg, cfg)
    if llm_reply:
        return {"reply": llm_reply, "action": None}

    # 12. Smart offline fallback
    return {
        "reply": (
            f"Command received: '{msg}'. You can ask me for system status, open apps (VS Code, Terminal, Browser), "
            "manage Today's Plan ('add task ...'), search the web ('search ...'), run calculations, or connect a Gemini/OpenAI key in Settings for full conversational AI."
        ),
        "action": None,
    }
