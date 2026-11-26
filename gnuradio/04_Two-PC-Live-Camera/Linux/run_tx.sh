#!/usr/bin/env bash
# Transmitter PC (PC A): camera -> Pluto A.
#   ./run_tx.sh                       live camera, TX attenuation 30 dB
#   ./run_tx.sh --source-mode test    moving test pattern instead of the camera
#   ./run_tx.sh --tx-attenuation 20   more output power (longer distance)
# Any r2_camera_tx.py option can be added (see ./run_tx.sh --help).
# Uses $PLUTO_URI if set, otherwise finds the board with ./find_pluto.sh.
set -u
cd "$(dirname "$0")"

if [[ " $* " == *" --help "* || " $* " == *" -h "* ]]; then
    sed -n '2,7p' "$0"; echo; exec python3 r2_camera_tx.py --help
fi

URI=$(./find_pluto.sh) || exit 1
echo "Pluto (TX): $URI"

# Power the TX LO up (a previous run_tx.sh powers it down on exit) ...
iio_attr -u "$URI" -c ad9361-phy altvoltage1 powerdown 0 >/dev/null
# ... and down again however this script ends, so the board never keeps
# transmitting unattended. (kill -9 cannot be trapped: then run ./mute_tx.sh)
mute() { iio_attr -u "$URI" -c ad9361-phy altvoltage1 powerdown 1 >/dev/null 2>&1 \
         && echo "TX muted (TX LO powered down)"; }
trap mute EXIT

args=("$@")
[[ " $* " == *" --tx-attenuation "* ]] || args+=(--tx-attenuation 30)
if [[ " $* " != *" --source-mode test "* ]]; then
    cam=$(ls /dev/video* 2>/dev/null | head -1)
    [[ -n "$cam" ]] || { echo "No camera (/dev/video*) found. Plug one in, or use --source-mode test"; exit 1; }
fi

python3 r2_camera_tx.py --tx-uri "$URI" "${args[@]}"
