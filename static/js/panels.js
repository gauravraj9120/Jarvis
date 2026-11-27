/**
 * Interactive panels for Today's Plan, Files, Tools, Security, Developer, and Settings.
 */

import { setAssistantConfig } from "./assistant.js";
import { refreshWeather } from "./telemetry.js";

function escapeHtml(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

// ---------- TODAY'S PLAN ----------
export async function loadTasks() {
  const listEl = document.getElementById("planList");
  const modalListEl = document.getElementById("modalPlanList");
  if (!listEl) return;

  try {
    const res = await fetch("/api/tasks");
    const tasks = await res.json();

    const renderInto = (container, maxItems = null) => {
      container.innerHTML = "";
      const slice = maxItems ? tasks.slice(0, maxItems) : tasks;
      if (slice.length === 0) {
        container.innerHTML = `<li class="plan-item"><span class="plan-title" style="color:var(--text-muted)">All missions complete. Add one below!</span></li>`;
        return;
      }
      slice.forEach((task) => {
        const li = document.createElement("li");
        li.className = `plan-item ${task.completed ? "done" : ""}`;
        li.innerHTML = `
          <button type="button" class="plan-chk" aria-label="Toggle task">${task.completed ? "✓" : ""}</button>
          <span class="plan-title">${escapeHtml(task.title)}</span>
          <button type="button" class="plan-del" title="Remove">✕</button>
        `;
        const toggle = async () => {
          await fetch(`/api/tasks/${task.id}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ completed: !task.completed }),
          });
          loadTasks();
        };
        li.querySelector(".plan-chk").addEventListener("click", toggle);
        li.querySelector(".plan-title").addEventListener("click", toggle);
        li.querySelector(".plan-del").addEventListener("click", async () => {
          await fetch(`/api/tasks/${task.id}`, { method: "DELETE" });
          loadTasks();
        });
        container.appendChild(li);
      });
    };

    renderInto(listEl, 5);
    if (modalListEl) renderInto(modalListEl, null);
  } catch {
    // ignore
  }
}

export function initPlanPanel() {
  const form = document.getElementById("quickTaskForm");
  const input = document.getElementById("quickTaskInput");
  const modal = document.getElementById("planModal");
  const openBtn = document.getElementById("btnOpenPlanModal");
  const closeBtn = document.getElementById("btnClosePlanModal");

  if (form && input) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const title = input.value.trim();
      if (!title) return;
      input.value = "";
      await fetch("/api/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      });
      loadTasks();
    });
  }

  if (openBtn && modal) {
    openBtn.addEventListener("click", () => {
      loadTasks();
      modal.classList.remove("hidden");
    });
  }
  if (closeBtn && modal) {
    closeBtn.addEventListener("click", () => modal.classList.add("hidden"));
    modal.addEventListener("click", (e) => {
      if (e.target === modal) modal.classList.add("hidden");
    });
  }
}

// ---------- FILES EXPLORER ----------
let currentDirPath = null;
let currentParentPath = null;

export async function loadFiles(path = null) {
  const listPane = document.getElementById("filesList");
  const pathInput = document.getElementById("filesPathInput");
  if (!listPane) return;

  const query = path ? `?path=${encodeURIComponent(path)}` : "";
  const res = await fetch(`/api/files/list${query}`);
  const data = await res.json();

  currentDirPath = data.path;
  currentParentPath = data.parent;
  if (pathInput) pathInput.value = data.path;

  listPane.innerHTML = "";
  if (data.error) {
    listPane.innerHTML = `<div class="file-row">${escapeHtml(data.error)}</div>`;
    return;
  }

  for (const entry of data.entries || []) {
    const row = document.createElement("div");
    row.className = "file-row";
    const sizeText = entry.is_dir ? "DIR" : `${(entry.size / 1024).toFixed(1)} KB`;
    row.innerHTML = `
      <span>${entry.is_dir ? "📁" : "📄"} ${escapeHtml(entry.name)}</span>
      <span class="file-meta">${sizeText}</span>
    `;
    row.addEventListener("click", async () => {
      if (entry.is_dir) {
        loadFiles(entry.path);
      } else {
        const fRes = await fetch(`/api/files/read?path=${encodeURIComponent(entry.path)}`);
        const fData = await fRes.json();
        document.getElementById("filePreviewTitle").textContent = fData.path || entry.name;
        document.getElementById("filePreviewContent").textContent =
          fData.content || fData.error || "";
      }
    });
    listPane.appendChild(row);
  }
}

function initFilesPanel() {
  document.getElementById("btnFilesUp")?.addEventListener("click", () => {
    if (currentParentPath) loadFiles(currentParentPath);
  });
  document.getElementById("btnFilesRefresh")?.addEventListener("click", () => {
    loadFiles(currentDirPath);
  });
}

// ---------- TOOLS (NOTES + TIMER + SEARCH) ----------
async function loadNotes() {
  const listEl = document.getElementById("notesList");
  if (!listEl) return;
  const res = await fetch("/api/notes");
  const notes = await res.json();

  listEl.innerHTML = "";
  notes.forEach((n, idx) => {
    const item = document.createElement("div");
    item.className = "note-item";
    item.innerHTML = `<strong>${escapeHtml(n.title)}</strong><div class="file-meta">${n.updated_at}</div>`;
    item.addEventListener("click", () => {
      document.querySelectorAll(".note-item").forEach((el) => el.classList.remove("active"));
      item.classList.add("active");
      document.getElementById("noteEditId").value = n.id;
      document.getElementById("noteTitleInput").value = n.title;
      document.getElementById("noteContentInput").value = n.content;
    });
    listEl.appendChild(item);
    if (idx === 0 && !document.getElementById("noteEditId").value) {
      item.click();
    }
  });
}

function initToolsPanel() {
  document.getElementById("btnNewNote")?.addEventListener("click", () => {
    document.getElementById("noteEditId").value = "";
    document.getElementById("noteTitleInput").value = "";
    document.getElementById("noteContentInput").value = "";
    document.getElementById("noteTitleInput").focus();
  });

  document.getElementById("btnSaveNote")?.addEventListener("click", async () => {
    const id = document.getElementById("noteEditId").value || null;
    const title = document.getElementById("noteTitleInput").value || "Untitled Note";
    const content = document.getElementById("noteContentInput").value || "";
    const res = await fetch("/api/notes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, title, content }),
    });
    const saved = await res.json();
    document.getElementById("noteEditId").value = saved.id;
    loadNotes();
  });

  document.getElementById("btnDeleteNote")?.addEventListener("click", async () => {
    const id = document.getElementById("noteEditId").value;
    if (!id) return;
    await fetch(`/api/notes/${id}`, { method: "DELETE" });
    document.getElementById("noteEditId").value = "";
    document.getElementById("noteTitleInput").value = "";
    document.getElementById("noteContentInput").value = "";
    loadNotes();
  });

  // Focus timer
  let remaining = 25 * 60;
  let timerId = null;
  const disp = document.getElementById("timerDisplay");
  const renderTimer = () => {
    const m = String(Math.floor(remaining / 60)).padStart(2, "0");
    const s = String(remaining % 60).padStart(2, "0");
    if (disp) disp.textContent = `${m}:${s}`;
  };
  const startCountdown = (seconds) => {
    clearInterval(timerId);
    remaining = seconds;
    renderTimer();
    timerId = setInterval(() => {
      if (remaining <= 0) {
        clearInterval(timerId);
        return;
      }
      remaining -= 1;
      renderTimer();
    }, 1000);
  };
  document.getElementById("btnTimerStart")?.addEventListener("click", () => startCountdown(25 * 60));
  document.getElementById("btnTimer5")?.addEventListener("click", () => startCountdown(5 * 60));
  document.getElementById("btnTimerReset")?.addEventListener("click", () => {
    clearInterval(timerId);
    remaining = 25 * 60;
    renderTimer();
  });

  document.getElementById("toolSearchForm")?.addEventListener("submit", (e) => {
    e.preventDefault();
    const q = document.getElementById("toolSearchInput").value.trim();
    if (!q) return;
    window.open(`https://www.google.com/search?q=${encodeURIComponent(q)}`, "_blank");
  });
}

// ---------- SECURITY ----------
export async function loadSecurityOverview() {
  const connBody = document.querySelector("#secConnectionsTable tbody");
  const procBody = document.querySelector("#secProcessesTable tbody");
  if (!connBody || !procBody) return;

  const res = await fetch("/api/security/overview");
  const data = await res.json();

  connBody.innerHTML = (data.connections || [])
    .map(
      (c) =>
        `<tr><td>${escapeHtml(c.local)}</td><td>${escapeHtml(c.remote)}</td><td>${escapeHtml(c.state)}</td><td>${escapeHtml(c.pid)}</td></tr>`
    )
    .join("");

  procBody.innerHTML = (data.processes || [])
    .map(
      (p) =>
        `<tr><td>${escapeHtml(p.name)}</td><td>${escapeHtml(p.pid)}</td><td>${p.memory_mb} MB</td></tr>`
    )
    .join("");
}

function initSecurityPanel() {
  document.getElementById("btnSecRefresh")?.addEventListener("click", loadSecurityOverview);

  document.getElementById("btnGenPwd")?.addEventListener("click", async () => {
    const length = Number(document.getElementById("pwdLenInput").value) || 18;
    const symbols = document.getElementById("pwdSymInput").checked;
    const res = await fetch(`/api/security/password?length=${length}&symbols=${symbols}`);
    const data = await res.json();
    document.getElementById("pwdOutput").textContent = data.password;
  });

  document.getElementById("btnComputeHash")?.addEventListener("click", async () => {
    const text = document.getElementById("hashInput").value;
    const res = await fetch("/api/security/hash", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    const h = await res.json();
    document.getElementById("hashOutput").textContent =
      `MD5:    ${h.md5}\nSHA1:   ${h.sha1}\nSHA256: ${h.sha256}\nSHA512: ${h.sha512}`;
  });
}

// ---------- DEVELOPER CONSOLE ----------
function initDeveloperPanel() {
  const form = document.getElementById("devExecForm");
  const input = document.getElementById("devCmdInput");
  const modeSel = document.getElementById("devModeSelect");
  const out = document.getElementById("devOutput");

  const runCmd = async (command, mode) => {
    out.textContent = `> [${mode}] ${command}\nRunning...`;
    const res = await fetch("/api/dev/exec", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ command, mode }),
    });
    const data = await res.json();
    const parts = [`> [${mode}] ${command} (exit ${data.exit_code})`];
    if (data.stdout) parts.push(data.stdout.trimEnd());
    if (data.stderr) parts.push(`[STDERR]\n${data.stderr.trimEnd()}`);
    out.textContent = parts.join("\n\n");
  };

  form?.addEventListener("submit", (e) => {
    e.preventDefault();
    const cmd = input.value.trim();
    if (!cmd) return;
    runCmd(cmd, modeSel.value);
  });

  document.querySelectorAll(".dev-preset").forEach((btn) => {
    btn.addEventListener("click", () => {
      modeSel.value = btn.dataset.mode;
      input.value = btn.dataset.cmd;
      runCmd(btn.dataset.cmd, btn.dataset.mode);
    });
  });
}

// ---------- SETTINGS ----------
export async function loadAndApplyConfig(onConfigApplied) {
  const res = await fetch("/api/config");
  const cfg = await res.json();

  document.getElementById("cfgUserName").value = cfg.user_name || "Gaurav Kumar";
  document.getElementById("cfgCity").value = cfg.city || "Bhopal, MP";
  document.getElementById("cfgCountry").value = cfg.country || "India";
  document.getElementById("cfgLat").value = cfg.latitude ?? 23.2599;
  document.getElementById("cfgLon").value = cfg.longitude ?? 77.4126;
  document.getElementById("cfgQuote").value = cfg.quote || "";
  document.getElementById("cfgVoiceEnabled").checked = cfg.voice_enabled !== false;
  document.getElementById("cfgWakeWordEnabled").checked = Boolean(cfg.wake_word_enabled);
  document.getElementById("cfgAiProvider").value = cfg.ai_provider || "local";
  document.getElementById("cfgAiModel").value = cfg.ai_model || "gemini-2.5-flash";
  document.getElementById("cfgAiKey").value = cfg.ai_api_key || "";

  setAssistantConfig(cfg);
  if (onConfigApplied) onConfigApplied(cfg);
  return cfg;
}

function initSettingsPanel(onConfigApplied, showToast) {
  const savePatch = async (patch) => {
    const res = await fetch("/api/config", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    });
    const cfg = await res.json();
    setAssistantConfig(cfg);
    if (onConfigApplied) onConfigApplied(cfg);
    refreshWeather();
    showToast("J.A.R.V.I.S. configuration saved.");
  };

  document.getElementById("settingsForm")?.addEventListener("submit", (e) => {
    e.preventDefault();
    savePatch({
      user_name: document.getElementById("cfgUserName").value.trim() || "Gaurav Kumar",
      city: document.getElementById("cfgCity").value.trim(),
      country: document.getElementById("cfgCountry").value.trim(),
      latitude: parseFloat(document.getElementById("cfgLat").value) || 23.2599,
      longitude: parseFloat(document.getElementById("cfgLon").value) || 77.4126,
      quote: document.getElementById("cfgQuote").value.trim(),
      voice_enabled: document.getElementById("cfgVoiceEnabled").checked,
      wake_word_enabled: document.getElementById("cfgWakeWordEnabled").checked,
    });
  });

  document.getElementById("aiSettingsForm")?.addEventListener("submit", (e) => {
    e.preventDefault();
    savePatch({
      ai_provider: document.getElementById("cfgAiProvider").value,
      ai_model: document.getElementById("cfgAiModel").value.trim(),
      ai_api_key: document.getElementById("cfgAiKey").value.trim(),
    });
  });
}

export function initAllPanels(onConfigApplied, showToast) {
  initPlanPanel();
  initFilesPanel();
  initToolsPanel();
  initSecurityPanel();
  initDeveloperPanel();
  initSettingsPanel(onConfigApplied, showToast);

  loadTasks();
  loadNotes();
  loadFiles();
  loadSecurityOverview();
  loadAndApplyConfig(onConfigApplied);
}
