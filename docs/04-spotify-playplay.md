# 🎵 Часть 4: Spotify Connect и преодоление ограничений ALSA и PlayPlay DRM

Интеграция Spotify на Яндекс Станции 2 (Миди) столкнулась с двумя сложнейшими архитектурными барьерами, которые ломали звук в других проектах. В этом руководстве подробно описано, в чём была суть проблем и как мы их преодолели.

---

## 🛑 Проблема 1: 32/64-битный конфликт ALSA `dmix` (Почему падал Soloist)

Ядро Яндекс Станции 2 собрано как 64-битное (`aarch64`), но **весь системный userspace и драйверы звука — 32-битные (`armhf`)**:
- Системный звуковой сервер Яндекса (`maind`) открывает звуковую карту `hw:0,0` через плагин `dmix` (Direct Mixing), создавая сегмент разделяемой памяти с ключом IPC `1024`.
- В 32-битном пространстве заголовок структуры `snd_pcm_direct_share_t` занимает ровно **496 байт**.
- Официальный клиент Spotify Soloist собран как 64-битный исполняемый файл. Его 64-битная библиотека ALSA ожидает структуру размером **568+ байт**.

При попытке открыть устройство вывода 64-битный клиент падает с ошибкой:
```text
ALSA lib pcm_direct.c:2195:(_snd_pcm_direct_new) unable to create IPC shm instance
soloist-shim: pcm open spotify failed: Invalid argument
```
В результате Spotify в приложении показывает, что трек идёт, но физически в динамик не уходит ни одного сэмпла звука.

---

## 🛑 Проблема 2: Блокировка аудиоключей Spotify (PlayPlay DRM)

В конце 2024–2026 годов Spotify изменил протокол раздачи ключей шифрования треков. Для большинства учётных записей в ряде регионов серверы Spotify Access Point стали отказывать стандартному опенсорсному Librespot:
```text
[INFO librespot_core::playplay] AP audio key refused; trying PlayPlay
[ERROR librespot_core::audio_key] PlayPlay audio key unavailable: Service unavailable
```
Обычные клиенты без проприетарного модуля DRM декодера **PlayPlay** бесконечно пропускают треки со статусом `Track unavailable`. Официальные приложения (и ТВ) работают, потому что имеют вшитый DRM PlayPlay.

---

## 💡 Решение: Spotiya (ARM32) + PlayPlay DRM Decoder

Мы развернули проект **[`spotiya`](https://github.com/klockky/spotiya)** (версия 0.9.4) со специальным профилем:

1. **Нативная 32-битная сборка (`armv7-linux-gnueabihf`):**
   - Компилируется под ABI `armhf` (glibc 2.23+), то есть находится в одном адресном пространстве с системным сервером Яндекса.
   - Подключается к `dmix_spk` (`pcm.!default`) без ошибок разделяемой памяти IPC.
2. **Аддон `playplay-decoder`:**
   - Устанавливается одной командой:
     ```bash
     spotiya addon install playplay
     ```
   - Запускает изолированный процесс эмуляции ARM-декодера PlayPlay через движок Unicorn.
   - Когда сервер Spotify отказывает в обычном ключе, декодер автоматически расшифровывает поток:
     ```text
     [INFO librespot_core::playplay] AP audio key refused; trying PlayPlay
     receiver: PlayPlay decoder configured on demand
     [INFO librespot_core::playplay] PlayPlay response accepted (version 5)
     [INFO librespot_audio::playplay] PlayPlay decoder ready
     ```

---

## 🔑 Авторизация в аккаунте Spotify

Для привязки Spotify Premium достаточно выполнить **одно** из двух действий:
1. **Через код на сайте:**
   Запустите команду `spotiya login`, перейдите по адресу [spotify.com/pair](https://spotify.com/pair) и введите полученный код.
2. **Через Spotify Connect на смартфоне:**
   Откройте приложение Spotify на смартфоне в той же Wi-Fi сети и в меню устройств выберите **`Yandex Station 2`**. Авторизация сохранится автоматически и навсегда.
