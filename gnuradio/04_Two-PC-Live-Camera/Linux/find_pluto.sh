#!/usr/bin/env bash
# Print the libiio URI of a Pluto attached to this PC, e.g. "usb:1.3.5".
#   ./find_pluto.sh tx       the board labelled TX in pluto_boards.conf
#   ./find_pluto.sh rx       the board labelled RX
#   ./find_pluto.sh          any board (only if exactly one is attached)
#   ./find_pluto.sh --list   every attached board: "<uri> <board-ip> [role]"
# $PLUTO_URI, if set, is used as is.
#
# How boards are told apart: by the board's own IP address (ipaddr in the
# config.txt on its USB drive). Serial numbers and MAC addresses are NOT used:
# PlutoSky clone boards can all report the same ones. Each board on USB creates
# a network interface on this PC in the board's subnet, which links its usb: URI
# (fastest for samples) to its IP. Boards are compared by that /24 subnet, so two
# boards on one PC must have different subnets (e.g. 192.168.2.1 and 192.168.3.1).
# A board labelled for the other role is never returned.
# Exit status 1 (and a hint on stderr) if the board is not found.
set -u
cd "$(dirname "$0")"
ROLE=${1:-}
CONF=pluto_boards.conf

if [[ -n "${PLUTO_URI:-}" && "$ROLE" != --list ]]; then echo "$PLUTO_URI"; exit 0; fi

has_phy() { timeout 5 iio_attr -u "$1" -d 2>/dev/null | grep -q ad9361-phy; }

board_ip() {  # uri -> board IP as "a.b.c.1"-style text (subnet-based for usb:)
    local u=$1
    if [[ $u == ip:* ]]; then echo "${u#ip:}"; return; fi
    local b d dev n a
    IFS=. read -r b d _ <<<"${u#usb:}"
    for dev in /sys/bus/usb/devices/*; do
        [[ -f $dev/busnum && $(<"$dev/busnum") == "$b" && $(<"$dev/devnum") == "$d" ]] || continue
        for n in "$dev"/*/net/*; do
            [[ -e $n ]] || continue
            a=$(ip -4 -o addr show dev "$(basename "$n")" 2>/dev/null | awk '{print $4}' | head -1)
            [[ -n $a ]] && { echo "${a%.*/*}.1"; return; }   # host 192.168.3.10/24 -> 192.168.3.1
        done
    done
}
subnet() { echo "${1%.*}"; }
label_of() {  # board ip -> role from pluto_boards.conf (empty if not labelled)
    [[ -f $CONF && -n $1 ]] || return 0
    awk -v n="$(subnet "$1")" '$1 !~ /^#/ { s=$2; sub(/\.[0-9]+$/, "", s); if (s == n) { print $1; exit } }' "$CONF"
}

# Scan USB/network/mDNS: libiio 0.2x (Pop!_OS/Ubuntu package) uses "iio_info -s",
# libiio 1.x uses "iio_info -S". Result lines end in "[uri]". USB first.
candidates=()
while read -r u; do candidates+=("$u"); done < <(
    { timeout 8 iio_info -s 2>/dev/null; timeout 8 iio_info -S 2>/dev/null; } |
    grep -oE '\[(ip|usb):[^]]+\]' | tr -d '[]' | sort -u | sort -t: -k1,1r)
candidates+=(ip:192.168.2.1 ip:192.168.3.1 ip:10.10.10.1)

found=(); seen=" "
for u in "${candidates[@]}"; do
    ipaddr=$(board_ip "$u")
    key=${ipaddr:+$(subnet "$ipaddr")}; key=${key:-$u}
    [[ "$seen" == *" $key "* ]] && continue      # same board reached two ways
    has_phy "$u" || continue
    seen+="$key "
    found+=("$u ${ipaddr:-unknown-ip} $(label_of "$ipaddr")")
done

if [[ "$ROLE" == --list ]]; then
    for f in "${found[@]}"; do echo "$f"; done
    exit 0
fi

pick=""
if [[ -n "$ROLE" ]]; then
    for f in "${found[@]}"; do read -r u i r <<<"$f"; [[ "$r" == "$ROLE" ]] && pick=$u && break; done
    if [[ -z "$pick" ]] && ! grep -qE "^$ROLE[[:space:]]" "$CONF" 2>/dev/null; then
        # No board labelled for this role yet: accept a single unlabelled board.
        free=(); for f in "${found[@]}"; do read -r u i r <<<"$f"; [[ -z "$r" ]] && free+=("$u"); done
        if [[ ${#free[@]} -eq 1 ]]; then pick=${free[0]}; fi
    fi
elif [[ ${#found[@]} -eq 1 ]]; then
    read -r pick _ <<<"${found[0]}"
fi

if [[ -n "$pick" ]]; then echo "$pick"; exit 0; fi

{
    if [[ ${#found[@]} -gt 0 ]]; then
        echo "Pluto boards attached:"
        for f in "${found[@]}"; do read -r u i r <<<"$f"; echo "  $u  board IP $i  ${r:+(labelled ${r^^})}"; done
    fi
    if [[ -n "$ROLE" ]] && grep -qE "^$ROLE[[:space:]]" "$CONF" 2>/dev/null; then
        echo "The ${ROLE^^} board (IP $(awk -v r="$ROLE" '$1==r{print $2}' "$CONF")) is not connected."
    elif [[ ${#found[@]} -gt 1 ]]; then
        echo "More than one board: label them once with ./label_pluto.sh tx|rx"
    else
        echo "No Pluto found. Check:"
        echo "  1. The board is plugged into the USB port marked USB2.0/OTG (not DEBUG) and its LED blinks."
        echo "  2. The cable carries data (many USB-C cables are charge-only)."
        echo "  3. Wait ~20 s after plugging in, then run this again."
        echo "  4. If the board is on Ethernet, give its address:  PLUTO_URI=ip:<address> $0"
    fi
} >&2
exit 1
