#!/bin/sh
set -eu
umask 077
. /data/opt/spotify-connect/service.sh
if SPOTIFY_PID=$(supervisor_pid); then
    echo "Spotify Connect already running (supervisor pid $SPOTIFY_PID)"
    exit 0
fi
if receiver_pid >/dev/null; then
    "$SPOTIFY_DIR/stop.sh"
fi
rm -f /run/spotify-connect-stop
nohup setsid "$SPOTIFY_DIR/run.sh" --supervise </dev/null >/tmp/spotify-connect-supervisor.log 2>&1 &
SPOTIFY_WAIT=0
until SPOTIFY_PID=$(supervisor_pid); do
    if [ "$SPOTIFY_WAIT" -ge 50 ]; then
        echo 'Spotify Connect supervisor failed; see /tmp/spotify-connect-supervisor.log' >&2
        exit 1
    fi
    SPOTIFY_WAIT=$((SPOTIFY_WAIT + SPOTIFY_TICK))
    pause_briefly
done
echo "Spotify Connect started (supervisor pid $SPOTIFY_PID)"

# Start MIDI hardware buttons and volume synchronizer
pkill -f spotiya-midi-bridge.py 2>/dev/null || true
nohup /opt/bin/python3 /data/opt/bin/spotiya-midi-bridge.py > /tmp/spotiya-midi-bridge.log 2>&1 &
echo "Spotiya MIDI Bridge started"
