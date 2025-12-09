#!/usr/bin/env bash
# Run SCONE on another machine that has Docker and the scone-headless image.
#
#   scripts/remote.sh <host> push          # copy code, scenarios and data/raw to <host>
#   scripts/remote.sh <host> pull          # copy results/raw/{runs,eval,logs} back
#   scripts/remote.sh <host> run <args>    # python scripts/run_scone.py <args> on <host>, detached
#
# The remote copy lives in ~/Projects/drop-foot-ankle-exo-sim. The runner only
# needs the Python standard library there (PYTHONPATH=src). Load the image on
# the remote once with: docker save scone-headless:latest | ssh <host> docker load
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
[[ $# -ge 2 ]] || { echo "usage: $0 <host> {push|pull|run <args>}" >&2; exit 2; }
host="$1"; cmd="$2"; shift 2
remote="Projects/drop-foot-ankle-exo-sim"

case "$cmd" in
  push)
    rsync -az --delete \
      --exclude .git --exclude .venv --exclude results/raw --exclude '__pycache__' \
      --exclude '.pytest_cache' --exclude 'scenarios/.eval_*' \
      "$root/" "$host:$remote/"
    ;;
  pull)
    mkdir -p "$root/results/raw"
    rsync -az "$host:$remote/results/raw/runs" "$host:$remote/results/raw/eval" \
      "$host:$remote/results/raw/logs" "$root/results/raw/" 2>/dev/null || true
    ;;
  run)
    log="results/raw/logs/$(date +%Y%m%d-%H%M%S)-$$.log"
    ssh "$host" "zsh -lc 'cd $remote && mkdir -p results/raw/logs && \
      PYTHONPATH=src nohup python3 scripts/run_scone.py $* > $log 2>&1 < /dev/null & echo started: $log'"
    ;;
  *)
    echo "unknown command $cmd" >&2; exit 2 ;;
esac
