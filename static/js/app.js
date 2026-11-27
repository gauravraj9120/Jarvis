/**
 * Main controller for the J.A.R.V.I.S. Futuristic HUD.
 */

import { initAssistant } from "./assistant.js";
import { initAllPanels, loadFiles, loadSecurityOverview, loadTasks } from "./panels.js";
import { initVisualizerAndParticles } from "./reactor.js";
import { startTelemetryLoop } from "./telemetry.js";

let currentUserName = "Gaurav Kumar";

export function showToast(msg) {
  const toast = document.getElementById("hudToast");
  if (!toast) return;
  toast.textContent = msg;
  toast.classList.remove("hidden");
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => toast.classList.add("hidden"), 3000);
}

export function switchTab(tabId) {
  document.querySelectorAll(".nav-pill").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tabId);
  });
  document.querySelectorAll(".tab-view").forEach((view) => {
    view.classList.toggle("active", view.id === `view-${tabId}`);
  });

  if (tabId === "files") loadFiles();
  if (tabId === "security") loadSecurityOverview();
}

function updateClockAndGreeting() {
  const now = new Date();
  let hours = now.getHours();
  const ampm = hours >= 12 ? "PM" : "AM";
  const greetWord =
    hours < 12 ? "Good Morning" : hours < 17 ? "Good Afternoon" : "Good Evening";

  const h12 = String(hours % 12 || 12).padStart(2, "0");
  const mins = String(now.getMinutes()).padStart(2, "0");
  const secs = String(now.getSeconds()).padStart(2, "0");

  const hmsEl = document.getElementById("clockHMS");
  const ampmEl = document.getElementById("clockAMPM");
  const dateEl = document.getElementById("clockDate");
  const greetEl = document.getElementById("greetingTitle");

  if (hmsEl) hmsEl.textContent = `${h12}:${mins}:${secs}`;
  if (ampmEl) ampmEl.textContent = ampm;
  if (dateEl) {
    dateEl.textContent = now.toLocaleDateString("en-GB", {
      weekday: "short",
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  }
  if (greetEl) greetEl.textContent = `${greetWord}, ${currentUserName}!`;
}

function applyConfigToHud(cfg) {
  currentUserName = cfg.user_name || "Gaurav Kumar";
  const bubbleUser = document.getElementById("bubbleUserName");
  const quoteEl = document.getElementById("infoQuote");
  const footerEl = document.getElementById("footerLabel");

  if (bubbleUser) bubbleUser.textContent = currentUserName;
  if (quoteEl && cfg.quote) quoteEl.textContent = `— "${cfg.quote}"`;
  if (footerEl) {
    footerEl.innerHTML = `${currentUserName.toUpperCase()} &nbsp;•&nbsp; POWERED BY J.A.R.V.I.S.`;
  }
  updateClockAndGreeting();
}

function initShortcuts() {
  document.querySelectorAll("[data-shortcut]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const target = btn.dataset.shortcut;
      try {
        const res = await fetch("/api/shortcuts/launch", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ target }),
        });
        const data = await res.json();
        showToast(data.message || `Triggered ${target}`);
      } catch {
        showToast(`Failed to launch ${target}`);
      }
    });
  });

  document.querySelectorAll("[data-tab-jump]").forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tabJump));
  });
}

function initTopBarControls() {
  document.querySelectorAll(".nav-pill").forEach((pill) => {
    pill.addEventListener("click", () => switchTab(pill.dataset.tab));
  });

  document.getElementById("btnFullscreen")?.addEventListener("click", () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen?.();
    } else {
      document.exitFullscreen?.();
    }
  });

  document.getElementById("btnHelp")?.addEventListener("click", () => {
    showToast("Tip: Press '/' to focus command dock, or click the Mic and say 'System status'!");
  });

  // Press '/' anywhere (outside inputs) to jump to command dock
  document.addEventListener("keydown", (e) => {
    if (
      e.key === "/" &&
      !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName)
    ) {
      e.preventDefault();
      switchTab("home");
      document.getElementById("commandInput")?.focus();
    }
  });
}

async function initializeAuthentication() {
  const gate = document.getElementById("authGate");
  const form = document.getElementById("authForm");
  const tokenInput = document.getElementById("authToken");
  const error = document.getElementById("authError");
  const signOutButton = document.getElementById("btnSignOut");

  try {
    const response = await fetch("/api/auth/status", { cache: "no-store" });
    if (!response.ok) throw new Error("Authentication status request failed.");

    const status = await response.json();
    if (!status.required) return true;

    if (status.authenticated) {
      signOutButton?.classList.remove("hidden");
      signOutButton?.addEventListener("click", async () => {
        try {
          const logout = await fetch("/api/auth/logout", { method: "POST" });
          if (!logout.ok) throw new Error("Sign-out failed.");
          window.location.reload();
        } catch {
          showToast("Unable to lock the session. Please try again.");
        }
      });
      return true;
    }
  } catch {
    if (error) error.textContent = "Could not reach the authentication service. Try again.";
  }

  gate?.classList.remove("hidden");
  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (error) error.textContent = "";

    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: tokenInput?.value || "" }),
      });
      if (!response.ok) {
        if (error) error.textContent = "Invalid access token.";
        tokenInput?.select();
        return;
      }
      window.location.reload();
    } catch {
      if (error) error.textContent = "Unable to contact the authentication service.";
    }
  });
  tokenInput?.focus();
  return false;
}

document.addEventListener("DOMContentLoaded", async () => {
  if (!(await initializeAuthentication())) return;

  initTopBarControls();
  initShortcuts();
  initVisualizerAndParticles();
  startTelemetryLoop();
  initAssistant({
    onSwitchTab: switchTab,
    onRefreshTasks: loadTasks,
    showToast,
  });
  initAllPanels(applyConfigToHud, showToast);

  updateClockAndGreeting();
  setInterval(updateClockAndGreeting, 1000);
});
