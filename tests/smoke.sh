#!/usr/bin/env bash
set -euo pipefail
simulator="$1"
scene="$2"
smoke="$3"
tmpdir=$(mktemp -d)
trap 'kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; rm -rf "$tmpdir"' EXIT
"$simulator" --socket "$tmpdir/simulator.sock" --benchmark-socket "$tmpdir/benchmark.sock" --scene "$scene" >"$tmpdir/server.log" 2>&1 &
pid=$!
for ((i=0; i<100; i++)); do
  if [[ -S "$tmpdir/simulator.sock" && -S "$tmpdir/benchmark.sock" ]]; then break; fi
  if ! kill -0 "$pid" 2>/dev/null; then cat "$tmpdir/server.log"; exit 1; fi
  sleep 0.1
done
"$smoke" "$tmpdir/simulator.sock" "$tmpdir/benchmark.sock"
