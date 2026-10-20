#!/usr/bin/env bash
# Incremental download+convert+delete for OpenAlex works/.
#
# Works is ~595 GiB raw; we don't have headroom to keep it AND parquet AND DuckDB
# without dipping below the 250 GB safety threshold. So we process in date-batches:
# download chunk → convert chunk to parquet → delete raw chunk → next.
#
# Each date partition is `s3://openalex/data/works/updated_date=YYYY-MM-DD/`.
#
# Usage: ./works_incremental.sh [batch_size]   default 20

# NOTE: deliberately NOT `set -e`. We want per-partition errors to be logged
# and skipped, not terminate the whole loop. The original `set -e` caused a
# silent exit after batch 20 on 2026-04-29 — almost certainly a transient
# aws s3 sync glitch. Now we retry each partition up to 3 times and continue
# past failures, recording them in `logs/works-incremental.failed`.
set -uo pipefail

BATCH_SIZE="${1:-20}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_ROOT="${NEUROAI_DATA:-$HOME/data/neuroai-citation-network}"
WORKS_RAW="$DATA_ROOT/data/openalex-snapshot/works"
WORKS_PARQUET="$DATA_ROOT/data/parquet/works"
LOG="$REPO/logs/works-incremental.log"

VENV_BIN="$REPO/.venv/bin"
export PATH="$VENV_BIN:$PATH"
export TMPDIR="$DATA_ROOT/tmp"
mkdir -p "$TMPDIR" "$WORKS_RAW" "$WORKS_PARQUET" "$(dirname "$LOG")"

echo "$(date -Iseconds) START works incremental, batch_size=$BATCH_SIZE" >> "$LOG"

# 1. Enumerate all date partitions on S3.
# Reverse-chronological (newest updated_date first) so high-citation / recently-updated
# papers — including Tier 1 bridge papers (Zador 2023, Richards 2019, etc.) — land
# in early batches. Old papers still being cited also have recent updated_date.
PARTITIONS_FILE="$TMPDIR/works-partitions.txt"
aws s3 ls --no-sign-request s3://openalex/data/works/ \
  | awk '/PRE updated_date=/ {print $2}' \
  | sed 's|/$||' \
  | sort -r > "$PARTITIONS_FILE"
TOTAL_PARTS=$(wc -l < "$PARTITIONS_FILE")
echo "$(date -Iseconds) found $TOTAL_PARTS date partitions (reverse-chrono order)" >> "$LOG"

# 2. Skip already-converted partitions (allow resumption).
DONE_FILE="$REPO/logs/works-incremental.done"
touch "$DONE_FILE"

# 3. Process in batches.
BATCH_NUM=0
while IFS= read -r PART; do
  if grep -qxF "$PART" "$DONE_FILE"; then
    continue
  fi

  # Free-space gate: stop if below 300 GB.
  free_gb=$(df --output=avail -B G "$DATA_ROOT" | tail -1 | tr -d ' G')
  if [ "$free_gb" -lt 300 ]; then
    echo "$(date -Iseconds) HALT free=${free_gb}G < 300G; not starting new batch" >> "$LOG"
    exit 2
  fi

  BATCH_NUM=$((BATCH_NUM + 1))
  PART_RAW="$WORKS_RAW/$PART"
  echo "$(date -Iseconds) batch $BATCH_NUM: download $PART (free=${free_gb}G)" >> "$LOG"

  # Download with retry. aws s3 sync is idempotent — retries resume from
  # last completed file. Up to 3 attempts.
  mkdir -p "$PART_RAW"
  download_ok=0
  for attempt in 1 2 3; do
    if aws s3 sync --no-sign-request --no-progress \
         "s3://openalex/data/works/$PART/" "$PART_RAW/" >> "$LOG" 2>&1; then
      download_ok=1
      break
    fi
    echo "$(date -Iseconds) batch $BATCH_NUM: download attempt $attempt failed; retrying" >> "$LOG"
    sleep $((10 * attempt))
  done
  if [ "$download_ok" -ne 1 ]; then
    echo "$(date -Iseconds) batch $BATCH_NUM: DOWNLOAD FAILED after 3 attempts; skipping $PART" >> "$LOG"
    echo "$PART" >> "$REPO/logs/works-incremental.failed"
    rm -rf "$PART_RAW"
    continue
  fi

  # Convert this single date partition. Up to 2 attempts (OOM is the main risk;
  # convert_works_partition.py is single-process so a retry is just a re-run).
  echo "$(date -Iseconds) batch $BATCH_NUM: convert $PART" >> "$LOG"
  convert_ok=0
  for attempt in 1 2; do
    if python "$REPO/scripts/convert_works_partition.py" "$PART" >> "$LOG" 2>&1; then
      convert_ok=1
      break
    fi
    echo "$(date -Iseconds) batch $BATCH_NUM: convert attempt $attempt failed; retrying" >> "$LOG"
  done
  if [ "$convert_ok" -ne 1 ]; then
    echo "$(date -Iseconds) batch $BATCH_NUM: CONVERT FAILED; skipping $PART" >> "$LOG"
    echo "$PART" >> "$REPO/logs/works-incremental.failed"
    rm -rf "$PART_RAW"
    continue
  fi

  # Delete raw to reclaim space.
  rm -rf "$PART_RAW"
  echo "$(date -Iseconds) batch $BATCH_NUM: deleted raw $PART" >> "$LOG"
  echo "$PART" >> "$DONE_FILE"

  # Every BATCH_SIZE partitions, append a progress line to logs/build-status.md.
  DONE_COUNT=$(wc -l < "$DONE_FILE")
  if [ $((DONE_COUNT % BATCH_SIZE)) -eq 0 ]; then
    free_gb_now=$(df --output=avail -B G "$DATA_ROOT" | tail -1 | tr -d ' G')
    parquet_size=$(du -sh "$WORKS_PARQUET" 2>/dev/null | cut -f1)
    {
      echo ""
      echo "## works progress — $(date -Iseconds)"
      echo ""
      echo "- Date partitions converted: **$DONE_COUNT / $TOTAL_PARTS**"
      echo "- Free disk: ${free_gb_now} GB"
      echo "- Parquet works/ size: $parquet_size"
      echo ""
    } >> "$REPO/logs/build-status.md"
  fi
done < "$PARTITIONS_FILE"

echo "$(date -Iseconds) DONE works incremental" >> "$LOG"
