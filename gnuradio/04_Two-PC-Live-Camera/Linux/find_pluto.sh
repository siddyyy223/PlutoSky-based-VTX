#!/usr/bin/env bash
# Print the libiio URI of the Pluto attached to this PC, e.g. "ip:192.168.2.1".
# Order: $PLUTO_URI if set, then libiio scan results, then the usual USB-network
# addresses. A URI counts only if an AD9361/AD9363 (ad9361-phy) answers there.
# Exit status 1 (and a hint on stderr) if no board answers.
set -u

has_phy() { timeout 5 iio_attr -u "$1" -d 2>/dev/null | grep -q ad9361-phy; }

candidates=()
[[ -n "${PLUTO_URI:-}" ]] && candidates+=("$PLUTO_URI")
# Scan USB/network/mDNS: libiio 0.2x (Pop!_OS/Ubuntu package) uses "iio_info -s",
# libiio 1.x uses "iio_info -S". Result lines end in "[uri]".
while read -r u; do candidates+=("$u"); done < <(
    { timeout 8 iio_info -s 2>/dev/null; timeout 8 iio_info -S 2>/dev/null; } |
    grep -oE '\[(ip|usb):[^]]+\]' | tr -d '[]' | sort -u)
candidates+=(ip:192.168.2.1 ip:192.168.3.1 ip:10.10.10.1 ip:pluto.local)

for u in "${candidates[@]}"; do
    if has_phy "$u"; then echo "$u"; exit 0; fi
done

{
    echo "No Pluto found. Check:"
    echo "  1. The board is plugged into the USB port marked USB2.0/OTG (not DEBUG) and its LED blinks."
    echo "  2. Wait ~20 s after plugging in, then run this again."
    echo "  3. 'ip -br addr' shows a new USB network interface with a 192.168.2.x address."
    echo "  4. If the board has another address, run with it:  PLUTO_URI=ip:<address> $0"
} >&2
exit 1
