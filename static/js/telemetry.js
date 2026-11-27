/**
 * Live Windows system telemetry gauges, network sparkline, and weather info.
 */

const CIRCUMFERENCE = 2 * Math.PI * 40; // r=40 => 251.327
const netHistory = Array(28).fill(0.2);

function setRingValue(circleId, textId, percent) {
  const circle = document.getElementById(circleId);
  const label = document.getElementById(textId);
  const clamped = Math.max(0, Math.min(100, Number(percent) || 0));
  if (circle) {
    const offset = CIRCUMFERENCE * (1 - clamped / 100);
    circle.style.strokeDasharray = `${CIRCUMFERENCE}`;
    circle.style.strokeDashoffset = `${offset}`;
  }
  if (label) {
    label.textContent = `${Math.round(clamped)}%`;
  }
}

function drawNetworkSparkline() {
  const canvas = document.getElementById("networkSparkline");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  // Subtle grid lines
  ctx.strokeStyle = "rgba(0, 229, 255, 0.12)";
  ctx.lineWidth = 1;
  for (let y = 14; y < h; y += 14) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  }

  const maxVal = Math.max(2, ...netHistory);
  const stepX = w / (netHistory.length - 1);

  ctx.beginPath();
  netHistory.forEach((val, i) => {
    const x = i * stepX;
    const y = h - 4 - (val / maxVal) * (h - 10);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });

  ctx.strokeStyle = "#22f58a";
  ctx.lineWidth = 2;
  ctx.stroke();

  // Fill gradient under curve
  ctx.lineTo(w, h);
  ctx.lineTo(0, h);
  ctx.closePath();
  const grad = ctx.createLinearGradient(0, 0, 0, h);
  grad.addColorStop(0, "rgba(34, 245, 138, 0.42)");
  grad.addColorStop(1, "rgba(0, 229, 255, 0.02)");
  ctx.fillStyle = grad;
  ctx.fill();
}

export async function pollTelemetry() {
  try {
    const res = await fetch("/api/telemetry");
    if (!res.ok) return;
    const data = await res.json();

    setRingValue("ringCpu", "valCpu", data.cpu?.percent);
    setRingValue("ringRam", "valRam", data.ram?.percent);
    setRingValue("ringDisk", "valDisk", data.disk?.percent);

    const sub = document.getElementById("sysSubline");
    if (sub && data.ram && data.disk) {
      sub.textContent = `${data.cpu.cores} Cores • RAM ${data.ram.used_gb}/${data.ram.total_gb} GB • ${data.disk.drive} ${data.disk.used_gb}/${data.disk.total_gb} GB`;
    }

    const uptime = document.getElementById("hostUptime");
    if (uptime && data.host) uptime.textContent = `UP ${data.host.uptime}`;

    const hostMeta = document.getElementById("hostNameMeta");
    if (hostMeta && data.host) hostMeta.textContent = data.host.hostname;

    const down = Number(data.network?.download_mbps ?? 0);
    const up = Number(data.network?.upload_mbps ?? 0);

    const downEl = document.getElementById("netDown");
    const upEl = document.getElementById("netUp");
    if (downEl) downEl.textContent = `${down.toFixed(1)} Mbps`;
    if (upEl) upEl.textContent = `${up.toFixed(1)} Mbps`;

    netHistory.push(Math.max(0.15, down + up));
    if (netHistory.length > 28) netHistory.shift();
    drawNetworkSparkline();
  } catch {
    // Keep HUD resilient if backend restarts
  }
}

export async function refreshWeather() {
  try {
    const res = await fetch("/api/weather");
    if (!res.ok) return;
    const w = await res.json();

    const tempEl = document.getElementById("weatherTemp");
    const condEl = document.getElementById("weatherCond");
    const iconEl = document.getElementById("weatherIcon");
    const cityEl = document.getElementById("locCity");
    const countryEl = document.getElementById("locCountry");

    if (tempEl) tempEl.textContent = `${w.temp_c}°C`;
    if (condEl) condEl.textContent = w.condition;
    if (cityEl) cityEl.textContent = w.city;
    if (countryEl) countryEl.textContent = w.country;
    if (iconEl) {
      const icons = { sun: "☀", "cloud-sun": "⛅", cloud: "☁", rain: "🌧", storm: "⛈" };
      iconEl.textContent = icons[w.icon] || "☀";
    }
  } catch {
    // Ignore transient weather fetch errors
  }
}

export function startTelemetryLoop() {
  pollTelemetry();
  refreshWeather();
  setInterval(pollTelemetry, 1800);
  setInterval(refreshWeather, 10 * 60 * 1000);
}
