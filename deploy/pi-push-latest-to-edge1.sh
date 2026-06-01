#!/usr/bin/env bash
# Run ON each Pi (as root). Pushes newest session frame to edge-1 storage.
# Usage on pi4-2:  CAMERA_ID=pi4-2 ./pi-push-latest-to-edge1.sh
set -euo pipefail

STORAGE_HOST="${STORAGE_HOST:-100.103.209.30}"
STORAGE_USER="${STORAGE_USER:-david}"
CAMERA_ID="${CAMERA_ID:?set CAMERA_ID=pi4-2 or pi4-3}"

LATEST="$(ls -1t /root/edge-client/data/session_*/*${CAMERA_ID}*.jpg 2>/dev/null | head -1)"
if [[ -z "${LATEST}" ]]; then
  echo "No frames found for ${CAMERA_ID}"
  exit 1
fi

TMP="latest/${CAMERA_ID}.jpg.tmp"
DEST="latest/${CAMERA_ID}.jpg"

rsync -av "${LATEST}" "${STORAGE_USER}@${STORAGE_HOST}:/data/frames/${TMP}"
ssh "${STORAGE_USER}@${STORAGE_HOST}" "mv /data/frames/${TMP} /data/frames/${DEST}"
echo "Pushed ${LATEST} -> edge-1:/data/frames/${DEST}"
