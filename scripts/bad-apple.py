#!/opt/bin/python3
# -*- coding: utf-8 -*-
"""
🍎 Bad Apple!! on Yandex Station 2 / Midi
Synced playback: Hi-Fi Audio (ALSA) + Terminal ASCII Art (30 FPS) + 89 RGBW LEDs (/dev/fb0)
"""

import os
import sys
import time
import gzip
import json
import mmap
import fcntl
import struct
import signal
import argparse
import subprocess

DIR = "/data/opt/bad-apple"
FPS = 10.0
TOTAL_FRAMES = 2181
LED_COUNT = 89
BYTES_PER_LED_FRAME = LED_COUNT * 4  # 356 bytes

def main():
    parser = argparse.ArgumentParser(description="Bad Apple!! on Yandex Station 2")
    parser.add_argument("--no-led", action="store_true", help="Disable LED panel sync")
    parser.add_argument("--no-audio", action="store_true", help="Disable audio output")
    parser.add_argument("--start", type=float, default=0.0, help="Start offset in seconds")
    args = parser.parse_args()

    # Terminal cursor management
    sys.stdout.write("\033[?25l\033[2J")  # Hide cursor, clear screen
    sys.stdout.flush()

    aplay_proc = None
    madplay_proc = None
    fb_file = None
    fb_mm = None
    fb_var = None

    def cleanup(sig=None, frame=None):
        # Restore terminal
        sys.stdout.write("\033[?25h\033[0m\n")
        sys.stdout.flush()

        # Stop audio
        if madplay_proc and madplay_proc.poll() is None:
            try:
                madplay_proc.terminate()
            except Exception:
                pass
        if aplay_proc and aplay_proc.poll() is None:
            try:
                aplay_proc.terminate()
            except Exception:
                pass

        # Clear LEDs
        if fb_mm is not None and fb_file is not None:
            try:
                fb_mm[:] = b"\x00" * BYTES_PER_LED_FRAME
                fcntl.ioctl(fb_file.fileno(), 0x4606, fb_var)
                fb_file.close()
            except Exception:
                pass

        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    # 1. Setup Framebuffer (/dev/fb0)
    if not args.no_led:
        try:
            fb_file = open("/dev/fb0", "r+b")
            fb_mm = mmap.mmap(fb_file.fileno(), BYTES_PER_LED_FRAME)
            fb_var = bytearray(160)
            struct.pack_into("II", fb_var, 0, LED_COUNT, 1)
        except Exception as e:
            fb_file = None
            fb_mm = None

    # 2. Load precomputed data
    try:
        sys.stdout.write("\033[H\033[36m[*] Загрузка данных Bad Apple!!...\033[0m\n")
        sys.stdout.flush()
        with gzip.open(f"{DIR}/frames.json.gz", "rt", encoding="utf-8") as f:
            ascii_frames = json.load(f)
        with open(f"{DIR}/leds.bin", "rb") as f:
            leds_data = f.read()
    except Exception as e:
        sys.stdout.write(f"\033[31mОшибка загрузки файлов: {e}\033[0m\n")
        cleanup()

    # 3. Start Audio Playback
    if not args.no_audio and os.path.exists(f"{DIR}/audio.mp3"):
        try:
            aplay_proc = subprocess.Popen(
                ["/usr/bin/aplay", "-f", "cd", "-q"],
                stdin=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )
            mad_args = ["/opt/bin/madplay"]
            if args.start > 0:
                mins = int(args.start // 60)
                secs = args.start % 60
                mad_args += ["-s", f"{mins:02d}:{secs:06.3f}"]
            mad_args += ["-o", "raw:-", f"{DIR}/audio.mp3"]
            madplay_proc = subprocess.Popen(
                mad_args,
                stdout=aplay_proc.stdin,
                stderr=subprocess.DEVNULL
            )
        except Exception as e:
            pass

    # 4. Main Playback Loop
    t_start = time.time() - args.start
    last_frame = -1

    try:
        while True:
            now = time.time()
            elapsed = now - t_start
            frame_idx = int(elapsed * FPS)

            if frame_idx >= len(ascii_frames):
                break

            if frame_idx != last_frame:
                last_frame = frame_idx

                # Update LED Panel
                if fb_mm is not None:
                    offset = frame_idx * BYTES_PER_LED_FRAME
                    fb_mm[:] = leds_data[offset : offset + BYTES_PER_LED_FRAME]
                    fcntl.ioctl(fb_file.fileno(), 0x4606, fb_var)

                # Render ASCII Frame in Terminal
                cur_min = int(elapsed // 60)
                cur_sec = int(elapsed % 60)
                pct = (frame_idx / len(ascii_frames)) * 100
                bar_len = 24
                filled = int(bar_len * (frame_idx / len(ascii_frames)))
                bar = "█" * filled + "░" * (bar_len - filled)

                frame_content = ascii_frames[frame_idx]
                info_line = (
                    f"\033[1;35m🍎 Bad Apple!!\033[0m | "
                    f"\033[36m[{bar}] {pct:4.1f}%\033[0m | "
                    f"\033[33m{cur_min:02d}:{cur_sec:02d} / 03:38\033[0m | "
                    f"\033[32mFrame {frame_idx:04d}/{len(ascii_frames)}\033[0m"
                )

                sys.stdout.write(f"\033[H{frame_content}\n\n{info_line}\n")
                sys.stdout.flush()

            # High precision frame sleep
            next_frame_time = t_start + (frame_idx + 1) / FPS
            sleep_time = next_frame_time - time.time()
            if sleep_time > 0.002:
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        pass
    finally:
        cleanup()

if __name__ == "__main__":
    main()
