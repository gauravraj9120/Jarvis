/**
 * J.A.R.V.I.S. Voice Recognition, Automatic Wake-Word Loop, Speech Synthesis, and Assistant.
 */

import { setCoreState } from "./reactor.js";
import { refreshWeather } from "./telemetry.js";

let voiceEnabled = true;
let wakeWordEnabled = false;
let wakeWordPhrase = "hey jarvis";
let recognition = null;
let isListening = false;
let isSpeaking = false;
let manualListening = false;
let awakeUntil = 0;
let userInteracted = false;
let restartTimer = null;

const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;

function updateMicStatus(text) {
  const el = document.getElementById("micStatus");
  if (el) el.textContent = text;
}

function updateAutoButton() {
  const btn = document.getElementById("btnAutoListen");
  if (!btn) return;
  btn.classList.toggle("active", wakeWordEnabled);
  btn.textContent = wakeWordEnabled ? "AUTO: ON" : "AUTO: OFF";
}

function startRecognitionSafe() {
  if (!recognition || isListening || isSpeaking) return;
  try {
    recognition.start();
  } catch {
    // Ignore InvalidStateError if already starting
  }
}

function scheduleAutoRestart(delayMs = 400) {
  clearTimeout(restartTimer);
  if (!wakeWordEnabled || isSpeaking) return;
  restartTimer = setTimeout(() => {
    if (wakeWordEnabled && !isListening && !isSpeaking) {
      startRecognitionSafe();
    }
  }, delayMs);
}

function extractWakeCommand(transcript) {
  const lower = transcript.toLowerCase().trim();
  const triggers = [
    wakeWordPhrase,
    "hey jarvis",
    "ok jarvis",
    "hi jarvis",
    "jarvis",
    "jarvish",
    "jarves",
  ];
  for (const trig of triggers) {
    const idx = lower.indexOf(trig);
    if (idx !== -1) {
      const rest = transcript.slice(idx + trig.length).replace(/^[,:\s.!?]+/, "").trim();
      return { matched: true, command: rest };
    }
  }
  return { matched: false, command: transcript.trim() };
}

export function setAssistantConfig(cfg) {
  voiceEnabled = cfg.voice_enabled !== false;
  wakeWordEnabled = Boolean(cfg.wake_word_enabled);
  wakeWordPhrase = (cfg.wake_word || "hey jarvis").toLowerCase();

  const btn = document.getElementById("btnVoiceToggle");
  if (btn) {
    btn.classList.toggle("muted", !voiceEnabled);
    btn.textContent = voiceEnabled ? "🔊" : "🔇";
  }

  updateAutoButton();

  if (wakeWordEnabled) {
    if (recognition && !isListening && !isSpeaking) {
      updateMicStatus('Auto-listening for "Hey Jarvis"...');
      startRecognitionSafe();
    }
  } else {
    clearTimeout(restartTimer);
    if (recognition && isListening && !manualListening) {
      recognition.stop();
    }
    if (!isListening) {
      updateMicStatus("Click Mic to speak...");
    }
  }
}

export function speakText(text) {
  if (!voiceEnabled || !("speechSynthesis" in window)) {
    setCoreState(isListening ? "listening" : "online");
    return;
  }

  // Pause mic while Jarvis speaks so he doesn't hear his own voice
  isSpeaking = true;
  clearTimeout(restartTimer);
  if (recognition && isListening) {
    try {
      recognition.abort();
    } catch {
      // ignore
    }
  }

  window.speechSynthesis.cancel();
  const utter = new SpeechSynthesisUtterance(text);
  const voices = window.speechSynthesis.getVoices();
  const preferred =
    voices.find((v) => /en-GB|Daniel|George|Ryan|Google UK English Male/i.test(v.name + v.lang)) ||
    voices.find((v) => v.lang.startsWith("en"));
  if (preferred) utter.voice = preferred;
  utter.rate = 1.03;
  utter.pitch = 0.94;

  const finishSpeaking = () => {
    isSpeaking = false;
    setCoreState(wakeWordEnabled ? "listening" : "online");
    if (wakeWordEnabled) {
      scheduleAutoRestart(350);
    }
  };

  utter.onstart = () => setCoreState("speaking");
  utter.onend = finishSpeaking;
  utter.onerror = finishSpeaking;
  window.speechSynthesis.speak(utter);
}

function appendChatMessage(role, text) {
  const lead = document.getElementById("bubbleLead");
  const caps = document.getElementById("bubbleCaps");
  const feed = document.getElementById("chatFeed");
  const bubble = document.getElementById("assistantBubble");

  if (lead) lead.classList.add("hidden");
  if (caps) caps.classList.add("hidden");
  if (feed) {
    feed.classList.remove("hidden");
    const div = document.createElement("div");
    div.className = `chat-msg ${role}`;
    div.textContent = role === "user" ? `You: ${text}` : text;
    feed.appendChild(div);
    while (feed.children.length > 16) {
      feed.removeChild(feed.firstChild);
    }
  }
  if (bubble) bubble.scrollTop = bubble.scrollHeight;
}

export function resetAssistantBubble() {
  const lead = document.getElementById("bubbleLead");
  const caps = document.getElementById("bubbleCaps");
  const feed = document.getElementById("chatFeed");
  if (lead) lead.classList.remove("hidden");
  if (caps) caps.classList.remove("hidden");
  if (feed) {
    feed.classList.add("hidden");
    feed.innerHTML = "";
  }
}

export async function sendJarvisCommand(message, callbacks = {}) {
  const { onSwitchTab, onRefreshTasks, showToast } = callbacks;
  const clean = message.trim();
  if (!clean) return;

  appendChatMessage("user", clean);
  setCoreState("thinking");

  try {
    const res = await fetch("/api/assistant/command", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: clean }),
    });
    const data = await res.json();
    const reply = data.reply || "Command executed.";
    appendChatMessage("jarvis", reply);

    if (data.action?.type === "sleep_mic") {
      awakeUntil = 0;
      wakeWordEnabled = false;
      updateAutoButton();
      fetch("/api/config", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ wake_word_enabled: false }),
      }).catch(() => {});
    } else if (data.action?.type === "switch_tab" && onSwitchTab) {
      onSwitchTab(data.action.tab);
    } else if (data.action?.type === "refresh_tasks" && onRefreshTasks) {
      onRefreshTasks();
    } else if (data.action?.type === "refresh_weather") {
      refreshWeather();
    }

    speakText(reply);
  } catch {
    const err = "Core connection interrupted. Verify FastAPI backend is running.";
    appendChatMessage("jarvis", err);
    setCoreState("online");
    if (showToast) showToast(err);
  }
}

export function initAssistant(callbacks) {
  const form = document.getElementById("commandForm");
  const input = document.getElementById("commandInput");
  const micBtn = document.getElementById("micBtn");
  const voiceToggle = document.getElementById("btnVoiceToggle");
  const autoListenBtn = document.getElementById("btnAutoListen");
  const resetBtn = document.getElementById("btnResetChat");

  // Unlock browser speech/mic on first user interaction if blocked before gesture
  const onFirstGesture = () => {
    if (userInteracted) return;
    userInteracted = true;
    if (wakeWordEnabled && !isListening && !isSpeaking) {
      startRecognitionSafe();
    }
  };
  document.addEventListener("pointerdown", onFirstGesture, { once: true });
  document.addEventListener("keydown", onFirstGesture, { once: true });

  if (form && input) {
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const val = input.value;
      input.value = "";
      sendJarvisCommand(val, callbacks);
    });
  }

  document.querySelectorAll(".prompt-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const cmd = chip.dataset.cmd || "";
      sendJarvisCommand(cmd, callbacks);
    });
  });

  if (voiceToggle) {
    voiceToggle.addEventListener("click", () => {
      voiceEnabled = !voiceEnabled;
      voiceToggle.classList.toggle("muted", !voiceEnabled);
      voiceToggle.textContent = voiceEnabled ? "🔊" : "🔇";
      if (!voiceEnabled && "speechSynthesis" in window) {
        window.speechSynthesis.cancel();
        isSpeaking = false;
      }
      fetch("/api/config", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ voice_enabled: voiceEnabled }),
      }).catch(() => {});
    });
  }

  if (autoListenBtn) {
    autoListenBtn.addEventListener("click", async () => {
      wakeWordEnabled = !wakeWordEnabled;
      updateAutoButton();
      const cfgChk = document.getElementById("cfgWakeWordEnabled");
      if (cfgChk) cfgChk.checked = wakeWordEnabled;

      await fetch("/api/config", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ wake_word_enabled: wakeWordEnabled }),
      }).catch(() => {});

      if (wakeWordEnabled) {
        updateMicStatus('Auto-listening for "Hey Jarvis"...');
        startRecognitionSafe();
      } else {
        clearTimeout(restartTimer);
        if (isListening) recognition?.stop();
        updateMicStatus("Click Mic to speak...");
      }
    });
  }

  if (resetBtn) {
    resetBtn.addEventListener("click", resetAssistantBubble);
  }

  if (micBtn) {
    if (!SpeechRec) {
      updateMicStatus("Type commands below (Mic unsupported in this browser)");
      micBtn.disabled = true;
      return;
    }

    recognition = new SpeechRec();
    recognition.lang = "en-IN";
    recognition.interimResults = false;
    recognition.continuous = false;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      isListening = true;
      micBtn.classList.add("active");
      setCoreState("listening");
      if (manualListening || Date.now() < awakeUntil) {
        updateMicStatus("Listening for command...");
      } else if (wakeWordEnabled) {
        updateMicStatus('Listening... say "Hey Jarvis"');
      } else {
        updateMicStatus("Listening...");
      }
    };

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript.trim();
      if (!transcript) return;

      const { matched, command } = extractWakeCommand(transcript);
      const isAwakeWindow = Date.now() < awakeUntil;

      if (manualListening || matched || isAwakeWindow || !wakeWordEnabled) {
        manualListening = false;
        awakeUntil = Date.now() + 18000;

        if (matched && !command) {
          updateMicStatus('Awake! Listening for command...');
          appendChatMessage("jarvis", "Yes? I am listening.");
          speakText("Yes? I am listening.");
          return;
        }

        const cmdToRun = matched ? command : transcript;
        updateMicStatus(`Heard: "${cmdToRun}"`);
        sendJarvisCommand(cmdToRun, callbacks);
      } else {
        updateMicStatus('Standby — say "Hey Jarvis"...');
      }
    };

    recognition.onerror = (event) => {
      isListening = false;
      micBtn.classList.remove("active");
      manualListening = false;

      if (event.error === "not-allowed" || event.error === "service-not-allowed") {
        updateMicStatus("Mic permission needed — click Mic to allow");
        setCoreState("online");
        return;
      }

      if (wakeWordEnabled && !isSpeaking && (event.error === "no-speech" || event.error === "aborted")) {
        scheduleAutoRestart(450);
        return;
      }

      updateMicStatus("Click Mic to speak...");
      setCoreState("online");
    };

    recognition.onend = () => {
      isListening = false;
      micBtn.classList.remove("active");
      manualListening = false;
      if (!isSpeaking) {
        setCoreState("online");
      }
      if (wakeWordEnabled && !isSpeaking) {
        scheduleAutoRestart(350);
      } else if (!wakeWordEnabled && !isSpeaking) {
        setTimeout(() => {
          if (!isListening) updateMicStatus("Click Mic to speak...");
        }, 1200);
      }
    };

    micBtn.addEventListener("click", () => {
      if (isListening) {
        manualListening = false;
        recognition.stop();
      } else {
        manualListening = true;
        awakeUntil = Date.now() + 20000;
        startRecognitionSafe();
      }
    });

    if (wakeWordEnabled) {
      startRecognitionSafe();
    }
  }
}
