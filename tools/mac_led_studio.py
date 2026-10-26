#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎨 Yandex Station 2 — Desktop LED Studio (macOS Native GUI)
Interactive Tkinter paint editor for 89 RGBW LEDs with live Wi-Fi sync.
"""

import math
import json
import urllib.request
import tkinter as tk
from tkinter import colorchooser, messagebox

STATION_IP = "192.168.3.11"
API_URL = f"http://{STATION_IP}:8080/api"
TOTAL_LEDS = 89

class DesktopLEDStudio:
    def __init__(self, root):
        self.root = root
        self.root.title("🎨 Станция 2 — LED Studio (macOS)")
        self.root.geometry("640x780")
        self.root.configure(bg="#0f111a")
        self.root.resizable(False, False)

        self.current_color = "#ff0033"
        self.brightness = 1.0
        self.white_val = 0
        self.is_painting = False
        self.layout_mode = "circle"  # "circle" or "grid"
        self.sync_job = None

        # State: 89 LEDs [R, G, B, W]
        self.led_state = [{"r": 0, "g": 0, "b": 0, "w": 0} for _ in range(TOTAL_LEDS)]
        self.led_items = []  # Canvas circle IDs

        self.create_widgets()
        self.compute_positions()
        self.draw_canvas()

    def create_widgets(self):
        # Header
        header = tk.Frame(self.root, bg="#0f111a", pady=10)
        header.pack(fill="x")
        tk.Label(
            header,
            text="🎨 Яндекс Станция 2 — LED Studio",
            font=("SF Pro Display", 18, "bold"),
            fg="#a78bfa",
            bg="#0f111a"
        ).pack()
        tk.Label(
            header,
            text=f"Синхронизация в реальном времени с {STATION_IP}:8080",
            font=("SF Pro Text", 11),
            fg="#9ca3af",
            bg="#0f111a"
        ).pack()

        # Canvas Frame
        canvas_card = tk.Frame(self.root, bg="#181b28", bd=1, relief="flat", padx=10, pady=10)
        canvas_card.pack(padx=20, pady=5)
        self.canvas = tk.Canvas(
            canvas_card,
            width=440,
            height=440,
            bg="#131622",
            highlightthickness=2,
            highlightbackground="#333a56",
            cursor="crosshair"
        )
        self.canvas.pack()

        self.canvas.bind("<Button-1>", self.on_canvas_press)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)

        # Palette & Tools Card
        panel = tk.Frame(self.root, bg="#181b28", bd=1, relief="flat", padx=15, pady=10)
        panel.pack(fill="x", padx=20, pady=10)

        # Colors Row
        palette_frame = tk.Frame(panel, bg="#181b28")
        palette_frame.pack(fill="x", pady=5)

        colors = [
            ("#ff0033", "Красный"),
            ("#00ff66", "Зелёный"),
            ("#0088ff", "Синий"),
            ("#a855f7", "Алиса"),
            ("#00ffff", "Циан"),
            ("#fbbf24", "Жёлтый"),
            ("#ffffff", "Белый"),
            ("#000000", "Ластик")
        ]

        for col, name in colors:
            btn = tk.Button(
                palette_frame,
                bg=col,
                activebackground=col,
                width=3,
                height=1,
                relief="flat",
                bd=0,
                command=lambda c=col: self.set_color(c)
            )
            btn.pack(side="left", padx=4)

        custom_btn = tk.Button(
            palette_frame,
            text="Палитра...",
            font=("SF Pro Text", 10),
            bg="#24293e",
            fg="#f3f4f6",
            relief="flat",
            command=self.choose_custom_color
        )
        custom_btn.pack(side="left", padx=8)

        # Brightness & White slider
        sliders = tk.Frame(panel, bg="#181b28")
        sliders.pack(fill="x", pady=6)

        tk.Label(sliders, text="Яркость:", font=("SF Pro Text", 10), fg="#9ca3af", bg="#181b28").pack(side="left", padx=4)
        self.bright_slider = tk.Scale(
            sliders,
            from_=5,
            to=100,
            orient="horizontal",
            bg="#181b28",
            fg="#f3f4f6",
            highlightthickness=0,
            command=self.on_bright_change
        )
        self.bright_slider.set(100)
        self.bright_slider.pack(side="left", fill="x", expand=True, padx=4)

        # Action Buttons
        btn_row = tk.Frame(panel, bg="#181b28")
        btn_row.pack(fill="x", pady=6)

        tk.Button(
            btn_row, text="🪣 Залить всё", font=("SF Pro Text", 11, "bold"),
            bg="#24293e", fg="#f3f4f6", relief="flat", command=self.fill_all
        ).pack(side="left", expand=True, fill="x", padx=3)

        tk.Button(
            btn_row, text="🧹 Очистить", font=("SF Pro Text", 11, "bold"),
            bg="#451a1a", fg="#fca5a5", relief="flat", command=self.clear_all
        ).pack(side="left", expand=True, fill="x", padx=3)

        tk.Button(
            btn_row, text="🔄 Раскладка", font=("SF Pro Text", 11),
            bg="#24293e", fg="#f3f4f6", relief="flat", command=self.toggle_layout
        ).pack(side="left", expand=True, fill="x", padx=3)

        # Effects Row
        fx_row = tk.Frame(panel, bg="#181b28")
        fx_row.pack(fill="x", pady=6)

        fx_list = [
            ("🌈 Радуга", "rainbow"),
            ("🕯️ Свеча", "candle"),
            ("💜 Пульс", "pulse"),
            ("🚨 Полиция", "police")
        ]
        for label, code in fx_list:
            tk.Button(
                fx_row, text=label, font=("SF Pro Text", 10),
                bg="#24293e", fg="#f3f4f6", relief="flat",
                command=lambda c=code: self.trigger_fx(c)
            ).pack(side="left", expand=True, fill="x", padx=2)

        # Status Bar
        self.status_label = tk.Label(
            self.root,
            text=f"● Онлайн — колонка подключена на {STATION_IP}:8080",
            font=("SF Pro Text", 11),
            fg="#10b981",
            bg="#0f111a"
        )
        self.status_label.pack(pady=4)

    def compute_positions(self):
        self.positions = []
        cx, cy = 220, 220
        if self.layout_mode == "circle":
            # Ring 1: 34 LEDs (r=170)
            for i in range(34):
                angle = (i / 34) * 2 * math.pi - math.pi / 2
                self.positions.append((cx + 170 * math.cos(angle), cy + 170 * math.sin(angle), 10))
            # Ring 2: 24 LEDs (r=120)
            for i in range(24):
                angle = (i / 24) * 2 * math.pi - math.pi / 2
                self.positions.append((cx + 120 * math.cos(angle), cy + 120 * math.sin(angle), 9))
            # Ring 3: 18 LEDs (r=75)
            for i in range(18):
                angle = (i / 18) * 2 * math.pi - math.pi / 2
                self.positions.append((cx + 75 * math.cos(angle), cy + 75 * math.sin(angle), 8.5))
            # Ring 4: 12 LEDs (r=36)
            for i in range(12):
                angle = (i / 12) * 2 * math.pi - math.pi / 2
                self.positions.append((cx + 36 * math.cos(angle), cy + 36 * math.sin(angle), 7.5))
            # Center: 1 LED
            self.positions.append((cx, cy, 8))
        else:
            # 10 x 9 Grid
            cols = 10
            for i in range(TOTAL_LEDS):
                r = i // cols
                c = i % cols
                self.positions.append((40 + c * 40, 40 + r * 44, 12))

    def draw_canvas(self):
        self.canvas.delete("all")
        self.led_items = []
        for i, (x, y, rad) in enumerate(self.positions):
            s = self.led_state[i]
            col = f"#{s['r']:02x}{s['g']:02x}{s['b']:02x}" if (s['r'] or s['g'] or s['b']) else "#1c2032"
            outline = "#ffffff" if (s['r'] or s['g'] or s['b']) else "#2e354e"
            item = self.canvas.create_oval(
                x - rad, y - rad, x + rad, y + rad,
                fill=col, outline=outline, width=1.5
            )
            # Label
            self.canvas.create_text(
                x, y, text=str(i),
                font=("SF Mono", 7),
                fill="#ffffff" if (s['r'] or s['g'] or s['b']) else "#4b557c"
            )
            self.led_items.append(item)

    def set_color(self, hex_col):
        self.current_color = hex_col

    def choose_custom_color(self):
        col = colorchooser.askcolor(color=self.current_color, title="Выберите цвет")
        if col and col[1]:
            self.current_color = col[1]

    def on_bright_change(self, val):
        self.brightness = float(val) / 100.0

    def hex_to_rgb(self, hex_col):
        hex_col = hex_col.lstrip("#")
        return [
            int(int(hex_col[0:2], 16) * self.brightness),
            int(int(hex_col[2:4], 16) * self.brightness),
            int(int(hex_col[4:6], 16) * self.brightness)
        ]

    def paint_at(self, event):
        x, y = event.x, event.y
        for i, (px, py, rad) in enumerate(self.positions):
            dist = math.hypot(px - x, py - y)
            if dist <= rad * 1.8:
                r, g, b = self.hex_to_rgb(self.current_color)
                self.led_state[i] = {"r": r, "g": g, "b": b, "w": self.white_val}
                fill = f"#{r:02x}{g:02x}{b:02x}" if (r or g or b) else "#1c2032"
                outline = "#ffffff" if (r or g or b) else "#2e354e"
                self.canvas.itemconfig(self.led_items[i], fill=fill, outline=outline)
                self.schedule_sync()
                break

    def on_canvas_press(self, event):
        self.is_painting = True
        self.paint_at(event)

    def on_canvas_drag(self, event):
        if self.is_painting:
            self.paint_at(event)

    def on_canvas_release(self, event):
        self.is_painting = False

    def fill_all(self):
        r, g, b = self.hex_to_rgb(self.current_color)
        for i in range(TOTAL_LEDS):
            self.led_state[i] = {"r": r, "g": g, "b": b, "w": self.white_val}
        self.draw_canvas()
        self.send_frame()

    def clear_all(self):
        for i in range(TOTAL_LEDS):
            self.led_state[i] = {"r": 0, "g": 0, "b": 0, "w": 0}
        self.draw_canvas()
        try:
            req = urllib.request.Request(f"{API_URL}/clear", method="POST")
            urllib.request.urlopen(req, timeout=1.0)
        except Exception:
            pass

    def toggle_layout(self):
        self.layout_mode = "grid" if self.layout_mode == "circle" else "circle"
        self.compute_positions()
        self.draw_canvas()

    def schedule_sync(self):
        if self.sync_job is not None:
            self.root.after_cancel(self.sync_job)
        self.sync_job = self.root.after(30, self.send_frame)

    def send_frame(self):
        try:
            data = json.dumps(self.led_state).encode("utf-8")
            req = urllib.request.Request(
                f"{API_URL}/frame",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            urllib.request.urlopen(req, timeout=1.0)
            self.status_label.config(text=f"● Онлайн — кадр синхронизирован с {STATION_IP}", fg="#10b981")
        except Exception as e:
            self.status_label.config(text=f"⚠ Ошибка отправки: {e}", fg="#f87171")

    def trigger_fx(self, fx_name):
        try:
            data = json.dumps({"fx": fx_name}).encode("utf-8")
            req = urllib.request.Request(
                f"{API_URL}/fx",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            urllib.request.urlopen(req, timeout=1.0)
            self.status_label.config(text=f"● Запущен эффект: {fx_name}", fg="#a78bfa")
        except Exception as e:
            self.status_label.config(text=f"⚠ Ошибка: {e}", fg="#f87171")

def main():
    root = tk.Tk()
    app = DesktopLEDStudio(root)
    root.mainloop()

if __name__ == "__main__":
    main()
