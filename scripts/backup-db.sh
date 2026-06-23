#!/bin/bash
# Automated daily database backup script
# Author: Shattyk Kuziyeva
# Fault Tolerance responsibility - RTO < 5 min

BACKUP_DIR="./backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

echo "Starting backup at $TIMESTAMP"

docker exec software-architecture-tournament-db-1 pg_dump \
  -U tournament_user tournament_db \
  > $BACKUP_DIR/tournament_$TIMESTAMP.sql

echo "Backup saved to $BACKUP_DIR/tournament_$TIMESTAMP.sql"

# Keep only last 7 backups
ls -t $BACKUP_DIR/tournament_*.sql | tail -n +8 | xargs rm -f
echo "Backup complete."
