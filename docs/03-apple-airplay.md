# 🍏 Часть 3: Apple AirPlay (Shairport Sync + tinysvcmdns)

Штатно Яндекс Станции поддерживают трансляцию только через Bluetooth и проприетарный Яндекс Мультирум. С помощью пакета **Shairport Sync 4.3** мы превращаем колонку в полноценный беспроводной Hi-Fi приёмник **Apple AirPlay** с автоматическим обнаружением на всех устройствах Apple (iPhone, iPad, Mac, Apple TV).

---

## 🏗️ Установка стека через Entware

Поскольку корневой раздел rootfs сильно ограничен по месту, для дополнительных пакетов используется **Entware aarch64**, установленный в энергонезависимый раздел `/data/opt/entware`.

1. **Инициализация Entware:**
   ```bash
   mkdir -p /data/opt/entware /opt
   mount --bind /data/opt/entware /opt
   wget -O - http://bin.entware.net/aarch64-k3.10/installer/generic.sh | /bin/sh
   ```
2. **Установка Shairport Sync и сопутствующих утилит:**
   ```bash
   /opt/bin/opkg update
   /opt/bin/opkg install shairport-sync-mini tinysvcmdns alsa-utils
   ```

---

## ⚙️ Конфигурация звука и mDNS

Файл конфигурации создаётся в `/opt/etc/shairport-sync.conf`:

```text
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
```

### Ключевые параметры:
- `mdns_backend = "tinysvcmdns"`: встроенный легковесный mDNS-клиент. Он не требует тяжелого D-Bus и демона Avahi, публикуя сервис `_raop._tcp` напрямую в локальную сеть.
- `output_backend = "alsa"`, `output_device = "default"`: направляет декодированный поток в системный микшер `dmix_spk` без монопольного захвата аудиокарты.
- `run_this_before_play_begins = "/usr/bin/spotiya release"`: когда с iPhone или Mac начинается трансляция AirPlay, Станция автоматически освобождает аудиоканал от Spotify.

---

## 🔄 Автозапуск при включении колонки

В `/etc/init.d/S99zentware`:
```bash
mount -o remount,rw /
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
mount -o remount,ro /
```

### Проверка в сети (с Mac):
```bash
dns-sd -B _raop._tcp local.
```
В списке появится:
```text
Add ... _raop._tcp. 2BE72C0A5E49@Yandex Station 2
```
На любом iPhone в Пункте управления в меню выбора аудиовыхода колонка появится мгновенно с именем **Yandex Station 2**.
