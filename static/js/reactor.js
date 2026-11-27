/**
 * Holographic Arc Reactor particles, core state controller, and topbar audio visualizer.
 */

let coreState = "online";

export function setCoreState(state) {
  coreState = state;
  const stage = document.querySelector(".reactor-stage");
  const statusEl = document.getElementById("reactorStatus");
  const statusText = document.getElementById("reactorStatusText");
  const helmet = document.getElementById("helmetReticle");
  const badge = document.getElementById("assistantModeBadge");

  if (!stage || !statusEl || !statusText) return;

  stage.classList.remove("listening", "speaking", "thinking");
  statusEl.classList.remove("listening", "speaking");
  if (helmet) helmet.classList.remove("speaking");

  if (state === "listening") {
    stage.classList.add("listening");
    statusEl.classList.add("listening");
    statusText.textContent = "LISTENING";
    if (badge) badge.textContent = "LISTENING";
  } else if (state === "speaking") {
    stage.classList.add("speaking");
    statusEl.classList.add("speaking");
    statusText.textContent = "SPEAKING";
    if (helmet) helmet.classList.add("speaking");
    if (badge) badge.textContent = "SPEAKING";
  } else if (state === "thinking") {
    stage.classList.add("listening");
    statusEl.classList.add("listening");
    statusText.textContent = "PROCESSING";
    if (badge) badge.textContent = "PROCESSING";
  } else {
    statusText.textContent = "ONLINE";
    if (badge) badge.textContent = "READY";
  }
}

export function initVisualizerAndParticles() {
  const waveCanvas = document.getElementById("topWaveform");
  const pCanvas = document.getElementById("reactorParticles");
  const wCtx = waveCanvas ? waveCanvas.getContext("2d") : null;
  const pCtx = pCanvas ? pCanvas.getContext("2d") : null;

  const particles = Array.from({ length: 42 }, (_, idx) => ({
    angle: (Math.PI * 2 * idx) / 42,
    radius: 145 + (idx % 5) * 18,
    speed: (0.002 + (idx % 4) * 0.0012) * (idx % 2 === 0 ? 1 : -1),
    size: 1.2 + (idx % 3) * 0.8,
    alpha: 0.35 + (idx % 4) * 0.14,
  }));

  let t = 0;

  function renderFrame() {
    t += 0.06;

    // 1. Topbar cyan audio waveform
    if (wCtx && waveCanvas) {
      const w = waveCanvas.width;
      const h = waveCanvas.height;
      wCtx.clearRect(0, 0, w, h);

      const bars = 36;
      const step = w / bars;
      const ampScale =
        coreState === "speaking" ? 1.0 : coreState === "listening" ? 0.78 : 0.36;

      for (let i = 0; i < bars; i++) {
        const norm = Math.sin((i / (bars - 1)) * Math.PI);
        const wave =
          Math.abs(Math.sin(t * 1.9 + i * 0.48) * Math.cos(t * 0.85 - i * 0.22));
        const barH = Math.max(3, norm * (6 + wave * 26 * ampScale));
        const x = i * step + 1;
        const y = (h - barH) / 2;

        const grad = wCtx.createLinearGradient(0, y, 0, y + barH);
        grad.addColorStop(0, "#7cf3ff");
        grad.addColorStop(0.5, "#00e5ff");
        grad.addColorStop(1, "#0077ff");
        wCtx.fillStyle = grad;
        wCtx.fillRect(x, y, Math.max(2, step - 2), barH);
      }
    }

    // 2. Orbital particles around the Arc Reactor
    if (pCtx && pCanvas) {
      const cw = pCanvas.width;
      const ch = pCanvas.height;
      const cx = cw / 2;
      const cy = ch / 2;
      pCtx.clearRect(0, 0, cw, ch);

      const mult = coreState === "listening" || coreState === "speaking" ? 2.4 : 1.0;
      for (const p of particles) {
        p.angle += p.speed * mult;
        const wobble = Math.sin(t + p.angle * 3) * 4;
        const x = cx + Math.cos(p.angle) * (p.radius + wobble);
        const y = cy + Math.sin(p.angle) * (p.radius + wobble);

        pCtx.beginPath();
        pCtx.arc(x, y, p.size, 0, Math.PI * 2);
        pCtx.fillStyle = `rgba(0, 229, 255, ${p.alpha})`;
        pCtx.fill();
      }
    }

    requestAnimationFrame(renderFrame);
  }

  requestAnimationFrame(renderFrame);
}
