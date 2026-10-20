#!/usr/bin/env bash
# Download a single OpenAlex snapshot partition via aws s3 sync (no-sign-request).
# Usage: ./download_snapshot.sh <partition>   e.g. topics, sources, works
#
# Writes to $NEUROAI_DATA/data/openalex-snapshot/<partition>/ (default ~/data/neuroai-citation-network)
# Logs to <repo>/logs/download-<partition>.log
#
# Exits non-zero on aws failure. Idempotent (re-run resumes).

set -euo pipefail

PARTITION="${1:?usage: $0 <partition> (e.g. topics, sources, works)}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_ROOT="${NEUROAI_DATA:-$HOME/data/neuroai-citation-network}"
DEST="$DATA_ROOT/data/openalex-snapshot/$PARTITION"
LOG="$REPO/logs/download-${PARTITION}.log"

mkdir -p "$DEST"
mkdir -p "$(dirname "$LOG")"

# Use venv's aws (installed via uv pip install awscli)
VENV_BIN="$REPO/.venv/bin"
if [ -x "$VENV_BIN/aws" ]; then
  export PATH="$VENV_BIN:$PATH"
fi

# TMPDIR off /tmp (root partition) onto the data drive
export TMPDIR="$DATA_ROOT/tmp"
mkdir -p "$TMPDIR"

echo "$(date -Iseconds) start partition=$PARTITION dest=$DEST" >> "$LOG"
aws s3 sync \
  --no-sign-request \
  --no-progress \
  "s3://openalex/data/$PARTITION/" \
  "$DEST/" >> "$LOG" 2>&1

echo "$(date -Iseconds) done partition=$PARTITION" >> "$LOG"
du -sh "$DEST" >> "$LOG"
