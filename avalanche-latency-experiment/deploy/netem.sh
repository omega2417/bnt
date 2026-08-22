#!/usr/bin/env bash
# Controlled delay, jitter and loss on an isolated experiment interface
# (protocol Listing 4).  Applies ONLY to topology T2; T0 and T1 must run
# with no netem at all, and the script refuses to touch a default route.
set -euo pipefail

: "${DEV:?isolated experiment interface is required}"
: "${DELAY_MS:?one-way delay in ms is required}"
: "${JITTER_MS:=2}"
: "${LOSS_PCT:=0.1}"

if ip route show default | grep -qw "$DEV"; then
  echo "refusing to shape $DEV: it carries the default route" >&2
  exit 1
fi

sudo tc qdisc replace dev "$DEV" root netem \
  delay "${DELAY_MS}ms" "${JITTER_MS}ms" distribution normal \
  loss "${LOSS_PCT}%"

echo "applied netem on $DEV:"
tc qdisc show dev "$DEV"

cat <<'NOTE'
Measure the actual RTT/jitter/loss matrix after applying netem and record it
in the run passport: the requested target and the realised path are not the
same number.  Remove the shaping after the run with:

  sudo tc qdisc del dev "$DEV" root
NOTE
