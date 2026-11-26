#!/usr/bin/env bash
# Receiver PC (PC B): Pluto B -> live video window. Start this BEFORE run_tx.sh.
#   ./run_rx.sh                  RX gain 35 dB (also adjustable live with the slider)
#   ./run_rx.sh --rx-gain 20     lower gain if the boards are close together
# Any r2_camera_rx.py option can be added (see ./run_rx.sh --help).
# Uses $PLUTO_URI if set, otherwise the board labelled in pluto_boards.conf (./find_pluto.sh).
set -u
cd "$(dirname "$0")"

if [[ " $* " == *" --help "* || " $* " == *" -h "* ]]; then
    sed -n '2,6p' "$0"; echo; exec python3 r2_camera_rx.py --help
fi

URI=$(./find_pluto.sh rx) || exit 1
echo "Pluto (RX): $URI"
exec python3 r2_camera_rx.py --rx-uri "$URI" "$@"
