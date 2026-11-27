# J.A.R.V.I.S. — Futuristic Command HUD

A futuristic Iron Man–inspired **J.A.R.V.I.S.** (*Just A Rather Very Intelligent System*) desktop HUD powered by **FastAPI** and a live **HTML5/SVG/Canvas** holographic interface.

## Features

- **Home HUD Dashboard**:
  - Live real-time digital clock & dynamic time-of-day greeting (`Gaurav Kumar`).
  - **System Status**: Native Windows Win32 telemetry (`GetSystemTimes`, `GlobalMemoryStatusEx`, `shutil.disk_usage`) feeding glowing CPU, RAM, and Disk circular gauges.
  - **Network Monitor**: Real-time Download/Upload Mbps (`GetIfTable`) with a live scrolling sparkline chart.
  - **Holographic Arc Reactor Core**: Multi-ring rotating SVG + particle field + topbar audio spectrum visualizer that reacts to `ONLINE`, `LISTENING`, `PROCESSING`, and `SPEAKING` states.
  - **J.A.R.V.I.S. Voice & Command Assistant**: Web Speech API microphone input + TTS voice response + text command bar (`System status`, `Open VS Code`, `Add task ...`, `Search ...`, `Tell me a joke`, math calculations, and optional Gemini/OpenAI LLM integration).
  - **Today's Plan & Quick Info**: Persistent task planner (`data/tasks.json`) and live weather via Open-Meteo (`Bhopal, MP, India`).
- **Multi-Tab Workspace**:
  - **Files**: Browse local workspace files and inspect source previews.
  - **Tools**: Persistent Mission Notes, 25/5 Focus Timer, App Launchers, and Web Search.
  - **Security**: Live TCP connections (`netstat`), top memory processes (`tasklist`), CSPRNG Password Generator, and MD5/SHA-1/SHA-256/SHA-512 Hash Inspector.
  - **Developer**: Execute PowerShell or Python 3.14 snippets directly in `D:\Jarvis`.
  - **Settings**: Customize operator name, city/coordinates, quote, voice/wake-word toggles, and optional Gemini/OpenAI API key.

## Launch
## Launch

Activate the virtual environment and run via Python, or double-click `start_jarvis.bat`:

```powershell
.\.venv\Scripts\Activate.ps1
python run_jarvis.py
```

Then open `http://127.0.0.1:8765` in your browser (Edge/Chrome recommended for Web Speech API voice recognition).

## Render deployment

1. Push this repository to GitHub.
2. In Render, choose **New → Blueprint**, select this repository, and apply the `render.yaml` blueprint.
3. After the service is live, open its URL and enter the generated `JARVIS_ACCESS_TOKEN` from the service's **Environment** settings.

The blueprint builds from the repository root, starts Uvicorn on Render's assigned port, and generates a private access token. Keep that token in Render's environment settings; never commit it. The public page and Google verification file remain reachable, while API routes require the authenticated session. When deployed, operating-system tools run in the Render container rather than on the desktop. The free instance uses ephemeral storage, so notes, tasks, and settings saved at runtime can be lost when the service restarts or redeploys.
