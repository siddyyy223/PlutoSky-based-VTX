#!/usr/bin/env bash
# Label the Pluto that is plugged in right now as the TX or RX board.
#   ./label_pluto.sh tx     (only the transmitter board plugged in)
#   ./label_pluto.sh rx     (only the receiver board plugged in)
# The label is the board's serial number, saved in pluto_boards.conf. After that,
# run_tx.sh / run_rx.sh always pick the right board, even with both on one PC.
set -u
cd "$(dirname "$0")"
ROLE=${1:-}
[[ "$ROLE" == tx || "$ROLE" == rx ]] || { echo "usage: $0 tx|rx"; exit 2; }
CONF=pluto_boards.conf

# Exactly one board must be attached (or PLUTO_URI given), so the label can't
# land on the wrong one. The role-less search refuses if there are several.
URI=$(./find_pluto.sh) || { echo "Plug in only the board to label as ${ROLE^^}, then run this again."; exit 1; }
SERIAL=$(timeout 5 iio_attr -u "$URI" -C hw_serial 2>/dev/null | awk '{print $2}')
[[ -n "$SERIAL" ]] || { echo "Could not read the serial number from $URI"; exit 1; }
MODEL=$(timeout 5 iio_attr -u "$URI" -C hw_model 2>/dev/null | cut -d' ' -f2-)

[[ -f $CONF ]] || printf '# Pluto board labels: <role> <serial> <description>. Written by ./label_pluto.sh\n' > "$CONF"
other=$(awk -v s="$SERIAL" -v r="$ROLE" '$1 !~ /^#/ && $2 == s && $1 != r {print $1}' "$CONF")
[[ -n "$other" ]] && echo "Note: this board was labelled ${other^^}; it is now ${ROLE^^}."
# Drop any old line for this role or this board, then add the new one.
awk -v s="$SERIAL" -v r="$ROLE" '$1 ~ /^#/ || ($1 != r && $2 != s)' "$CONF" > "$CONF.tmp" && mv "$CONF.tmp" "$CONF"
echo "$ROLE $SERIAL $MODEL" >> "$CONF"
echo "Labelled ${ROLE^^} board: serial $SERIAL ($MODEL), now at $URI"
echo "Tip: also put a physical sticker \"${ROLE^^}\" on the board."
