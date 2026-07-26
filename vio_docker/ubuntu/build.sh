#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
#  build.sh  —  Run this to build the Docker image on Ubuntu
# ─────────────────────────────────────────────────────────────────────────────
set +e
cd "$(dirname "$0")/.."

echo "Ensuring Docker daemon is running..."
if ! docker info > /dev/null 2>&1; then
    echo "Docker daemon not running. Starting Docker..."
    sudo systemctl start docker
    echo "Waiting for Docker daemon to become ready..."
    while ! docker info > /dev/null 2>&1; do
        sleep 2
    done
fi

echo "Building VIO Docker image..."
docker compose build
RC=$?
if [ $RC -ne 0 ]; then
    echo ""
    echo "[ERROR] Build failed. See output above."
    read -rp "Press Enter to exit..."
    exit $RC
fi
echo ""
echo "Build complete."
read -rp "Press Enter to exit..."
