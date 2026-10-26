#!/opt/bin/python3
# -*- coding: utf-8 -*-
"""
🎨 Yandex Station 2 — Pixel Grid Studio v4
Dual Port (80 & 8080) + Bulletproof DOM Grid (height: 44px) + elementFromPoint Pointer Drag
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
                        fcntl.ioctl(self.fb_file.fileno(), 0x4606, self.fb_var)  # FBIOPAN_DISPLAY
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
/* GRID OF CELLS */
.grid-container {
  display: grid;
  grid-template-columns: repeat(10, 1fr);
  gap: 6px;
  width: 100%;
  margin: 0 auto;
}
.led-cell {
  height: 44px;
  min-height: 44px;
  border-radius: 8px;
  background-color: #1a1e30;
  border: 1.5px solid #2d3450;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-family: monospace;
  font-weight: 600;
  color: #64748b;
  cursor: pointer;
  transition: transform 0.05s, background-color 0.05s;
  box-shadow: 0 2px 5px rgba(0,0,0,0.3);
}
.led-cell:hover {
  transform: scale(1.08);
  border-color: #ffffff;
  z-index: 2;
}
.led-cell.active-color {
  color: #ffffff;
  border-color: rgba(255, 255, 255, 0.9);
  box-shadow: 0 0 10px var(--glow-col);
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
  grid-template-columns: repeat(3, 1fr);
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
  <p>Кликай по светодиодам или зажимай мышку и веди (89 диодов)</p>
</header>

<div class="main-container">
  <div class="panel-card">
    <div class="grid-container" id="ledGrid">
<button type="button" class="led-cell" id="c0" onclick="paintCell(0)" onmouseenter="if(isPointerDown)paintCell(0)">0</button>
<button type="button" class="led-cell" id="c1" onclick="paintCell(1)" onmouseenter="if(isPointerDown)paintCell(1)">1</button>
<button type="button" class="led-cell" id="c2" onclick="paintCell(2)" onmouseenter="if(isPointerDown)paintCell(2)">2</button>
<button type="button" class="led-cell" id="c3" onclick="paintCell(3)" onmouseenter="if(isPointerDown)paintCell(3)">3</button>
<button type="button" class="led-cell" id="c4" onclick="paintCell(4)" onmouseenter="if(isPointerDown)paintCell(4)">4</button>
<button type="button" class="led-cell" id="c5" onclick="paintCell(5)" onmouseenter="if(isPointerDown)paintCell(5)">5</button>
<button type="button" class="led-cell" id="c6" onclick="paintCell(6)" onmouseenter="if(isPointerDown)paintCell(6)">6</button>
<button type="button" class="led-cell" id="c7" onclick="paintCell(7)" onmouseenter="if(isPointerDown)paintCell(7)">7</button>
<button type="button" class="led-cell" id="c8" onclick="paintCell(8)" onmouseenter="if(isPointerDown)paintCell(8)">8</button>
<button type="button" class="led-cell" id="c9" onclick="paintCell(9)" onmouseenter="if(isPointerDown)paintCell(9)">9</button>
<button type="button" class="led-cell" id="c10" onclick="paintCell(10)" onmouseenter="if(isPointerDown)paintCell(10)">10</button>
<button type="button" class="led-cell" id="c11" onclick="paintCell(11)" onmouseenter="if(isPointerDown)paintCell(11)">11</button>
<button type="button" class="led-cell" id="c12" onclick="paintCell(12)" onmouseenter="if(isPointerDown)paintCell(12)">12</button>
<button type="button" class="led-cell" id="c13" onclick="paintCell(13)" onmouseenter="if(isPointerDown)paintCell(13)">13</button>
<button type="button" class="led-cell" id="c14" onclick="paintCell(14)" onmouseenter="if(isPointerDown)paintCell(14)">14</button>
<button type="button" class="led-cell" id="c15" onclick="paintCell(15)" onmouseenter="if(isPointerDown)paintCell(15)">15</button>
<button type="button" class="led-cell" id="c16" onclick="paintCell(16)" onmouseenter="if(isPointerDown)paintCell(16)">16</button>
<button type="button" class="led-cell" id="c17" onclick="paintCell(17)" onmouseenter="if(isPointerDown)paintCell(17)">17</button>
<button type="button" class="led-cell" id="c18" onclick="paintCell(18)" onmouseenter="if(isPointerDown)paintCell(18)">18</button>
<button type="button" class="led-cell" id="c19" onclick="paintCell(19)" onmouseenter="if(isPointerDown)paintCell(19)">19</button>
<button type="button" class="led-cell" id="c20" onclick="paintCell(20)" onmouseenter="if(isPointerDown)paintCell(20)">20</button>
<button type="button" class="led-cell" id="c21" onclick="paintCell(21)" onmouseenter="if(isPointerDown)paintCell(21)">21</button>
<button type="button" class="led-cell" id="c22" onclick="paintCell(22)" onmouseenter="if(isPointerDown)paintCell(22)">22</button>
<button type="button" class="led-cell" id="c23" onclick="paintCell(23)" onmouseenter="if(isPointerDown)paintCell(23)">23</button>
<button type="button" class="led-cell" id="c24" onclick="paintCell(24)" onmouseenter="if(isPointerDown)paintCell(24)">24</button>
<button type="button" class="led-cell" id="c25" onclick="paintCell(25)" onmouseenter="if(isPointerDown)paintCell(25)">25</button>
<button type="button" class="led-cell" id="c26" onclick="paintCell(26)" onmouseenter="if(isPointerDown)paintCell(26)">26</button>
<button type="button" class="led-cell" id="c27" onclick="paintCell(27)" onmouseenter="if(isPointerDown)paintCell(27)">27</button>
<button type="button" class="led-cell" id="c28" onclick="paintCell(28)" onmouseenter="if(isPointerDown)paintCell(28)">28</button>
<button type="button" class="led-cell" id="c29" onclick="paintCell(29)" onmouseenter="if(isPointerDown)paintCell(29)">29</button>
<button type="button" class="led-cell" id="c30" onclick="paintCell(30)" onmouseenter="if(isPointerDown)paintCell(30)">30</button>
<button type="button" class="led-cell" id="c31" onclick="paintCell(31)" onmouseenter="if(isPointerDown)paintCell(31)">31</button>
<button type="button" class="led-cell" id="c32" onclick="paintCell(32)" onmouseenter="if(isPointerDown)paintCell(32)">32</button>
<button type="button" class="led-cell" id="c33" onclick="paintCell(33)" onmouseenter="if(isPointerDown)paintCell(33)">33</button>
<button type="button" class="led-cell" id="c34" onclick="paintCell(34)" onmouseenter="if(isPointerDown)paintCell(34)">34</button>
<button type="button" class="led-cell" id="c35" onclick="paintCell(35)" onmouseenter="if(isPointerDown)paintCell(35)">35</button>
<button type="button" class="led-cell" id="c36" onclick="paintCell(36)" onmouseenter="if(isPointerDown)paintCell(36)">36</button>
<button type="button" class="led-cell" id="c37" onclick="paintCell(37)" onmouseenter="if(isPointerDown)paintCell(37)">37</button>
<button type="button" class="led-cell" id="c38" onclick="paintCell(38)" onmouseenter="if(isPointerDown)paintCell(38)">38</button>
<button type="button" class="led-cell" id="c39" onclick="paintCell(39)" onmouseenter="if(isPointerDown)paintCell(39)">39</button>
<button type="button" class="led-cell" id="c40" onclick="paintCell(40)" onmouseenter="if(isPointerDown)paintCell(40)">40</button>
<button type="button" class="led-cell" id="c41" onclick="paintCell(41)" onmouseenter="if(isPointerDown)paintCell(41)">41</button>
<button type="button" class="led-cell" id="c42" onclick="paintCell(42)" onmouseenter="if(isPointerDown)paintCell(42)">42</button>
<button type="button" class="led-cell" id="c43" onclick="paintCell(43)" onmouseenter="if(isPointerDown)paintCell(43)">43</button>
<button type="button" class="led-cell" id="c44" onclick="paintCell(44)" onmouseenter="if(isPointerDown)paintCell(44)">44</button>
<button type="button" class="led-cell" id="c45" onclick="paintCell(45)" onmouseenter="if(isPointerDown)paintCell(45)">45</button>
<button type="button" class="led-cell" id="c46" onclick="paintCell(46)" onmouseenter="if(isPointerDown)paintCell(46)">46</button>
<button type="button" class="led-cell" id="c47" onclick="paintCell(47)" onmouseenter="if(isPointerDown)paintCell(47)">47</button>
<button type="button" class="led-cell" id="c48" onclick="paintCell(48)" onmouseenter="if(isPointerDown)paintCell(48)">48</button>
<button type="button" class="led-cell" id="c49" onclick="paintCell(49)" onmouseenter="if(isPointerDown)paintCell(49)">49</button>
<button type="button" class="led-cell" id="c50" onclick="paintCell(50)" onmouseenter="if(isPointerDown)paintCell(50)">50</button>
<button type="button" class="led-cell" id="c51" onclick="paintCell(51)" onmouseenter="if(isPointerDown)paintCell(51)">51</button>
<button type="button" class="led-cell" id="c52" onclick="paintCell(52)" onmouseenter="if(isPointerDown)paintCell(52)">52</button>
<button type="button" class="led-cell" id="c53" onclick="paintCell(53)" onmouseenter="if(isPointerDown)paintCell(53)">53</button>
<button type="button" class="led-cell" id="c54" onclick="paintCell(54)" onmouseenter="if(isPointerDown)paintCell(54)">54</button>
<button type="button" class="led-cell" id="c55" onclick="paintCell(55)" onmouseenter="if(isPointerDown)paintCell(55)">55</button>
<button type="button" class="led-cell" id="c56" onclick="paintCell(56)" onmouseenter="if(isPointerDown)paintCell(56)">56</button>
<button type="button" class="led-cell" id="c57" onclick="paintCell(57)" onmouseenter="if(isPointerDown)paintCell(57)">57</button>
<button type="button" class="led-cell" id="c58" onclick="paintCell(58)" onmouseenter="if(isPointerDown)paintCell(58)">58</button>
<button type="button" class="led-cell" id="c59" onclick="paintCell(59)" onmouseenter="if(isPointerDown)paintCell(59)">59</button>
<button type="button" class="led-cell" id="c60" onclick="paintCell(60)" onmouseenter="if(isPointerDown)paintCell(60)">60</button>
<button type="button" class="led-cell" id="c61" onclick="paintCell(61)" onmouseenter="if(isPointerDown)paintCell(61)">61</button>
<button type="button" class="led-cell" id="c62" onclick="paintCell(62)" onmouseenter="if(isPointerDown)paintCell(62)">62</button>
<button type="button" class="led-cell" id="c63" onclick="paintCell(63)" onmouseenter="if(isPointerDown)paintCell(63)">63</button>
<button type="button" class="led-cell" id="c64" onclick="paintCell(64)" onmouseenter="if(isPointerDown)paintCell(64)">64</button>
<button type="button" class="led-cell" id="c65" onclick="paintCell(65)" onmouseenter="if(isPointerDown)paintCell(65)">65</button>
<button type="button" class="led-cell" id="c66" onclick="paintCell(66)" onmouseenter="if(isPointerDown)paintCell(66)">66</button>
<button type="button" class="led-cell" id="c67" onclick="paintCell(67)" onmouseenter="if(isPointerDown)paintCell(67)">67</button>
<button type="button" class="led-cell" id="c68" onclick="paintCell(68)" onmouseenter="if(isPointerDown)paintCell(68)">68</button>
<button type="button" class="led-cell" id="c69" onclick="paintCell(69)" onmouseenter="if(isPointerDown)paintCell(69)">69</button>
<button type="button" class="led-cell" id="c70" onclick="paintCell(70)" onmouseenter="if(isPointerDown)paintCell(70)">70</button>
<button type="button" class="led-cell" id="c71" onclick="paintCell(71)" onmouseenter="if(isPointerDown)paintCell(71)">71</button>
<button type="button" class="led-cell" id="c72" onclick="paintCell(72)" onmouseenter="if(isPointerDown)paintCell(72)">72</button>
<button type="button" class="led-cell" id="c73" onclick="paintCell(73)" onmouseenter="if(isPointerDown)paintCell(73)">73</button>
<button type="button" class="led-cell" id="c74" onclick="paintCell(74)" onmouseenter="if(isPointerDown)paintCell(74)">74</button>
<button type="button" class="led-cell" id="c75" onclick="paintCell(75)" onmouseenter="if(isPointerDown)paintCell(75)">75</button>
<button type="button" class="led-cell" id="c76" onclick="paintCell(76)" onmouseenter="if(isPointerDown)paintCell(76)">76</button>
<button type="button" class="led-cell" id="c77" onclick="paintCell(77)" onmouseenter="if(isPointerDown)paintCell(77)">77</button>
<button type="button" class="led-cell" id="c78" onclick="paintCell(78)" onmouseenter="if(isPointerDown)paintCell(78)">78</button>
<button type="button" class="led-cell" id="c79" onclick="paintCell(79)" onmouseenter="if(isPointerDown)paintCell(79)">79</button>
<button type="button" class="led-cell" id="c80" onclick="paintCell(80)" onmouseenter="if(isPointerDown)paintCell(80)">80</button>
<button type="button" class="led-cell" id="c81" onclick="paintCell(81)" onmouseenter="if(isPointerDown)paintCell(81)">81</button>
<button type="button" class="led-cell" id="c82" onclick="paintCell(82)" onmouseenter="if(isPointerDown)paintCell(82)">82</button>
<button type="button" class="led-cell" id="c83" onclick="paintCell(83)" onmouseenter="if(isPointerDown)paintCell(83)">83</button>
<button type="button" class="led-cell" id="c84" onclick="paintCell(84)" onmouseenter="if(isPointerDown)paintCell(84)">84</button>
<button type="button" class="led-cell" id="c85" onclick="paintCell(85)" onmouseenter="if(isPointerDown)paintCell(85)">85</button>
<button type="button" class="led-cell" id="c86" onclick="paintCell(86)" onmouseenter="if(isPointerDown)paintCell(86)">86</button>
<button type="button" class="led-cell" id="c87" onclick="paintCell(87)" onmouseenter="if(isPointerDown)paintCell(87)">87</button>
<button type="button" class="led-cell" id="c88" onclick="paintCell(88)" onmouseenter="if(isPointerDown)paintCell(88)">88</button>
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
      <button class="btn" id="btnExport">💾 Скачать .led</button>
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
      <span id="statusText">Подключено (Live 30 FPS Loop)</span>
    </div>
  </div>
</div>

<script>
const TOTAL_LEDS = 89;
const gridContainer = document.getElementById('ledGrid');

let currentColor = '#ff0033';
let brightnessPct = 1.0;
let whiteIntensity = 0;
let isPointerDown = false;

const ledState = Array.from({length: TOTAL_LEDS}, () => ({r: 0, g: 0, b: 0, w: 0}));
const gridCells = [];

// Populate 89 grid cells
for (let i = 0; i < TOTAL_LEDS; i++) {
  const cell = document.createElement('div');
  cell.className = 'led-cell';
  cell.id = `led-cell-${i}`;
  cell.dataset.idx = i;
  cell.innerText = i;
  gridContainer.appendChild(cell);
  gridCells.push(cell);
}

function hexToRgb(hex) {
  const bigint = parseInt(hex.slice(1), 16);
  return {
    r: Math.round(((bigint >> 16) & 255) * brightnessPct),
    g: Math.round(((bigint >> 8) & 255) * brightnessPct),
    b: Math.round((bigint & 255) * brightnessPct)
  };
}

function paintCell(idx) {
  if (idx < 0 || idx >= TOTAL_LEDS) return;
  const rgb = hexToRgb(currentColor);
  ledState[idx] = { r: rgb.r, g: rgb.g, b: rgb.b, w: parseInt(whiteIntensity) };
  
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

function checkAndPaint(e) {
  const el = document.elementFromPoint(e.clientX, e.clientY);
  if (el && el.classList && el.classList.contains('led-cell')) {
    const idx = parseInt(el.dataset.idx);
    if (!isNaN(idx)) {
      paintCell(idx);
    }
  }
}

// Global Drag & Click listeners using elementFromPoint
window.addEventListener('pointerdown', (e) => {
  isPointerDown = true;
  checkAndPaint(e);
});

window.addEventListener('pointermove', (e) => {
  if (isPointerDown) {
    checkAndPaint(e);
  }
});

window.addEventListener('pointerup', () => { isPointerDown = false; });
window.addEventListener('pointercancel', () => { isPointerDown = false; });

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
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.send_header("Connection", "close")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
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

        if self.path == "/api/pixel":
            try:
                data = json.loads(post_body.decode("utf-8"))
                idx = int(data.get("index", -1))
                col = data.get("color", "#ff0000").lstrip("#")
                r = int(col[0:2], 16) if len(col) >= 2 else 0
                g = int(col[2:4], 16) if len(col) >= 4 else 0
                b = int(col[4:6], 16) if len(col) >= 6 else 0
                controller.set_pixel(idx, r, g, b, 0)
                self.reply_data(b"OK")
            except Exception as e:
                self.reply_data(f"Error: {e}".encode("utf-8"), code=400)
        elif self.path == "/api/frame":
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

def run_server(port):
    try:
        server = HTTPServer(("0.0.0.0", port), RequestHandler)
        print(f"[*] LED Studio Server started on port {port}")
        server.serve_forever()
    except Exception as e:
        print(f"[!] Server error on port {port}: {e}")

def main():
    # Start on port 80 and port 8080!
    t1 = threading.Thread(target=run_server, args=(80,), daemon=True)
    t1.start()
    
    # Main on 8080
    run_server(8080)

if __name__ == "__main__":
    main()
