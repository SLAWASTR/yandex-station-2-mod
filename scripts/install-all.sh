#!/bin/sh
set -eu

echo "=================================================================="
echo " 🚀 Яндекс Станция 2 / Миди (YNDX-00051) — All-in-One Mod Installer"
echo "    • Постоянный ADB root (порт 5555)"
echo "    • Постоянный Dropbear SSH (порт 2222)"
echo "    • Полная блокировка автообновлений Яндекса"
echo "    • Apple AirPlay (Shairport Sync 4.3)"
echo "    • Spotify Connect (Spotiya + PlayPlay DRM) с нативным звуком"
echo "    • Аппаратные кнопки (+ / - / tap) и синхронизация громкости с Алисой"
echo "=================================================================="

if [ "$(id -u)" -ne 0 ]; then
    echo "ОШИБКА: Запустите этот скрипт от root (adb shell или ssh)!" >&2
    exit 1
fi

SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)

# 1. Remount rootfs read-write
echo "[1/6] Перемонтирование rootfs в режим записи..."
mount -o remount,rw /

# 2. Permanent ADB
echo "[2/6] Установка постоянного ADB на порту 5555..."
mkdir -p /etc/init.d
cat << 'EOF' > /etc/init.d/S97adb
#!/bin/sh
case "$1" in
  start)
    echo "Starting ADB daemon..."
    setprop service.adb.tcp.port 5555
    stop adbd 2>/dev/null || true
    start adbd 2>/dev/null || true
    ;;
  stop)
    stop adbd 2>/dev/null || true
    ;;
  restart)
    $0 stop
    $0 start
    ;;
esac
EOF
chmod 755 /etc/init.d/S97adb

# 3. Permanent Dropbear SSH on port 2222
echo "[3/6] Настройка постоянного Dropbear SSH на порту 2222..."
mkdir -p /data/opt/bin /data/opt/etc/dropbear /etc/dropbear
if [ ! -f /data/opt/bin/dropbear ]; then
    if [ -f /usr/sbin/dropbear ]; then
        cp -f /usr/sbin/dropbear /data/opt/bin/dropbear
    elif [ -f /usr/bin/dropbear ]; then
        cp -f /usr/bin/dropbear /data/opt/bin/dropbear
    fi
fi
if [ -x /data/opt/bin/dropbear ]; then
    if [ ! -f /data/opt/etc/dropbear/hk_ed25519 ]; then
        dropbearkey -t ed25519 -f /data/opt/etc/dropbear/hk_ed25519 2>/dev/null || true
    fi
    cat << 'EOF' > /etc/init.d/S99zdropbear
#!/bin/sh
DAEMON=/data/opt/bin/dropbear
KEY=/data/opt/etc/dropbear/hk_ed25519
PORT=2222

case "$1" in
    start)
        echo "Starting Dropbear SSH on port $PORT..."
        if [ -x "$DAEMON" ] && [ -f "$KEY" ]; then
            $DAEMON -r "$KEY" -p "$PORT" -B
        fi
        ;;
    stop)
        killall dropbear 2>/dev/null || true
        ;;
    restart)
        $0 stop
        $0 start
        ;;
esac
EOF
    chmod 755 /etc/init.d/S99zdropbear
fi

# 4. Disable Yandex Updates
echo "[4/6] Блокировка автообновлений Яндекса..."
if [ -f "$SCRIPT_DIR/yandex-noupdate.sh" ]; then
    sh "$SCRIPT_DIR/yandex-noupdate.sh"
elif [ -f /data/opt/yandex-noupdate.sh ]; then
    sh /data/opt/yandex-noupdate.sh
fi

# 5. Bootstrap Entware & AirPlay
echo "[5/6] Проверка Entware и Apple AirPlay..."
if [ ! -x /opt/bin/opkg ]; then
    echo "Установка Entware aarch64..."
    mkdir -p /data/opt/entware /opt
    mount --bind /data/opt/entware /opt
    wget -O - http://bin.entware.net/aarch64-k3.10/installer/generic.sh | /bin/sh
fi

if [ -x /opt/bin/opkg ]; then
    /opt/bin/opkg update
    /opt/bin/opkg install shairport-sync-mini tinysvcmdns alsa-utils python3-light python3-ctypes
    
    # Configure Shairport Sync
    mkdir -p /opt/etc
    cat << 'EOF' > /opt/etc/shairport-sync.conf
general = {
  name = "Yandex Station 2";
  output_backend = "alsa";
  mdns_backend = "tinysvcmdns";
};

alsa = {
  output_device = "default";
};

sessioncontrol = {
  run_this_before_play_begins = "/usr/bin/spotiya release";
  wait_for_completion = "no";
};
EOF

    cat << 'EOF' > /etc/init.d/S99zentware
#!/bin/sh
case "$1" in
    start)
        mkdir -p /opt
        mount --bind /data/opt/entware /opt 2>/dev/null || true
        /opt/etc/init.d/rc.unslung start 2>/dev/null || true
        /opt/bin/shairport-sync -d 2>/dev/null || true
        ;;
    stop)
        killall shairport-sync 2>/dev/null || true
        /opt/etc/init.d/rc.unslung stop 2>/dev/null || true
        umount /opt 2>/dev/null || true
        ;;
    restart)
        $0 stop
        $0 start
        ;;
esac
EOF
    chmod 755 /etc/init.d/S99zentware
    /etc/init.d/S99zentware start || true
fi

# 6. Spotiya + PlayPlay + MIDI Bridge
echo "[6/6] Установка Spotiya Spotify Connect, PlayPlay DRM и MIDI Bridge..."
SPOTIYA_DIR=/data/opt/spotify-connect
mkdir -p "$SPOTIYA_DIR" /data/opt/bin

if command -v spotiya >/dev/null 2>&1; then
    echo "Spotiya уже установлена"
else
    echo "Загрузка Spotiya v0.9.4..."
    TMP_D=$(mktemp -d /tmp/spotiya.XXXXXX)
    wget -qO "$TMP_D/spotiya.tar.gz" https://github.com/klockky/spotiya/releases/download/v0.9.4/spotiya-armv7-linux-gnueabihf.tar.gz
    tar -xzf "$TMP_D/spotiya.tar.gz" -C "$TMP_D"
    chmod +x "$TMP_D/spotiya/spotiya" "$TMP_D/spotiya/scripts/install.sh"
    sh "$TMP_D/spotiya/scripts/install.sh"
    rm -rf "$TMP_D"
fi

# Configure device name & profile
cp -f "$SCRIPT_DIR/run.sh" "$SPOTIYA_DIR/run.sh"
chmod 755 "$SPOTIYA_DIR/run.sh"

spotiya profile select mini1 || true
spotiya addon install playplay || true

# Install MIDI Touch & Volume Bridge
cp -f "$SCRIPT_DIR/spotiya-midi-bridge.py" /data/opt/bin/spotiya-midi-bridge.py
chmod 755 /data/opt/bin/spotiya-midi-bridge.py

cp -f "$SCRIPT_DIR/start.sh" "$SPOTIYA_DIR/start.sh"
cp -f "$SCRIPT_DIR/stop.sh" "$SPOTIYA_DIR/stop.sh"
chmod 755 "$SPOTIYA_DIR/start.sh" "$SPOTIYA_DIR/stop.sh"

# Fix init.d autostart
cp -f "$SCRIPT_DIR/S99spotify-connect" /etc/init.d/S99spotify-connect
chmod 755 /etc/init.d/S99spotify-connect

# Remount rootfs read-only
sync
mount -o remount,ro / || true

# Start services
spotiya restart

echo ""
echo "=================================================================="
echo " ✅ ВСЁ УСПЕШНО УСТАНОВЛЕНО И ЗАПУЩЕНО!"
echo "    Имя в сети: 'Yandex Station 2'"
echo "    Для первой авторизации в Spotify:"
echo "      Вариант А: откройте https://spotify.com/pair и введите код из 'spotiya login'"
echo "      Вариант Б: выберите 'Yandex Station 2' в приложении Spotify на телефоне/ПК"
echo "=================================================================="
