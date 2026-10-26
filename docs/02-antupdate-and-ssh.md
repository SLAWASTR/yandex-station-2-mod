# 🛡️ Часть 2: Блокировка автообновлений и настройка постоянного Dropbear SSH

Яндекс регулярно выпускает обновления прошивки (OTA). Если не отключить обновление, первая же фоновая ночная прошивка затрёт root-доступ, восстановит закрытый образ и заблокирует порт ADB.

---

## 🚫 Полная блокировка автообновлений (Zero-Day Protection)

В Станции процесс обновления состоит из трёх компонентов:
1. `updatesd` — системный демон проверки и скачивания OTA-образов в фоне;
2. `applier` — бинарник, прошивающий скачанные образы в неактивный раздел памяти (A/B схема разметки);
3. Публичный ключ верификации OTA-подписи в `/etc/ota.key`.

Скрипт `scripts/yandex-noupdate.sh` выполняет комплексную нейтрализацию:
- **Удаляет `updatesd` из менеджера процессов `launch.json`** — демон проверки больше никогда не запускается супервизором;
- **Заменяет бинарник `applier` на заглушку** (`exit 0`) — даже при ручной попытке накатить апдейт ядро откажется его прошивать;
- **Подменяет ключ `ota.key`** на фиктивный;
- **Убивает запущенные процессы `maind --updatesd`**.

### Применение защиты:
В терминале с root-доступом выполните:
```bash
sh /data/opt/yandex-noupdate.sh
```

Вывод подтвердит:
```text
launch.json: updatesd убран
applier: заглушён
ota key: подменён
updatesd: остановлен
Статус: обновления Яндекса полностью отключены навсегда.
```

---

## 🔑 Установка постоянного Dropbear SSH (порт 2222)

ADB удобен для кабеля и локальной отладки, но для полноценного Linux-управления нужен быстрый, стандартный SSH-сервер.

1. Создаём каталоги для ключей и бинарника:
   ```bash
   mount -o remount,rw /
   mkdir -p /data/opt/bin /data/opt/etc/dropbear /etc/dropbear
   ```
2. Копируем легковесный `dropbear` (он уже собран в `/usr/sbin/dropbear` или Entware) и генерируем современный `ed25519` ключ хоста:
   ```bash
   cp -f /usr/sbin/dropbear /data/opt/bin/dropbear
   dropbearkey -t ed25519 -f /data/opt/etc/dropbear/hk_ed25519
   ```
3. Создаём скрипт автозапуска в `/etc/init.d/S99zdropbear`:
   ```bash
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
   /etc/init.d/S99zdropbear start
   mount -o remount,ro /
   ```

### Проверка подключения:
С вашего компьютера (Mac, Linux, Windows):
```bash
ssh -p 2222 root@192.168.3.11
```
*(По умолчанию вход без пароля или по вашему SSH-ключу в `~/.ssh/authorized_keys`).*
