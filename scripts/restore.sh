#!/usr/bin/env bash
#
# PostgreSQL restore script for Trade Bot
#
# Usage:
#   ./scripts/restore.sh backups/tradebot_20240101_120000.sql.gz
#
# Environment variables:
#   POSTGRES_HOST     (default: localhost)
#   POSTGRES_PORT     (default: 5432)
#   POSTGRES_USER     (default: tradebot)
#   POSTGRES_DB       (default: tradebot)
#   PGPASSWORD        (required for non-interactive use)
#

set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 <backup-file.sql.gz>"
  echo ""
  echo "Available backups:"
  ls -lht backups/*.sql.gz 2>/dev/null || echo "  No backups found in ./backups/"
  exit 1
fi

BACKUP_FILE="$1"
HOST="${POSTGRES_HOST:-localhost}"
PORT="${POSTGRES_PORT:-5432}"
USER="${POSTGRES_USER:-tradebot}"
DB="${POSTGRES_DB:-tradebot}"

if [ ! -f "$BACKUP_FILE" ]; then
  echo "Error: Backup file not found: ${BACKUP_FILE}"
  exit 1
fi

echo "[$(date)] WARNING: This will overwrite all data in ${DB}@${HOST}:${PORT}"
echo "[$(date)] Restoring from: ${BACKUP_FILE}"
read -r -p "Continue? [y/N] " confirm
if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
  echo "Aborted."
  exit 0
fi

echo "[$(date)] Restoring..."
gunzip -c "$BACKUP_FILE" | psql \
  -h "$HOST" \
  -p "$PORT" \
  -U "$USER" \
  -d "$DB" \
  --quiet

echo "[$(date)] Restore complete."
