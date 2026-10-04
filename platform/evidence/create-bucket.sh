#!/bin/sh
# Creates the write-once evidence bucket on an S3-compatible store (MinIO
# client shown). Object lock in compliance mode means no one, admins included,
# can change or delete a bundle before its retention ends.
set -eu
ALIAS="${1:?usage: create-bucket.sh <mc-alias> [bucket] [retention-days]}"
BUCKET="${2:-factory-evidence}"
DAYS="${3:-730}"   # 2 years, the default in the plan

mc mb --with-lock "$ALIAS/$BUCKET"
mc retention set --default COMPLIANCE "${DAYS}d" "$ALIAS/$BUCKET"
mc version enable "$ALIAS/$BUCKET"
echo "Created $ALIAS/$BUCKET with ${DAYS}-day compliance retention"
