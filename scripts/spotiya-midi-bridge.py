#!/opt/bin/python3
"""
Spotiya MIDI Bridge for Yandex Station 2 (Midi)
Handles:
1. Physical touch buttons (+, -, center tap) on /dev/input/event1
2. Quasar volume changes (/data/quasar/data/last_vendor_volume)
3. Quasar voice commands on 127.0.0.1:9875 ("тише", "громче", "громкость N", "стоп", "дальше", etc.)
4. Instant synchronization with Spotify Connect and ALSA Master
"""

import os
import sys
import time
import socket
import select
import struct
import json
import re

CONTROL_SOCK = "/run/spotiya.control"
STATUS_FILE = "/run/spotiya.status"
VENDOR_VOL_FILE = "/data/quasar/data/last_vendor_volume"
EVENT_DEV = "/dev/input/event1"
QUASAR_ADDR = ("127.0.0.1", 9875)

NUM_WORDS = {
    "ноль": 0, "нуль": 0,
    "один": 10, "единица": 10,
    "два": 20, "двойка": 20,
    "три": 30, "тройка": 30,
    "четыре": 40, "четверка": 40,
    "пять": 50, "пятерка": 50,
    "шесть": 60, "шестерка": 60,
    "семь": 70, "семерка": 70,
    "восемь": 80, "восьмерка": 80,
    "девять": 90, "девятка": 90,
    "десять": 100, "десятка": 100, "максимум": 100, "полная": 100, "всю": 100
}

def log(msg):
    t = time.strftime("%H:%M:%S")
    print(f"[{t}] [midi-bridge] {msg}", flush=True)

def send_spotiya_cmd(cmd):
    try:
        if os.path.exists(CONTROL_SOCK):
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(0.3)
            s.connect(CONTROL_SOCK)
            s.sendall((cmd.strip() + "\n").encode())
            s.close()
            return True
    except Exception as e:
        log(f"Error sending command '{cmd}': {e}")
    return False

def get_spotify_volume():
    try:
        if os.path.exists(STATUS_FILE):
            with open(STATUS_FILE, "r") as f:
                data = json.load(f)
                return int(data.get("volume", 50))
    except Exception:
        pass
    return 50

def set_spotify_volume(pct):
    pct = max(0, min(100, int(pct)))
    log(f"Setting Spotify volume -> {pct}%")
    send_spotiya_cmd(f"VOLUME {pct}")

def parse_protobuf_fields(data):
    fields = {}
    idx = 0
    dlen = len(data)
    while idx < dlen:
        key = 0
        shift = 0
        while idx < dlen:
            b = data[idx]
            idx += 1
            key |= (b & 0x7f) << shift
            if (b & 0x80) == 0: break
            shift += 7
        fnum = key >> 3
        wtype = key & 7
        if fnum == 0: break
        if wtype == 0: # varint
            val = 0
            shift = 0
            while idx < dlen:
                b = data[idx]
                idx += 1
                val |= (b & 0x7f) << shift
                if (b & 0x80) == 0: break
                shift += 7
            fields[fnum] = val
        elif wtype == 2: # length delimited
            length = 0
            shift = 0
            while idx < dlen:
                b = data[idx]
                idx += 1
                length |= (b & 0x7f) << shift
                if (b & 0x80) == 0: break
                shift += 7
            end = idx + length
            if end > dlen: break
            fields[fnum] = data[idx:end]
            idx = end
        elif wtype == 1: # 64-bit
            idx += 8
        elif wtype == 5: # 32-bit
            idx += 4
        else:
            break
    return fields

def cancel_alice(quasar_sock):
    """Tell Quasar to stop talking / cancel dialog so Alice doesn't speak over Spotify"""
    try:
        # Remoting message: field 210, AliceCapability STOP_CONVERSATION (method 3)
        cancel_frame = (
            b"\x18\x00\x00\x00"
            b"\x92\x0d\x15"
            b"\x3a\x0fAliceCapability"
            b"\x42\x02\x08\x03"
        )
        quasar_sock.sendall(cancel_frame)
    except Exception:
        pass

def handle_voice_text(text, quasar_sock):
    raw = text.strip()
    norm = raw.lower().replace("ё", "е").strip(" .!?")
    t = norm.replace("алиса, ", "").replace("алиса ", "").strip()
    
    cur_vol = get_spotify_volume()

    # 1. Volume DOWN
    if t in ("тише", "потише", "сделай тише", "убавь", "убавь звук", "убавь громкость", "уменьши звук", "уменьши громкость"):
        log(f"Voice action: VOLUME DOWN (from {cur_vol}%)")
        cancel_alice(quasar_sock)
        set_spotify_volume(cur_vol - 10)
        return True

    # 2. Volume UP
    if t in ("громче", "погромче", "сделай громче", "прибавь", "прибавь звук", "прибавь громкость", "добавь звук", "добавь громкость", "увеличь звук", "увеличь громкость"):
        log(f"Voice action: VOLUME UP (from {cur_vol}%)")
        cancel_alice(quasar_sock)
        set_spotify_volume(cur_vol + 10)
        return True

    # 3. Specific volume ("громкость 5", "громкость на 7", "поставь громкость пять")
    m = re.search(r"громкост[ья]\s*(?:на\s*)?(\d+|[а-я]+)", t)
    if m:
        val_str = m.group(1)
        target = None
        if val_str.isdigit():
            n = int(val_str)
            if 0 <= n <= 10:
                target = n * 10
            elif 10 < n <= 100:
                target = n
        elif val_str in NUM_WORDS:
            target = NUM_WORDS[val_str]
        
        if target is not None:
            log(f"Voice action: SET VOLUME to {target}%")
            cancel_alice(quasar_sock)
            set_spotify_volume(target)
            return True

    # 4. Instant transport commands without "Алиса"
    if t in ("стоп", "пауза", "хватит", "замолчи", "останови", "останови музыку", "выключи музыку"):
        log("Voice action: PAUSE")
        cancel_alice(quasar_sock)
        send_spotiya_cmd("PAUSE")
        return True

    if t in ("дальше", "следующий", "следующий трек", "переключи", "следующая песня"):
        log("Voice action: NEXT")
        cancel_alice(quasar_sock)
        send_spotiya_cmd("NEXT")
        return True

    if t in ("назад", "предыдущий", "предыдущий трек", "предыдущая песня"):
        log("Voice action: PREVIOUS")
        cancel_alice(quasar_sock)
        send_spotiya_cmd("PREVIOUS")
        return True

    if t in ("играй", "продолжи", "возобнови", "включи музыку", "продолжай"):
        log("Voice action: RESUME")
        cancel_alice(quasar_sock)
        send_spotiya_cmd("RESUME")
        return True

    return False

def main():
    log("Starting Spotiya MIDI Bridge v1.0...")

    # Open event1 for touch buttons
    input_fd = -1
    try:
        input_fd = os.open(EVENT_DEV, os.O_RDONLY | os.O_NONBLOCK)
        log(f"Opened {EVENT_DEV} for touch buttons")
    except Exception as e:
        log(f"Warning: could not open {EVENT_DEV}: {e}")

    # Track vendor volume file
    last_vendor_vol = None
    if os.path.exists(VENDOR_VOL_FILE):
        try:
            with open(VENDOR_VOL_FILE, "r") as f:
                last_vendor_vol = f.read().strip()
                log(f"Initial vendor volume: {last_vendor_vol}")
        except Exception:
            pass

    # Touch tracking
    touch_press_time = 0
    touch_is_down = False

    # Quasar socket
    quasar_sock = None
    quasar_buf = bytearray()
    last_quasar_connect_attempt = 0
    seen_requests = set()

    last_file_check = 0

    while True:
        now = time.time()

        # 1. Connect to Quasar if disconnected
        if quasar_sock is None and (now - last_quasar_connect_attempt >= 3):
            last_quasar_connect_attempt = now
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.setblocking(False)
                s.connect_ex(QUASAR_ADDR)
                quasar_sock = s
                quasar_buf.clear()
                log("Connected to Quasar on 127.0.0.1:9875")
            except Exception as e:
                quasar_sock = None

        # 2. Check vendor volume file every 250ms
        if now - last_file_check >= 0.25:
            last_file_check = now
            if os.path.exists(VENDOR_VOL_FILE):
                try:
                    with open(VENDOR_VOL_FILE, "r") as f:
                        cur_v = f.read().strip()
                    if cur_v and cur_v != last_vendor_vol:
                        last_vendor_vol = cur_v
                        if cur_v.isdigit():
                            level = int(cur_v)
                            target = max(0, min(100, level * 10))
                            log(f"Quasar vendor volume changed to {level} -> sync Spotify to {target}%")
                            set_spotify_volume(target)
                except Exception:
                    pass

        # 3. Build select poll list
        rlist = []
        if input_fd >= 0:
            rlist.append(input_fd)
        if quasar_sock is not None:
            rlist.append(quasar_sock)

        try:
            r, _, _ = select.select(rlist, [], [], 0.05)
        except Exception:
            time.sleep(0.05)
            continue

        # 4. Handle Touch Buttons
        if input_fd in r:
            try:
                raw = os.read(input_fd, 24 * 16)
                for i in range(0, len(raw), 24):
                    chunk = raw[i:i+24]
                    if len(chunk) == 24:
                        sec, usec, etype, ecode, evalue = struct.unpack("qqHHi", chunk)
                        if etype == 1: # EV_KEY
                            # Key 115 = Volume Up (+)
                            if ecode == 115 and evalue == 1: # Press
                                cur = get_spotify_volume()
                                new_vol = min(100, cur + 5)
                                log(f"Touch [+] pressed -> {new_vol}%")
                                set_spotify_volume(new_vol)

                            # Key 114 = Volume Down (-)
                            elif ecode == 114 and evalue == 1: # Press
                                cur = get_spotify_volume()
                                new_vol = max(0, cur - 5)
                                log(f"Touch [-] pressed -> {new_vol}%")
                                set_spotify_volume(new_vol)

                            # Key 582 = Center Voice / Action Tap
                            elif ecode == 582:
                                if evalue == 1:
                                    touch_press_time = time.time()
                                    touch_is_down = True
                                elif evalue == 0 and touch_is_down:
                                    dur = time.time() - touch_press_time
                                    touch_is_down = False
                                    if dur < 0.6: # Tap < 600ms
                                        log("Touch center TAP -> TOGGLE PLAY/PAUSE")
                                        send_spotiya_cmd("TOGGLE")
            except Exception as e:
                pass

        # 5. Handle Quasar events
        if quasar_sock in r:
            try:
                chunk = quasar_sock.recv(4096)
                if not chunk:
                    log("Quasar disconnected, will reconnect...")
                    quasar_sock.close()
                    quasar_sock = None
                    continue
                quasar_buf.extend(chunk)

                # Process framed messages: [uint32 length][payload]
                while len(quasar_buf) >= 4:
                    flen = struct.unpack("<I", quasar_buf[:4])[0]
                    if flen > 512 * 1024:
                        quasar_buf.clear()
                        break
                    if len(quasar_buf) < 4 + flen:
                        break
                    payload = bytes(quasar_buf[4:4+flen])
                    del quasar_buf[:4+flen]

                    msg_fields = parse_protobuf_fields(payload)
                    # Quasar message: AliceState in f=3 or f=252
                    state_bytes = msg_fields.get(3) or msg_fields.get(252)
                    if state_bytes and isinstance(state_bytes, bytes):
                        state_fields = parse_protobuf_fields(state_bytes)
                        # field 7: request_id, field 2: recognized text, field 15: asr_payload
                        req_id = state_fields.get(7)
                        rec_text = state_fields.get(2)
                        
                        if not rec_text and 15 in state_fields:
                            asr = parse_protobuf_fields(state_fields[15])
                            rec_text = asr.get(1)

                        if rec_text and isinstance(rec_text, bytes):
                            text_str = rec_text.decode("utf-8", errors="ignore")
                            req_key = str(req_id) if req_id else text_str
                            if req_key not in seen_requests:
                                seen_requests.add(req_key)
                                if len(seen_requests) > 64:
                                    seen_requests.pop()
                                handle_voice_text(text_str, quasar_sock)
            except Exception as e:
                log(f"Quasar socket error: {e}")
                if quasar_sock:
                    quasar_sock.close()
                quasar_sock = None

if __name__ == "__main__":
    main()
