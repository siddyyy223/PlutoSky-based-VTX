#!/usr/bin/env bash
# Emergency stop: stop the Pluto's RF output (powers down its TX LO).
# Use it if run_tx.sh was killed hard or you are unsure whether the board is
# still transmitting. run_tx.sh powers the TX LO up again when it starts.
set -u
cd "$(dirname "$0")"
URI=$(./find_pluto.sh) || exit 1
iio_attr -u "$URI" -c ad9361-phy altvoltage1 powerdown 1 >/dev/null && echo "TX muted on $URI"
