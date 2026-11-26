#!/usr/bin/env bash
# One-time setup of a fresh Pop!_OS / Ubuntu PC for the PlutoSky live video link.
#   ./setup_pc.sh          install packages (asks for your password once), then check
#   ./setup_pc.sh --check  only check, install nothing
set -u
cd "$(dirname "$0")"

ok()   { printf '  \e[32mOK\e[0m    %s\n' "$*"; }
warn() { printf '  \e[33mWARN\e[0m  %s\n' "$*"; }
bad()  { printf '  \e[31mFAIL\e[0m  %s\n' "$*"; FAILED=1; }
FAILED=0

PKGS=(gnuradio libiio-utils python3-pyqt5 python3-yaml python3-numpy ffmpeg v4l-utils iputils-ping)

if [[ "${1:-}" != "--check" ]]; then
    echo "== Installing packages (sudo password needed once) =="
    sudo apt-get update && sudo apt-get install -y "${PKGS[@]}" || {
        echo "apt-get failed -- fix the error above and run ./setup_pc.sh again"; exit 1; }
    # Camera access for this user (takes effect after logging out and in again).
    if ! id -nG | grep -qw video; then sudo usermod -aG video "$USER" && \
        warn "added $USER to the 'video' group -- log out and back in once"; fi
fi

echo "== Checking software =="
. /etc/os-release 2>/dev/null && ok "OS: ${PRETTY_NAME:-unknown}"
if command -v gnuradio-config-info >/dev/null; then
    v=$(gnuradio-config-info --version)
    case "$v" in 3.10.*) ok "GNU Radio $v";; *) bad "GNU Radio $v -- version 3.10 is required";; esac
else bad "GNU Radio not installed (run ./setup_pc.sh without --check)"; fi
python3 - <<'EOF' && ok "Python modules: gnuradio (iio, digital, qtgui), PyQt5, numpy" || bad "Python modules missing -- see the error above"
from gnuradio import gr, iio, digital, blocks, qtgui, filter  # noqa
from PyQt5 import QtCore, QtGui, QtWidgets  # noqa
import numpy  # noqa
EOF
command -v iio_info >/dev/null && ok "libiio tools ($(iio_info -V 2>&1 | head -1))" || bad "iio_info missing (libiio-utils)"
command -v ffmpeg >/dev/null && ok "ffmpeg" || warn "ffmpeg missing -- needed only on the transmitter (camera) PC"
python3 r2_camera_tx.py --help >/dev/null 2>&1 && python3 r2_camera_rx.py --help >/dev/null 2>&1 \
    && ok "r2_camera_tx.py / r2_camera_rx.py load" || bad "flowgraph scripts fail to load: run  python3 r2_camera_rx.py --help  to see why"

echo "== Checking hardware =="
cams=$(ls /dev/video* 2>/dev/null | tr '\n' ' ')
[[ -n "$cams" ]] && ok "camera devices: $cams(only needed on the transmitter PC)" \
                 || warn "no camera found (fine for the receiver PC)"
if uri=$(./find_pluto.sh 2>/dev/null) || uri=$(./find_pluto.sh tx 2>/dev/null) || uri=$(./find_pluto.sh rx 2>/dev/null); then ok "Pluto found at $uri"
else warn "no Pluto found -- plug it into USB, wait ~20 s, then run ./find_pluto.sh"; fi

echo
if [[ $FAILED == 0 ]]; then echo "Setup OK. Next: ./run_rx.sh on the receiver PC, ./run_tx.sh on the transmitter PC."
else echo "Setup has problems -- fix the FAIL lines above."; exit 1; fi
