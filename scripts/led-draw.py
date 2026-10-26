#!/opt/bin/python3
# -*- coding: utf-8 -*-
"""
🎨 Yandex Station 2 — Terminal LED Drawer (TUI)
Interactive ANSI Grid Editor for 89 RGBW LEDs. Run directly in SSH terminal!
"""

import os
import sys
import tty
import termios
import select
import mmap
import fcntl
import struct
import math
import time

TOTAL_LEDS = 89
COLS = 10
ROWS = 9
BYTES_PER_FRAME = TOTAL_LEDS * 4

# Hardware setup
fb_file = None
fb_mm = None
fb_var = bytearray(160)

try:
    fb_file = open("/dev/fb0", "r+b")
    fcntl.ioctl(fb_file.fileno(), 0x4600, fb_var)  # FBIOGET_VSCREENINFO
    fb_mm = mmap.mmap(fb_file.fileno(), 4096)
except Exception as e:
    fb_mm = None

# 89 LEDs state: list of [R, G, B, W]
pixels = [[0, 0, 0, 0] for _ in range(TOTAL_LEDS)]

# Color palette: (Name, ANSI_FG, ANSI_BG, (R, G, B, W))
PALETTE = {
    '1': ("Красный",  "\033[91m", "\033[41m", (255, 0, 0, 0)),
    '2': ("Зелёный",  "\033[92m", "\033[42m", (0, 255, 0, 0)),
    '3': ("Синий",    "\033[94m", "\033[44m", (0, 100, 255, 0)),
    '4': ("Фиолет",   "\033[95m", "\033[45m", (170, 0, 255, 0)),
    '5': ("Циан",     "\033[96m", "\033[46m", (0, 255, 255, 0)),
    '6': ("Жёлтый",   "\033[93m", "\033[43m", (255, 220, 0, 0)),
    '7': ("Белый",    "\033[97m", "\033[47m", (255, 255, 255, 255)),
    '0': ("Выкл",     "\033[90m", "\033[40m", (0, 0, 0, 0)),
}

current_color_key = '1'
cursor_idx = 0

def sync_hardware():
    if fb_mm is None or fb_file is None:
        return
    buf = bytearray()
    for r, g, b, w in pixels:
        # Hardware: B, G, R, W
        buf.extend(bytes([
            max(0, min(255, int(b))),
            max(0, min(255, int(g))),
            max(0, min(255, int(r))),
            max(0, min(255, int(w)))
        ]))
    fb_mm[:BYTES_PER_FRAME] = buf
    try:
        fcntl.ioctl(fb_file.fileno(), 0x4606, fb_var)  # FBIOPAN_DISPLAY
    except Exception:
        pass

def get_ansi_for_rgb(r, g, b):
    if r == 0 and g == 0 and b == 0:
        return "\033[90m\033[40m"
    # Match closest palette color
    best_dist = 9999999
    best_bg = "\033[40m"
    for k, (_, _, bg, (pr, pg, pb, _)) in PALETTE.items():
        if k == '0': continue
        d = (r - pr)**2 + (g - pg)**2 + (b - pb)**2
        if d < best_dist:
            best_dist = d
            best_bg = bg
    return f"\033[97;1m{best_bg}"

def draw_tui():
    lines = []
    lines.append("\033[H\033[1;35m╔═══════════════════════════════════════════════════════════╗\033[0m")
    lines.append("\033[1;35m║  🎨 Станция 2 — Консольный редактор LED (89 диодов)       ║\033[0m")
    lines.append("\033[1;35m╚═══════════════════════════════════════════════════════════╝\033[0m\n")

    for r in range(ROWS):
        row_str = " "
        for c in range(COLS):
            idx = r * COLS + c
            if idx >= TOTAL_LEDS:
                break
            
            is_cursor = (idx == cursor_idx)
            pr, pg, pb, _ = pixels[idx]
            color_code = get_ansi_for_rgb(pr, pg, pb)
            
            if is_cursor:
                # Inverted blinking cursor
                row_str += f"\033[7;1m[{idx:02d}]\033[0m "
            else:
                row_str += f"{color_code}[{idx:02d}]\033[0m "
        lines.append(row_str)

    lines.append("\n" + "─" * 60)
    col_name, col_fg, col_bg, _ = PALETTE[current_color_key]
    lines.append(f"Выбран цвет: {col_fg}{col_bg} {col_name} \033[0m  |  Курсор на диоде: \033[1;36m#{cursor_idx:02d}\033[0m")
    lines.append("\033[90m[1]Красн [2]Зел [3]Син [4]Фиолет [5]Циан [6]Желт [7]Белый [0]Ластик\033[0m")
    lines.append("\033[33mУправление:\033[0m Стрелочки/WASD: курсор | Пробел/Enter: закрасить")
    lines.append("           [F]: залить всё | [C]: очистить | [R]: радуга | [Q]: выход")

    sys.stdout.write("\n".join(lines) + "\n")
    sys.stdout.flush()

def main():
    global cursor_idx, current_color_key, pixels

    # Terminal setup
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    
    # Hide cursor, clear screen
    sys.stdout.write("\033[?25l\033[2J")
    sys.stdout.flush()
    
    sync_hardware()

    try:
        tty.setraw(fd)
        draw_tui()

        while True:
            r, _, _ = select.select([sys.stdin], [], [], 0.05)
            if not r:
                continue

            ch = sys.stdin.read(1)

            # Handle Escape Sequences (Arrow keys)
            if ch == '\x1b':
                seq = sys.stdin.read(2)
                if seq == '[A':   # UP
                    if cursor_idx >= COLS: cursor_idx -= COLS
                elif seq == '[B': # DOWN
                    if cursor_idx + COLS < TOTAL_LEDS: cursor_idx += COLS
                elif seq == '[C': # RIGHT
                    if cursor_idx + 1 < TOTAL_LEDS: cursor_idx += 1
                elif seq == '[D': # LEFT
                    if cursor_idx > 0: cursor_idx -= 1
            # WASD
            elif ch in ('w', 'W'):
                if cursor_idx >= COLS: cursor_idx -= COLS
            elif ch in ('s', 'S'):
                if cursor_idx + COLS < TOTAL_LEDS: cursor_idx += COLS
            elif ch in ('d', 'D'):
                if cursor_idx + 1 < TOTAL_LEDS: cursor_idx += 1
            elif ch in ('a', 'A'):
                if cursor_idx > 0: cursor_idx -= 1
            # Color selection: 0..7
            elif ch in PALETTE:
                current_color_key = ch
                # Auto paint on number press
                pixels[cursor_idx] = list(PALETTE[ch][3])
                sync_hardware()
            # Paint: Space or Enter
            elif ch in (' ', '\r', '\n'):
                pixels[cursor_idx] = list(PALETTE[current_color_key][3])
                sync_hardware()
            # Clear: C
            elif ch in ('c', 'C'):
                pixels = [[0, 0, 0, 0] for _ in range(TOTAL_LEDS)]
                sync_hardware()
            # Fill All: F
            elif ch in ('f', 'F'):
                col = list(PALETTE[current_color_key][3])
                pixels = [list(col) for _ in range(TOTAL_LEDS)]
                sync_hardware()
            # Rainbow effect: R
            elif ch in ('r', 'R'):
                for i in range(TOTAL_LEDS):
                    hue = (i / TOTAL_LEDS) % 1.0
                    r = int((math.sin(hue * 6.28) + 1.0) * 0.5 * 255)
                    g = int((math.sin(hue * 6.28 + 2.09) + 1.0) * 0.5 * 255)
                    b = int((math.sin(hue * 6.28 + 4.18) + 1.0) * 0.5 * 255)
                    pixels[i] = [r, g, b, 0]
                sync_hardware()
            # Quit: Q or Ctrl+C
            elif ch in ('q', 'Q', '\x03'):
                break

            draw_tui()

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        sys.stdout.write("\033[?25h\033[0m\033[2J\033[H")
        sys.stdout.flush()
        print("✔ Редактор закрыт. Светодиоды сохранены.")

if __name__ == "__main__":
    main()
