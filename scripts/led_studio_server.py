#!/opt/bin/python3
# -*- coding: utf-8 -*-
"""
🎨 Yandex Station 2 — Pixel Grid LED Studio v3
DOM Grid + Pointer Events (Mouse/Touch Drag) + Real-Time Sync + /dev/fb0 30 FPS Render Loop
"""

import os
import sys
import time
import json
import mmap
import fcntl
import struct
import math
import random
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
        self.pixels = [[0, 0, 0, 0] for _ in range(LED_COUNT)]  # [R, G, B, W]
        self.active_fx = None
        self.running = True

        try:
            self.fb_file = open("/dev/fb0", "r+b")
            fcntl.ioctl(self.fb_file.fileno(), 0x4600, self.fb_var)  # FBIOGET_VSCREENINFO
            self.fb_mm = mmap.mmap(self.fb_file.fileno(), 4096)
            print("[*] Framebuffer /dev/fb0 initialized successfully")
        except Exception as e:
            print(f"[!] Warning: /dev/fb0 open failed: {e}")

        self.render_thread = threading.Thread(target=self._render_loop, daemon=True)
        self.render_thread.start()

    def _render_loop(self):
        t = 0.0
        while self.running:
            try:
                if self.active_fx:
                    self._update_fx(self.active_fx, t)
                    t += 0.033

                if self.fb_mm is not None and self.fb_file is not None:
                    buf = bytearray()
                    with self.lock:
                        for r, g, b, w in self.pixels:
                            # Hardware format: B, G, R, W
                            buf.extend(bytes([
                                max(0, min(255, int(b))),
                                max(0, min(255, int(g))),
                                max(0, min(255, int(r))),
                                max(0, min(255, int(w)))
                            ]))
                    self.fb_mm[:BYTES_PER_FRAME] = buf
                    try:
                        fcntl.ioctl(self.fb_file.fileno(), 0x4606, self.fb_var)
                    except Exception:
                        pass
            except Exception as e:
                pass
            time.sleep(0.033)

    def _update_fx(self, fx_name, t):
        with self.lock:
            if fx_name == "rainbow":
                for i in range(LED_COUNT):
                    hue = (t * 0.8 + i / LED_COUNT) % 1.0
                    r = int((math.sin(hue * 6.28) + 1.0) * 0.5 * 255)
                    g = int((math.sin(hue * 6.28 + 2.09) + 1.0) * 0.5 * 255)
                    b = int((math.sin(hue * 6.28 + 4.18) + 1.0) * 0.5 * 255)
                    self.pixels[i] = [r, g, b, 0]
            elif fx_name == "candle":
                base_r, base_g = 255, 60
                for i in range(LED_COUNT):
                    flicker = random.randint(-30, 30)
                    rr = max(0, min(255, base_r + flicker))
                    gg = max(0, min(255, base_g + flicker // 2))
                    self.pixels[i] = [rr, gg, 0, 15]
            elif fx_name == "pulse":
                val = int((math.sin(t * 3.5) + 1.0) * 0.5 * 255)
                for i in range(LED_COUNT):
                    self.pixels[i] = [int(val * 0.65), 0, val, 0]
            elif fx_name == "police":
                step = int(t * 5) % 2
                for i in range(LED_COUNT):
                    if (i < 45 and step == 0) or (i >= 45 and step == 1):
                        self.pixels[i] = [255, 0, 0, 0] if i < 45 else [0, 0, 255, 0]
                    else:
                        self.pixels[i] = [0, 0, 0, 0]

    def set_pixel(self, index, r, g, b, w=0):
        self.active_fx = None
        if 0 <= index < LED_COUNT:
            with self.lock:
                self.pixels[index] = [r, g, b, w]

    def set_frame(self, frame_data):
        self.active_fx = None
        with self.lock:
            for i in range(min(LED_COUNT, len(frame_data))):
                item = frame_data[i]
                r = item.get("r", 0)
                g = item.get("g", 0)
                b = item.get("b", 0)
                w = item.get("w", 0)
                self.pixels[i] = [r, g, b, w]

    def fill_all(self, r, g, b, w=0):
        self.active_fx = None
        with self.lock:
            for i in range(LED_COUNT):
                self.pixels[i] = [r, g, b, w]

    def clear(self):
        self.fill_all(0, 0, 0, 0)

    def start_fx(self, fx_name):
        self.active_fx = fx_name

    def stop_fx(self):
        self.active_fx = None

controller = LEDController()

HTML_PAGE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>🎨 Станция 2 — Pixel Grid Studio</title>
<style>
:root {
  --bg: #0b0d14;
  --card-bg: #141724;
  --accent: #8b5cf6;
  --text: #f3f4f6;
  --text-muted: #9ca3af;
  --border: #24293e;
}
* { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
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
  margin-bottom: 16px;
}
header h1 {
  font-size: 22px;
  font-weight: 700;
  background: linear-gradient(135deg, #a78bfa, #f43f5e);
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
  gap: 14px;
  width: 100%;
  max-width: 540px;
}
.panel-card {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 16px;
  box-shadow: 0 8px 30px rgba(0,0,0,0.4);
}
/* GRID STYLES */
.grid-container {
  display: grid;
  grid-template-columns: repeat(10, 1fr);
  gap: 6px;
  width: 100%;
  margin: 0 auto;
  touch-action: none;
}
.led-cell {
  aspect-ratio: 1 / 1;
  border-radius: 8px;
  background-color: #1a1e30;
  border: 1.5px solid #2d3450;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-family: monospace;
  color: #4b557c;
  cursor: pointer;
  transition: transform 0.1s, box-shadow 0.1s;
  position: relative;
}
.led-cell:hover {
  border-color: #fff;
  transform: scale(1.08);
  z-index: 2;
}
.led-cell.active-color {
  color: #ffffff;
  border-color: rgba(255, 255, 255, 0.8);
  box-shadow: 0 0 10px var(--glow-col);
}
/* CIRCLE PANEL VIEW */
.canvas-wrapper {
  position: relative;
  width: 100%;
  aspect-ratio: 1 / 1;
  max-width: 420px;
  margin: 0 auto;
  display: none;
  justify-content: center;
  align-items: center;
}
#ledCanvas {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background: radial-gradient(circle at center, #181c2d 0%, #0d0f18 100%);
  border: 2px solid #2e354e;
  cursor: crosshair;
}

.palette-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  justify-content: center;
  margin-bottom: 12px;
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
  transform: scale(1.18);
  border-color: #fff;
  box-shadow: 0 0 12px var(--btn-color);
}
.custom-picker-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
  background: #1e2338;
  padding: 4px 10px;
  border-radius: 20px;
}
input[type="color"] {
  appearance: none;
  border: none;
  width: 26px;
  height: 26px;
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
  margin-bottom: 12px;
}
.btn {
  background: #1e2338;
  color: var(--text);
  border: 1px solid var(--border);
  padding: 10px 8px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}
.btn:hover { background: #2b324e; border-color: #4b557c; }
.btn:active { transform: scale(0.96); }
.btn.danger {
  background: rgba(239, 68, 68, 0.15);
  border-color: rgba(239, 68, 68, 0.4);
  color: #fca5a5;
}
.btn.danger:hover { background: rgba(239, 68, 68, 0.25); }
.slider-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}
.slider-row {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
}
.slider-row span:first-child { width: 80px; color: var(--text-muted); }
.slider-row input[type="range"] { flex: 1; accent-color: var(--accent); }
.slider-val { width: 35px; text-align: right; font-family: monospace; }
.fx-title {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  margin-bottom: 6px;
}
.fx-group {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  margin-bottom: 12px;
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
  <h1>🎨 Станция 2 — Pixel Grid Studio</h1>
  <p>Интерактивная сетка 89 светодиодов (кликай и закрашивай)</p>
</header>

<div class="main-container">
  <div class="panel-card">
    <!-- GRID VIEW (DEFAULT) -->
    <div class="grid-container" id="ledGrid"></div>
    <!-- CIRCLE VIEW (OPTIONAL) -->
    <div class="canvas-wrapper" id="canvasWrapper">
      <canvas id="ledCanvas" width="420" height="420"></canvas>
    </div>
  </div>

  <div class="panel-card">
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
      <button class="btn" id="btnToggleView">🔄 Круг / Сетка</button>
      <button class="btn" id="btnExport">💾 Скачать</button>
    </div>

    <div class="fx-title">Эффекты</div>
    <div class="fx-group">
      <button class="btn" onclick="startFx('rainbow')">🌈 Радуга</button>
      <button class="btn" onclick="startFx('candle')">🕯️ Свеча</button>
      <button class="btn" onclick="startFx('pulse')">💜 Пульс</button>
      <button class="btn" onclick="startFx('police')">🚨 Полиция</button>
    </div>

    <div class="status-bar">
      <div class="status-dot"></div>
      <span id="statusText">Подключено (30 FPS Hardware Loop)</span>
    </div>
  </div>
</div>

<script>
const TOTAL_LEDS = 89;
const gridContainer = document.getElementById('ledGrid');
const canvasWrapper = document.getElementById('canvasWrapper');
const canvas = document.getElementById('ledCanvas');
const ctx = canvas.getContext('2d');

let currentColor = '#ff0033';
let brightnessPct = 1.0;
let whiteIntensity = 0;
let isPointerDown = false;
let currentView = 'grid'; // 'grid' or 'circle'

const ledState = Array.from({length: TOTAL_LEDS}, () => ({r: 0, g: 0, b: 0, w: 0}));
const gridCells = [];

// Build Grid DOM elements
for (let i = 0; i < TOTAL_LEDS; i++) {
  const cell = document.createElement('div');
  cell.className = 'led-cell';
  cell.id = `led-cell-${i}`;
  cell.dataset.idx = i;
  cell.innerText = i;
  
  // Pointer down (start drag)
  cell.addEventListener('pointerdown', (e) => {
    isPointerDown = true;
    cell.releasePointerCapture(e.pointerId);
    paintCell(i);
  });
  
  // Pointer enter (during drag)
  cell.addEventListener('pointerenter', () => {
    if (isPointerDown) {
      paintCell(i);
    }
  });

  gridContainer.appendChild(cell);
  gridCells.push(cell);
}

// Global pointer up
window.addEventListener('pointerup', () => { isPointerDown = false; });
window.addEventListener('pointercancel', () => { isPointerDown = false; });

function hexToRgb(hex) {
  const bigint = parseInt(hex.slice(1), 16);
  return {
    r: Math.round(((bigint >> 16) & 255) * brightnessPct),
    g: Math.round(((bigint >> 8) & 255) * brightnessPct),
    b: Math.round((bigint & 255) * brightnessPct)
  };
}

function paintCell(idx) {
  const rgb = hexToRgb(currentColor);
  ledState[idx] = { r: rgb.r, g: rgb.g, b: rgb.b, w: parseInt(whiteIntensity) };
  
  // Update Cell UI
  const cell = gridCells[idx];
  const hasColor = rgb.r > 0 || rgb.g > 0 || rgb.b > 0 || whiteIntensity > 0;
  if (hasColor) {
    cell.style.backgroundColor = `rgb(${rgb.r}, ${rgb.g}, ${rgb.b})`;
    cell.style.setProperty('--glow-col', `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.8)`);
    cell.classList.add('active-color');
  } else {
    cell.style.backgroundColor = '#1a1e30';
    cell.classList.remove('active-color');
  }

  syncToStation();
}

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
    syncTimeout = setTimeout(send, 20);
  }
}

// Palette buttons
document.querySelectorAll('.color-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.color-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentColor = btn.dataset.color;
  });
});

document.getElementById('customColor').addEventListener('input', (e) => {
  currentColor = e.target.value;
  document.querySelectorAll('.color-btn').forEach(b => b.classList.remove('active'));
});

document.getElementById('brightness').addEventListener('input', (e) => {
  brightnessPct = e.target.value / 100.0;
  document.getElementById('brightVal').innerText = `${e.target.value}%`;
});

document.getElementById('whiteLed').addEventListener('input', (e) => {
  whiteIntensity = e.target.value;
  document.getElementById('whiteVal').innerText = e.target.value;
});

document.getElementById('btnClear').addEventListener('click', () => {
  for (let i = 0; i < TOTAL_LEDS; i++) {
    ledState[i] = {r: 0, g: 0, b: 0, w: 0};
    gridCells[i].style.backgroundColor = '#1a1e30';
    gridCells[i].classList.remove('active-color');
  }
  fetch('/api/clear', {method: 'POST'});
});

document.getElementById('btnFill').addEventListener('click', () => {
  const rgb = hexToRgb(currentColor);
  for (let i = 0; i < TOTAL_LEDS; i++) {
    ledState[i] = {r: rgb.r, g: rgb.g, b: rgb.b, w: parseInt(whiteIntensity)};
    const cell = gridCells[i];
    if (rgb.r > 0 || rgb.g > 0 || rgb.b > 0 || whiteIntensity > 0) {
      cell.style.backgroundColor = `rgb(${rgb.r}, ${rgb.g}, ${rgb.b})`;
      cell.style.setProperty('--glow-col', `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.8)`);
      cell.classList.add('active-color');
    } else {
      cell.style.backgroundColor = '#1a1e30';
      cell.classList.remove('active-color');
    }
  }
  syncToStation(true);
});

document.getElementById('btnToggleView').addEventListener('click', () => {
  if (currentView === 'grid') {
    currentView = 'circle';
    gridContainer.style.display = 'none';
    canvasWrapper.style.display = 'flex';
    renderCircleCanvas();
  } else {
    currentView = 'grid';
    gridContainer.style.display = 'grid';
    canvasWrapper.style.display = 'none';
  }
});

// Circle render support
function renderCircleCanvas() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const cx = 210, cy = 210;
  // Outer ring: 34
  for (let i = 0; i < 34; i++) {
    const angle = (i / 34) * Math.PI * 2 - Math.PI / 2;
    const x = cx + 165 * Math.cos(angle);
    const y = cy + 165 * Math.sin(angle);
    drawCircleLed(i, x, y, 9);
  }
  // Ring 2: 24
  for (let i = 0; i < 24; i++) {
    const angle = (i / 24) * Math.PI * 2 - Math.PI / 2;
    const x = cx + 118 * Math.cos(angle);
    const y = cy + 118 * Math.sin(angle);
    drawCircleLed(34 + i, x, y, 8.5);
  }
  // Ring 3: 18
  for (let i = 0; i < 18; i++) {
    const angle = (i / 18) * Math.PI * 2 - Math.PI / 2;
    const x = cx + 74 * Math.cos(angle);
    const y = cy + 74 * Math.sin(angle);
    drawCircleLed(58 + i, x, y, 8);
  }
  // Ring 4: 12
  for (let i = 0; i < 12; i++) {
    const angle = (i / 12) * Math.PI * 2 - Math.PI / 2;
    const x = cx + 36 * Math.cos(angle);
    const y = cy + 36 * Math.sin(angle);
    drawCircleLed(76 + i, x, y, 7);
  }
  // Center
  drawCircleLed(88, cx, cy, 8);
}

function drawCircleLed(i, x, y, rad) {
  const s = ledState[i];
  const hasColor = s.r > 0 || s.g > 0 || s.b > 0 || s.w > 0;
  ctx.beginPath();
  ctx.arc(x, y, rad, 0, Math.PI * 2);
  ctx.fillStyle = hasColor ? `rgb(${s.r}, ${s.g}, ${s.b})` : '#161926';
  ctx.fill();
  ctx.lineWidth = 1.5;
  ctx.strokeStyle = hasColor ? '#ffffff88' : '#272d42';
  ctx.stroke();
  ctx.fillStyle = hasColor ? '#fff' : '#3d4766';
  ctx.font = '7.5px monospace';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(i, x, y);
}

document.getElementById('btnExport').addEventListener('click', () => {
  let hexLine = "";
  for (let i = 0; i < TOTAL_LEDS; i++) {
    const s = ledState[i];
    hexLine += `${s.r.toString(16).padStart(2,'0')}${s.g.toString(16).padStart(2,'0')}${s.b.toString(16).padStart(2,'0')}${s.w.toString(16).padStart(2,'0')} `;
  }
  hexLine += "20\n";
  const blob = new Blob([hexLine], {type: "text/plain"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "pattern.led";
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
    def send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def reply_data(self, data, content_type="text/plain", code=200):
        if isinstance(data, str):
            data = data.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Connection", "close")
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.send_header("Connection", "close")
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/index"):
            self.reply_data(HTML_PAGE, "text/html; charset=utf-8")
        elif self.path == "/api/state":
            with controller.lock:
                state_json = json.dumps(controller.pixels)
            self.reply_data(state_json, "application/json")
        else:
            self.reply_data(b"Not Found", code=404)

    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(content_len) if content_len > 0 else b""

        if self.path == "/api/frame":
            try:
                frame_data = json.loads(post_body.decode("utf-8"))
                controller.set_frame(frame_data)
                self.reply_data(b"OK")
            except Exception as e:
                self.reply_data(f"Error: {e}".encode("utf-8"), code=400)
        elif self.path == "/api/clear":
            controller.clear()
            self.reply_data(b"OK")
        elif self.path == "/api/fx":
            try:
                data = json.loads(post_body.decode("utf-8"))
                fx = data.get("fx")
                if fx:
                    controller.start_fx(fx)
                self.reply_data(b"OK")
            except Exception as e:
                self.reply_data(f"Error: {e}".encode("utf-8"), code=400)
        else:
            self.reply_data(b"Not Found", code=404)

def main():
    print(f"[*] LED Studio v3 starting on port {PORT}...")
    server = HTTPServer(("0.0.0.0", PORT), RequestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        controller.running = False
        controller.clear()

if __name__ == "__main__":
    main()
