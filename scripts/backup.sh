#!/usr/bin/env bash
#
# PostgreSQL backup script for Trade Bot
#
# Usage:
#   ./scripts/backup.sh                    # Backup to default location
#   ./scripts/backup.sh /path/to/dir       # Backup to specific directory
#   BACKUP_RETENTION_DAYS=14 ./scripts/backup.sh  # Custom retention
#
# Environment variables:
#   POSTGRES_HOST     (default: localhost)
#   POSTGRES_PORT     (default: 5432)
#   POSTGRES_USER     (default: tradebot)
#   POSTGRES_DB       (default: tradebot)
#   PGPASSWORD        (required for non-interactive use)
#   BACKUP_RETENTION_DAYS (default: 7)
#

set -euo pipefail

BACKUP_DIR="${1:-./backups}"
HOST="${POSTGRES_HOST:-localhost}"
PORT="${POSTGRES_PORT:-5432}"
USER="${POSTGRES_USER:-tradebot}"
DB="${POSTGRES_DB:-tradebot}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FILENAME="${DB}_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting backup of ${DB}@${HOST}:${PORT}..."

pg_dump \
  -h "$HOST" \
  -p "$PORT" \
  -U "$USER" \
  -d "$DB" \
  --no-owner \
  --no-privileges \
  --format=plain \
  | gzip > "${BACKUP_DIR}/${FILENAME}"

SIZE=$(du -h "${BACKUP_DIR}/${FILENAME}" | cut -f1)
echo "[$(date)] Backup complete: ${FILENAME} (${SIZE})"

# Prune old backups
PRUNED=0
if [ "$RETENTION_DAYS" -gt 0 ]; then
  while IFS= read -r old_backup; do
    rm -f "$old_backup"
    PRUNED=$((PRUNED + 1))
  done < <(find "$BACKUP_DIR" -name "${DB}_*.sql.gz" -mtime +"$RETENTION_DAYS" -type f 2>/dev/null)
fi

if [ "$PRUNED" -gt 0 ]; then
  echo "[$(date)] Pruned ${PRUNED} backup(s) older than ${RETENTION_DAYS} days"
fi

echo "[$(date)] Done. Backups in ${BACKUP_DIR}:"
ls -lh "${BACKUP_DIR}"/${DB}_*.sql.gz 2>/dev/null | tail -5
