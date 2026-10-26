#!/opt/bin/python3
# -*- coding: utf-8 -*-
"""
🎨 Yandex Station 2 / Midi — Web LED Studio
Interactive Real-Time RGBW Graphic Editor & Animation Engine for /dev/fb0
"""

import os
import sys
import time
import json
import mmap
import fcntl
import struct
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 8080
LED_COUNT = 89
BYTES_PER_FRAME = LED_COUNT * 4  # 356 bytes

class LEDController:
    def __init__(self):
        self.lock = threading.Lock()
        self.fb_file = None
        self.fb_mm = None
        self.fb_var = bytearray(160)
        struct.pack_into("II", self.fb_var, 0, LED_COUNT, 1)
        self.pixels = [[0, 0, 0, 0] for _ in range(LED_COUNT)]  # [R, G, B, W]
        self.active_fx = None
        self.fx_thread = None
        self.fx_stop = threading.Event()

        try:
            self.fb_file = open("/dev/fb0", "r+b")
            self.fb_mm = mmap.mmap(self.fb_file.fileno(), BYTES_PER_FRAME)
        except Exception as e:
            print(f"Warning: /dev/fb0 open failed: {e}")

    def update_hardware(self):
        if self.fb_mm is None or self.fb_file is None:
            return
        buf = bytearray()
        for r, g, b, w in self.pixels:
            # Native format: Little-endian 32-bit (B, G, R, W)
            buf.extend(bytes([
                max(0, min(255, int(b))),
                max(0, min(255, int(g))),
                max(0, min(255, int(r))),
                max(0, min(255, int(w)))
            ]))
        with self.lock:
            self.fb_mm[:] = buf
            try:
                fcntl.ioctl(self.fb_file.fileno(), 0x4606, self.fb_var)
            except Exception:
                pass

    def set_pixel(self, index, r, g, b, w=0):
        if 0 <= index < LED_COUNT:
            self.stop_fx()
            self.pixels[index] = [r, g, b, w]
            self.update_hardware()

    def set_frame(self, frame_data):
        self.stop_fx()
        for i in range(min(LED_COUNT, len(frame_data))):
            item = frame_data[i]
            r = item.get("r", 0)
            g = item.get("g", 0)
            b = item.get("b", 0)
            w = item.get("w", 0)
            self.pixels[i] = [r, g, b, w]
        self.update_hardware()

    def fill_all(self, r, g, b, w=0):
        self.stop_fx()
        for i in range(LED_COUNT):
            self.pixels[i] = [r, g, b, w]
        self.update_hardware()

    def clear(self):
        self.fill_all(0, 0, 0, 0)

    def stop_fx(self):
        if self.fx_thread and self.fx_thread.is_alive():
            self.fx_stop.set()
            self.fx_thread.join(timeout=0.5)
        self.active_fx = None

    def start_fx(self, fx_name):
        self.stop_fx()
        self.fx_stop.clear()
        self.active_fx = fx_name

        def fx_worker():
            t = 0.0
            import math
            while not self.fx_stop.is_set():
                if fx_name == "rainbow":
                    for i in range(LED_COUNT):
                        hue = (t * 0.5 + i / LED_COUNT) % 1.0
                        # Simple HSV to RGB
                        r, g, b = hsv_to_rgb(hue, 1.0, 1.0)
                        self.pixels[i] = [int(r*255), int(g*255), int(b*255), 0]
                elif fx_name == "candle":
                    import random
                    base_r, base_g = 255, 60
                    for i in range(LED_COUNT):
                        flicker = random.randint(-25, 25)
                        rr = max(0, min(255, base_r + flicker))
                        gg = max(0, min(255, base_g + flicker // 2))
                        self.pixels[i] = [rr, gg, 0, 10]
                elif fx_name == "pulse":
                    val = int((math.sin(t * 3.0) + 1.0) * 0.5 * 255)
                    for i in range(LED_COUNT):
                        # Alice purple
                        self.pixels[i] = [int(val * 0.6), 0, val, 0]
                elif fx_name == "police":
                    step = int(t * 4) % 2
                    for i in range(LED_COUNT):
                        if (i < 45 and step == 0) or (i >= 45 and step == 1):
                            self.pixels[i] = [255, 0, 0, 0] if i < 45 else [0, 0, 255, 0]
                        else:
                            self.pixels[i] = [0, 0, 0, 0]
                self.update_hardware()
                time.sleep(0.04)
                t += 0.04

        self.fx_thread = threading.Thread(target=fx_worker, daemon=True)
        self.fx_thread.start()

def hsv_to_rgb(h, s, v):
    import math
    i = math.floor(h * 6)
    f = h * 6 - i
    p = v * (1 - s)
    q = v * (1 - f * s)
    t = v * (1 - (1 - f) * s)
    r, g, b = [
        (v, t, p),
        (q, v, p),
        (p, v, t),
        (p, q, v),
        (t, p, v),
        (v, p, q)
    ][int(i % 6)]
    return r, g, b

controller = LEDController()

HTML_PAGE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>🎨 Станция 2 — LED Studio</title>
<style>
:root {
  --bg: #0f111a;
  --card-bg: #181b28;
  --accent: #8b5cf6;
  --accent-glow: rgba(139, 92, 246, 0.4);
  --text: #f3f4f6;
  --text-muted: #9ca3af;
  --border: #2e344e;
}
* { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  background-color: var(--bg);
  color: var(--text);
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16px;
  user-select: none;
}
header {
  text-align: center;
  margin-bottom: 20px;
}
header h1 {
  font-size: 24px;
  font-weight: 700;
  background: linear-gradient(135deg, #a78bfa, #ec4899);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  margin-bottom: 4px;
}
header p {
  font-size: 13px;
  color: var(--text-muted);
}
.main-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
  width: 100%;
  max-width: 540px;
}
.panel-card {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 16px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.3);
}
.canvas-wrapper {
  position: relative;
  width: 100%;
  aspect-ratio: 1 / 1;
  max-width: 440px;
  margin: 0 auto;
  display: flex;
  justify-content: center;
  align-items: center;
}
#ledCanvas {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background: radial-gradient(circle at center, #1e2235 0%, #131622 100%);
  border: 2px solid #333a56;
  box-shadow: inset 0 0 20px rgba(0,0,0,0.6), 0 0 30px rgba(139, 92, 246, 0.1);
  cursor: crosshair;
  touch-action: none;
}
.controls-grid {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.palette-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  justify-content: center;
}
.color-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: 2px solid rgba(255,255,255,0.2);
  cursor: pointer;
  transition: transform 0.15s, border-color 0.15s;
}
.color-btn.active {
  transform: scale(1.15);
  border-color: #fff;
  box-shadow: 0 0 12px var(--btn-color);
}
.custom-picker-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #24293e;
  padding: 4px 10px;
  border-radius: 20px;
}
input[type="color"] {
  appearance: none;
  border: none;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  cursor: pointer;
  background: none;
}
input[type="color"]::-webkit-color-swatch-wrapper { padding: 0; }
input[type="color"]::-webkit-color-swatch { border-radius: 50%; border: 1px solid #fff; }
.tool-btn-group {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}
.btn {
  background: #24293e;
  color: var(--text);
  border: 1px solid var(--border);
  padding: 10px 12px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}
.btn:hover {
  background: #313854;
  border-color: #4b557c;
}
.btn:active {
  transform: scale(0.97);
}
.btn.danger {
  background: rgba(239, 68, 68, 0.15);
  border-color: rgba(239, 68, 68, 0.4);
  color: #fca5a5;
}
.btn.danger:hover {
  background: rgba(239, 68, 68, 0.25);
}
.slider-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.slider-row {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
}
.slider-row span:first-child { width: 90px; color: var(--text-muted); }
.slider-row input[type="range"] {
  flex: 1;
  accent-color: var(--accent);
}
.slider-val { width: 35px; text-align: right; font-family: monospace; }
.fx-title {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  margin-top: 4px;
}
.fx-group {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}
.status-bar {
  text-align: center;
  font-size: 12px;
  color: #10b981;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #10b981;
  box-shadow: 0 0 8px #10b981;
}
</style>
</head>
<body>

<header>
  <h1>🎨 Yandex Station 2 — LED Studio</h1>
  <p>Интерактивный графический редактор для светодиодной панели (89 RGBW LEDs)</p>
</header>

<div class="main-container">
  <div class="panel-card">
    <div class="canvas-wrapper">
      <canvas id="ledCanvas" width="440" height="440"></canvas>
    </div>
  </div>

  <div class="panel-card controls-grid">
    <div class="palette-row" id="palette">
      <div class="color-btn active" style="background:#ff0033; --btn-color:#ff0033;" data-color="#ff0033"></div>
      <div class="color-btn" style="background:#00ff66; --btn-color:#00ff66;" data-color="#00ff66"></div>
      <div class="color-btn" style="background:#0088ff; --btn-color:#0088ff;" data-color="#0088ff"></div>
      <div class="color-btn" style="background:#a855f7; --btn-color:#a855f7;" data-color="#a855f7"></div>
      <div class="color-btn" style="background:#00ffff; --btn-color:#00ffff;" data-color="#00ffff"></div>
      <div class="color-btn" style="background:#fbbf24; --btn-color:#fbbf24;" data-color="#fbbf24"></div>
      <div class="color-btn" style="background:#ffffff; --btn-color:#ffffff;" data-color="#ffffff"></div>
      <div class="color-btn" style="background:#111827; border-color:#666; --btn-color:#fff;" data-color="#000000" title="Ластик"></div>
      <div class="custom-picker-wrap">
        <input type="color" id="customColor" value="#ff0033">
        <span style="font-size:12px;">Свой</span>
      </div>
    </div>

    <div class="slider-group">
      <div class="slider-row">
        <span>Яркость:</span>
        <input type="range" id="brightness" min="5" max="100" value="100">
        <span class="slider-val" id="brightVal">100%</span>
      </div>
      <div class="slider-row">
        <span>White LED:</span>
        <input type="range" id="whiteLed" min="0" max="255" value="0">
        <span class="slider-val" id="whiteVal">0</span>
      </div>
    </div>

    <div class="tool-btn-group">
      <button class="btn" id="btnFill">🪣 Залить всё</button>
      <button class="btn danger" id="btnClear">🧹 Очистить</button>
      <button class="btn" id="btnMode">🔄 Раскладка</button>
      <button class="btn" id="btnExport">💾 Скачать .led</button>
    </div>

    <div class="fx-title">Эффекты и анимация</div>
    <div class="fx-group">
      <button class="btn" onclick="startFx('rainbow')">🌈 Радуга</button>
      <button class="btn" onclick="startFx('candle')">🕯️ Свеча</button>
      <button class="btn" onclick="startFx('pulse')">💜 Пульс</button>
      <button class="btn" onclick="startFx('police')">🚨 Полиция</button>
    </div>

    <div class="status-bar">
      <div class="status-dot"></div>
      <span id="statusText">Подключено к Станции (Live Sync 0ms)</span>
    </div>
  </div>
</div>

<script>
const TOTAL_LEDS = 89;
const canvas = document.getElementById('ledCanvas');
const ctx = canvas.getContext('2d');
let currentColor = '#ff0033';
let brightnessPct = 1.0;
let whiteIntensity = 0;
let isPainting = false;
let layoutMode = 'circle'; // 'circle' or 'grid'

// 89 LEDs state: [{r, g, b, w}]
const ledState = Array.from({length: TOTAL_LEDS}, () => ({r: 0, g: 0, b: 0, w: 0}));

// Calculate LED physical coordinates on canvas (440 x 440)
const ledPositions = [];
function computePositions() {
  ledPositions.length = 0;
  const cx = 220, cy = 220;
  
  if (layoutMode === 'circle') {
    // Outer ring: 34 leds (indices 0..33)
    const r1 = 175;
    for (let i = 0; i < 34; i++) {
      const angle = (i / 34) * Math.PI * 2 - Math.PI / 2;
      ledPositions.push({
        x: cx + r1 * Math.cos(angle),
        y: cy + r1 * Math.sin(angle),
        radius: 10,
        idx: i
      });
    }
    // Ring 2: 24 leds (indices 34..57)
    const r2 = 125;
    for (let i = 0; i < 24; i++) {
      const angle = (i / 24) * Math.PI * 2 - Math.PI / 2;
      ledPositions.push({
        x: cx + r2 * Math.cos(angle),
        y: cy + r2 * Math.sin(angle),
        radius: 9,
        idx: 34 + i
      });
    }
    // Ring 3: 18 leds (indices 58..75)
    const r3 = 78;
    for (let i = 0; i < 18; i++) {
      const angle = (i / 18) * Math.PI * 2 - Math.PI / 2;
      ledPositions.push({
        x: cx + r3 * Math.cos(angle),
        y: cy + r3 * Math.sin(angle),
        radius: 8.5,
        idx: 58 + i
      });
    }
    // Ring 4: 12 leds (indices 76..87)
    const r4 = 38;
    for (let i = 0; i < 12; i++) {
      const angle = (i / 12) * Math.PI * 2 - Math.PI / 2;
      ledPositions.push({
        x: cx + r4 * Math.cos(angle),
        y: cy + r4 * Math.sin(angle),
        radius: 7.5,
        idx: 76 + i
      });
    }
    // Center: 1 led (index 88)
    ledPositions.push({
      x: cx,
      y: cy,
      radius: 8,
      idx: 88
    });
  } else {
    // Grid mode: 10 x 9
    const cols = 10, rows = 9;
    const startX = 40, startY = 40;
    const stepX = 40, stepY = 44;
    for (let i = 0; i < TOTAL_LEDS; i++) {
      const row = Math.floor(i / cols);
      const col = i % cols;
      ledPositions.push({
        x: startX + col * stepX,
        y: startY + row * stepY,
        radius: 12,
        idx: i
      });
    }
  }
}
computePositions();

function renderCanvas() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  for (let i = 0; i < ledPositions.length; i++) {
    const p = ledPositions[i];
    const s = ledState[i];
    const hasColor = s.r > 0 || s.g > 0 || s.b > 0 || s.w > 0;
    
    // Outer glow
    if (hasColor) {
      const grad = ctx.createRadialGradient(p.x, p.y, p.radius * 0.5, p.x, p.y, p.radius * 2.2);
      grad.addColorStop(0, `rgba(${s.r}, ${s.g}, ${s.b}, 0.8)`);
      grad.addColorStop(1, `rgba(${s.r}, ${s.g}, ${s.b}, 0)`);
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.radius * 2.2, 0, Math.PI * 2);
      ctx.fill();
    }

    // LED Body
    ctx.beginPath();
    ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
    if (hasColor) {
      ctx.fillStyle = `rgb(${s.r}, ${s.g}, ${s.b})`;
    } else {
      ctx.fillStyle = '#1c2032';
    }
    ctx.fill();
    ctx.lineWidth = 1.5;
    ctx.strokeStyle = hasColor ? '#ffffff88' : '#2e354e';
    ctx.stroke();

    // Small index label
    ctx.fillStyle = hasColor ? '#ffffffcc' : '#4b557c';
    ctx.font = '8px monospace';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(i, p.x, p.y);
  }
}
renderCanvas();

// Live API Sync
let syncTimeout = null;
function syncToStation(immediate = false) {
  if (syncTimeout) clearTimeout(syncTimeout);
  
  const send = () => {
    fetch('/api/frame', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(ledState)
    }).catch(e => console.error(e));
  };

  if (immediate) {
    send();
  } else {
    syncTimeout = setTimeout(send, 25);
  }
}

function hexToRgb(hex) {
  const bigint = parseInt(hex.slice(1), 16);
  return {
    r: Math.round(((bigint >> 16) & 255) * brightnessPct),
    g: Math.round(((bigint >> 8) & 255) * brightnessPct),
    b: Math.round((bigint & 255) * brightnessPct)
  };
}

function paintAt(x, y) {
  for (let i = 0; i < ledPositions.length; i++) {
    const p = ledPositions[i];
    const dist = Math.hypot(p.x - x, p.y - y);
    if (dist <= p.radius * 1.8) {
      const rgb = hexToRgb(currentColor);
      ledState[i] = {
        r: rgb.r,
        g: rgb.g,
        b: rgb.b,
        w: parseInt(whiteIntensity)
      };
      renderCanvas();
      syncToStation();
      break;
    }
  }
}

function getCoords(e) {
  const rect = canvas.getBoundingClientRect();
  const scaleX = canvas.width / rect.width;
  const scaleY = canvas.height / rect.height;
  const clientX = e.touches ? e.touches[0].clientX : e.clientX;
  const clientY = e.touches ? e.touches[0].clientY : e.clientY;
  return {
    x: (clientX - rect.left) * scaleX,
    y: (clientY - rect.top) * scaleY
  };
}

// Mouse and Touch Event Listeners
canvas.addEventListener('mousedown', (e) => {
  isPainting = true;
  const pos = getCoords(e);
  paintAt(pos.x, pos.y);
});
window.addEventListener('mousemove', (e) => {
  if (!isPainting) return;
  const pos = getCoords(e);
  paintAt(pos.x, pos.y);
});
window.addEventListener('mouseup', () => { isPainting = false; });

canvas.addEventListener('touchstart', (e) => {
  e.preventDefault();
  isPainting = true;
  const pos = getCoords(e);
  paintAt(pos.x, pos.y);
}, {passive: false});

canvas.addEventListener('touchmove', (e) => {
  e.preventDefault();
  if (!isPainting) return;
  const pos = getCoords(e);
  paintAt(pos.x, pos.y);
}, {passive: false});

window.addEventListener('touchend', () => { isPainting = false; });

// Palette selection
document.querySelectorAll('.color-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.color-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentColor = btn.dataset.color;
  });
});

const customPicker = document.getElementById('customColor');
customPicker.addEventListener('input', (e) => {
  currentColor = e.target.value;
  document.querySelectorAll('.color-btn').forEach(b => b.classList.remove('active'));
});

// Sliders
document.getElementById('brightness').addEventListener('input', (e) => {
  brightnessPct = e.target.value / 100.0;
  document.getElementById('brightVal').innerText = `${e.target.value}%`;
});

document.getElementById('whiteLed').addEventListener('input', (e) => {
  whiteIntensity = e.target.value;
  document.getElementById('whiteVal').innerText = e.target.value;
});

// Action buttons
document.getElementById('btnClear').addEventListener('click', () => {
  for (let i = 0; i < TOTAL_LEDS; i++) {
    ledState[i] = {r: 0, g: 0, b: 0, w: 0};
  }
  renderCanvas();
  fetch('/api/clear', {method: 'POST'});
});

document.getElementById('btnFill').addEventListener('click', () => {
  const rgb = hexToRgb(currentColor);
  for (let i = 0; i < TOTAL_LEDS; i++) {
    ledState[i] = {r: rgb.r, g: rgb.g, b: rgb.b, w: parseInt(whiteIntensity)};
  }
  renderCanvas();
  syncToStation(true);
});

document.getElementById('btnMode').addEventListener('click', () => {
  layoutMode = (layoutMode === 'circle') ? 'grid' : 'circle';
  computePositions();
  renderCanvas();
});

document.getElementById('btnExport').addEventListener('click', () => {
  let hexLine = "";
  for (let i = 0; i < TOTAL_LEDS; i++) {
    const s = ledState[i];
    const r = s.r.toString(16).padStart(2, '0');
    const g = s.g.toString(16).padStart(2, '0');
    const b = s.b.toString(16).padStart(2, '0');
    const w = s.w.toString(16).padStart(2, '0');
    hexLine += `${r}${g}${b}${w} `;
  }
  hexLine += "20\n";
  const blob = new Blob([hexLine], {type: "text/plain"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "custom_pattern.led";
  a.click();
});

function startFx(name) {
  fetch('/api/fx', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({fx: name})
  });
}
</script>
</body>
</html>
"""

class RequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Quiet logging

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
        elif self.path == "/api/state":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(controller.pixels).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(content_len) if content_len > 0 else b""

        if self.path == "/api/frame":
            try:
                frame_data = json.loads(post_body.decode("utf-8"))
                controller.set_frame(frame_data)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"OK")
            except Exception as e:
                self.send_response(400)
                self.end_headers()
        elif self.path == "/api/clear":
            controller.clear()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        elif self.path == "/api/fx":
            try:
                data = json.loads(post_body.decode("utf-8"))
                fx = data.get("fx")
                if fx:
                    controller.start_fx(fx)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"OK")
            except Exception:
                self.send_response(400)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

def main():
    print(f"[*] Запуск LED Studio Web Server на порту {PORT}...")
    server = HTTPServer(("0.0.0.0", PORT), RequestHandler)
    print(f"[*] Сервер готов: http://0.0.0.0:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        controller.clear()

if __name__ == "__main__":
    main()
