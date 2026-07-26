#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
#  run.sh  —  Run this to start all VIO containers on Ubuntu
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

# Remove any old session token so a new timestamped folder is generated
if [ -f "outputs/current_session.txt" ]; then
    rm "outputs/current_session.txt"
fi

echo "Creating outputs directory..."
mkdir -p outputs

echo ""
echo "Starting Docker containers..."
docker compose up -d

RC=$?
if [ $RC -ne 0 ]; then
    echo ""
    echo "[ERROR] Failed to start containers. See output above."
    read -rp "Press Enter to exit..."
    exit $RC
fi

sleep 2

echo "Opening terminals to follow logs for all containers..."
if command -v gnome-terminal > /dev/null 2>&1; then
    gnome-terminal -- bash -c "docker logs -f feature_tracker; exec bash" 2>/dev/null &
    gnome-terminal -- bash -c "docker logs -f vins_fusion; exec bash" 2>/dev/null &
    gnome-terminal -- bash -c "docker logs -f mavlink_udp; exec bash" 2>/dev/null &
elif command -v xterm > /dev/null 2>&1; then
    xterm -e "docker logs -f feature_tracker" &
    xterm -e "docker logs -f vins_fusion" &
    xterm -e "docker logs -f mavlink_udp" &
else
    echo "  (No supported terminal emulator found — follow logs manually)"
    echo "    docker logs -f feature_tracker"
    echo "    docker logs -f vins_fusion"
    echo "    docker logs -f mavlink_udp"
fi

echo ""
echo "Containers started."
echo "Outputs will be written to ./outputs/session_YYYYMMDD_HHMMSS/"
echo "  ./outputs/session_YYYYMMDD_HHMMSS/depth/        — Depth map PNG + CSV (mm per pixel)"
echo "  ./outputs/session_YYYYMMDD_HHMMSS/pointclouds/  — Point cloud PLY files"
echo "  ./outputs/session_YYYYMMDD_HHMMSS/features/     — Feature overlay PNG + CSV"
echo "  ./outputs/session_YYYYMMDD_HHMMSS/imu/          — IMU log CSV"
echo "  ./outputs/session_YYYYMMDD_HHMMSS/pose/         — VIO trajectory CSV"
echo "  ./outputs/session_YYYYMMDD_HHMMSS/mavlink/      — MAVLink VISION_POSITION_ESTIMATE CSV"
echo "  ./outputs/session_YYYYMMDD_HHMMSS/raw/          — Raw left, right, rgb, and depth video files (.mp4)"
echo ""
echo ""

while :; do
    read -n 1 -s -r -p "Press 's' to STOP recording and shut down containers..." key
    if [[ "$key" == "s" || "$key" == "S" ]]; then
        echo ""
        break
    fi
done

echo ""
echo "Stopping VIO containers..."
docker compose down
RC=$?
if [ $RC -ne 0 ]; then
    echo ""
    echo "[ERROR] Failed to stop containers."
    read -rp "Press Enter to exit..."
    exit $RC
fi
echo ""
echo "Containers stopped."
read -rp "Press Enter to exit..."
