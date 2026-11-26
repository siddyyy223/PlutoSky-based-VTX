#!/usr/bin/env bash
# Label a Pluto as the TX or RX board.
#   ./label_pluto.sh tx     label the board that is plugged in
#   ./label_pluto.sh rx     with the TX board also plugged in: labels the other one
# Which board gets the label: the only board attached, or else the only attached
# board that has no label yet. A board is identified by its own IP address (the
# ipaddr in config.txt on the board's USB drive), saved in pluto_boards.conf.
# Serial numbers can't be used: PlutoSky clone boards may all share one.
# After labelling, run_tx.sh / run_rx.sh always pick the right board, even with
# both on one PC.
set -u
cd "$(dirname "$0")"
ROLE=${1:-}
[[ "$ROLE" == tx || "$ROLE" == rx ]] || { echo "usage: $0 tx|rx"; exit 2; }
CONF=pluto_boards.conf

mapfile -t boards < <(PLUTO_URI= ./find_pluto.sh --list)
if [[ ${#boards[@]} -eq 0 ]]; then
    ./find_pluto.sh >/dev/null; echo "Plug in the board to label as ${ROLE^^}, then run this again."; exit 1
fi
echo "Pluto boards attached:"
for b in "${boards[@]}"; do read -r u i r <<<"$b"; echo "  $u  board IP $i  ${r:+(labelled ${r^^})}"; done

# Two boards with the same IP subnet look like one board: catch that.
nusb=$(grep -l '^0456$' /sys/bus/usb/devices/*/idVendor 2>/dev/null | wc -l)
nseen=$(printf '%s\n' "${boards[@]}" | grep -c '^usb:')
if (( nusb > nseen )); then
    echo
    echo "$nusb Pluto boards are on USB but only $nseen can be told apart: two boards use the same IP."
    echo "Give one of them another address: open its USB drive (PlutoSDR) in the file manager,"
    echo "edit config.txt, in [NETWORK] set  ipaddr = 192.168.3.1  and  ipaddr_host = 192.168.3.10"
    echo "(any subnet not used by the other board), save, eject the drive, wait for the board"
    echo "to reboot, then run this again."
    exit 1
fi

if [[ ${#boards[@]} -eq 1 ]]; then
    read -r URI IPADDR _ <<<"${boards[0]}"
else
    free=(); for b in "${boards[@]}"; do read -r u i r <<<"$b"; [[ -z "$r" ]] && free+=("$b"); done
    if [[ ${#free[@]} -ne 1 ]]; then
        echo "Can't tell which board to label: ${#free[@]} unlabelled boards attached."
        echo "Unplug all but the board to label as ${ROLE^^}, then run this again."; exit 1
    fi
    read -r URI IPADDR _ <<<"${free[0]}"
fi
if [[ -z "$IPADDR" || "$IPADDR" == unknown-ip ]]; then
    echo "Can't read the IP address of the board at $URI (no USB network interface with an"
    echo "IPv4 address on this PC). Check 'ip -br addr' shows a 192.168.x.10 interface."; exit 1
fi
# Never give one board both labels while the other board is attached.
for b in "${boards[@]}"; do
    read -r u i r <<<"$b"
    if [[ "$i" == "$IPADDR" && -n "$r" && "$r" != "$ROLE" && ${#boards[@]} -gt 1 ]]; then
        echo "Refusing: $u is the ${r^^} board."; exit 1
    fi
done
MODEL=$(timeout 5 iio_attr -u "$URI" -C hw_model 2>/dev/null | cut -d' ' -f2-)

[[ -f $CONF ]] || printf '# Pluto board labels: <role> <board IP> <description>. Written by ./label_pluto.sh\n' > "$CONF"
net=${IPADDR%.*}
other=$(awk -v n="$net" -v r="$ROLE" '$1 !~ /^#/ && $1 != r { s=$2; sub(/\.[0-9]+$/, "", s); if (s == n) print $1 }' "$CONF")
[[ -n "$other" ]] && echo "Note: this board was labelled ${other^^}; it is now ${ROLE^^}."
# Drop any old line for this role or this board, then add the new one.
awk -v n="$net" -v r="$ROLE" '$1 ~ /^#/ { print; next } { s=$2; sub(/\.[0-9]+$/, "", s); if ($1 != r && s != n) print }' \
    "$CONF" > "$CONF.tmp" && mv "$CONF.tmp" "$CONF"
echo "$ROLE $IPADDR $MODEL" >> "$CONF"
echo "Labelled ${ROLE^^} board: IP $IPADDR ($MODEL), now at $URI"
echo "Tip: also put a physical sticker \"${ROLE^^}\" on the board."
