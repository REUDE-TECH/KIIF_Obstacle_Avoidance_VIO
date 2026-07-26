#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
#  stop.sh  —  Run this to stop all VIO containers on Ubuntu
# ─────────────────────────────────────────────────────────────────────────────
set +e
cd "$(dirname "$0")/.."

echo "Stopping VIO containers..."
docker compose down
RC=$?
if [ $RC -ne 0 ]; then
    echo ""
    echo "[ERROR] Failed to stop containers. See output above."
    read -rp "Press Enter to exit..."
    exit $RC
fi
read -rp "Press Enter to exit..."
