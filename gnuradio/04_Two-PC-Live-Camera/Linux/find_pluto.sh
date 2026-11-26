#!/usr/bin/env bash
# Print the libiio URI of a Pluto attached to this PC, e.g. "usb:1.3.5".
#   ./find_pluto.sh tx    the board labelled TX in pluto_boards.conf
#   ./find_pluto.sh rx    the board labelled RX
#   ./find_pluto.sh       any board (only if exactly one is attached)
# Boards are matched by serial number, so the USB port or address doesn't matter.
# A board labelled for the other role is never returned. $PLUTO_URI, if set,
# is used as is.
# Exit status 1 (and a hint on stderr) if the board is not found.
set -u
cd "$(dirname "$0")"
ROLE=${1:-}
CONF=pluto_boards.conf

if [[ -n "${PLUTO_URI:-}" ]]; then echo "$PLUTO_URI"; exit 0; fi

label_of() {  # serial -> role from pluto_boards.conf (empty if not labelled)
    [[ -f $CONF ]] && awk -v s="$1" '$1 !~ /^#/ && $2 == s {print $1; exit}' "$CONF"
}
serial_of() {  # uri -> hw_serial, empty if no AD936x board answers there
    timeout 5 iio_attr -u "$1" -d 2>/dev/null | grep -q ad9361-phy || return 0
    timeout 5 iio_attr -u "$1" -C hw_serial 2>/dev/null | awk '{print $2}'
}

# Scan USB/network/mDNS: libiio 0.2x (Pop!_OS/Ubuntu package) uses "iio_info -s",
# libiio 1.x uses "iio_info -S". Result lines end in "[uri]". USB first: a board
# on USB is reachable that way even when its USB-network address is not.
candidates=()
while read -r u; do candidates+=("$u"); done < <(
    { timeout 8 iio_info -s 2>/dev/null; timeout 8 iio_info -S 2>/dev/null; } |
    grep -oE '\[(ip|usb):[^]]+\]' | tr -d '[]' | sort -u | sort -t: -k1,1r)
candidates+=(ip:192.168.2.1 ip:192.168.3.1 ip:10.10.10.1)

found=(); seen=" "
for u in "${candidates[@]}"; do
    s=$(serial_of "$u"); [[ -n "$s" ]] || continue
    [[ "$seen" == *" $s "* ]] && continue      # same board reached two ways
    seen+="$s "
    found+=("$u $s $(label_of "$s")")
done

pick=""
if [[ -n "$ROLE" ]]; then
    for f in "${found[@]}"; do read -r u s r <<<"$f"; [[ "$r" == "$ROLE" ]] && pick=$u && break; done
    if [[ -z "$pick" ]] && ! grep -qE "^$ROLE[[:space:]]" "$CONF" 2>/dev/null; then
        # No board labelled for this role yet: accept a single unlabelled board.
        free=(); for f in "${found[@]}"; do read -r u s r <<<"$f"; [[ -z "$r" ]] && free+=("$u"); done
        if [[ ${#free[@]} -eq 1 ]]; then pick=${free[0]}; fi
    fi
elif [[ ${#found[@]} -eq 1 ]]; then
    read -r pick _ <<<"${found[0]}"
fi

if [[ -n "$pick" ]]; then echo "$pick"; exit 0; fi

{
    if [[ ${#found[@]} -gt 0 ]]; then
        echo "Pluto boards attached:"
        for f in "${found[@]}"; do read -r u s r <<<"$f"; echo "  $u  serial $s  ${r:+(labelled ${r^^})}"; done
    fi
    if [[ -n "$ROLE" ]] && grep -qE "^$ROLE[[:space:]]" "$CONF" 2>/dev/null; then
        echo "The ${ROLE^^} board (serial $(awk -v r="$ROLE" '$1==r{print $2}' "$CONF")) is not connected."
    elif [[ ${#found[@]} -gt 1 ]]; then
        echo "More than one board: label them once, one at a time, with ./label_pluto.sh tx|rx"
    else
        echo "No Pluto found. Check:"
        echo "  1. The board is plugged into the USB port marked USB2.0/OTG (not DEBUG) and its LED blinks."
        echo "  2. The cable carries data (many USB-C cables are charge-only)."
        echo "  3. Wait ~20 s after plugging in, then run this again."
        echo "  4. If the board is on Ethernet, give its address:  PLUTO_URI=ip:<address> $0"
    fi
} >&2
exit 1
