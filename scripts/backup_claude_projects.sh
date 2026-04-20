#!/usr/bin/env bash
# Periodically rsync ~/.claude/projects to a persistent archive.
# Install as a cron job or launchd agent to run daily/weekly so Claude Code's
# 30-day cleanup doesn't erase your session history.
#
# Usage:
#   ./scripts/backup_claude_projects.sh [archive_dir]
#
# Default archive: ~/ClaudeCodeArchive

set -euo pipefail

ARCHIVE_DIR="${1:-$HOME/ClaudeCodeArchive}"
SRC="$HOME/.claude/projects"
TS=$(date +%Y-%m-%d)

mkdir -p "$ARCHIVE_DIR"

# --update keeps only newer files; never deletes archived history
rsync -a --update --exclude='*.tmp' "$SRC/" "$ARCHIVE_DIR/current/"

# Optionally also produce a dated snapshot (hardlink-based, cheap)
if command -v rsync >/dev/null; then
  rsync -a --link-dest="$ARCHIVE_DIR/current" "$ARCHIVE_DIR/current/" "$ARCHIVE_DIR/snapshots/$TS/" 2>/dev/null || true
fi

# Count files per month for a quick report
echo "Backed up to $ARCHIVE_DIR/current"
find "$ARCHIVE_DIR/current" -name "*.jsonl" -not -path "*/subagents/*" \
  -exec stat -f "%Sm" -t "%Y-%m" {} \; 2>/dev/null |
  sort | uniq -c
