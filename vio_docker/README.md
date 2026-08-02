# VIO Docker Setup

This repository contains the Dockerized environment for the VIO stack
(`feature_tracker` → `vins_fusion` → optional `mavlink_udp`).

## Documentation

- [Setup Guide](docs/setup_guide.md)
- [Architecture](docs/architecture.md)
- [Troubleshooting](docs/troubleshooting.md)

---

## Local host workflow (this Windows PC)

Use this section for day-to-day testing on
`Z:\Engineering Team\10.1 Obstacle avoidance\camera_check`.

### Which path should I use?

| Goal | Use | URL / result |
| ---- | --- | ------------ |
| Live OAK-D + avoidance UI on this PC | **A — Native Streamlit** (recommended) | http://localhost:8501 |
| Full C++ VINS-Fusion in Docker | **B — vio_docker** | containers + `vio_docker\outputs\` |
| Cloud demo (no USB camera) | Render | https://oak-obstacle-avoidance.onrender.com |

> **Important (Windows + Docker Desktop):** DepthAI re-enumerates the OAK-D USB
> during boot. `usbipd` often drops the device → `feature_tracker` dies with
> `X_LINK_DEVICE_NOT_FOUND`. Prefer **Path A** on this laptop; use **Path B** on
> Linux (native USB) or when Docker attach is known-good.

---

### Path A — Native localhost dashboard (recommended)

Camera stays on **Windows** (must **not** be Attached to WSL/Docker).

#### Step-by-step

1. **Plug in** the OAK-D (USB3 port). Wait ~3 seconds.
2. **Free the camera from Docker/WSL** (if you ran vio_docker earlier):

   ```powershell
   usbipd list
   # If STATE is Attached:
   usbipd detach --busid <BUSID>
   ```

   Confirm STATE is `Shared` or `Not shared` — **not** `Attached`.

3. **Stop anything else** using the camera / port 8501 (old Streamlit, Docker VIO).

4. **Start the dashboard**:

   ```powershell
   cd "C:\Users\rkraj\oa_obstacle_avoidance"
   .\run.bat
   ```

   Team-share copy (same app):

   ```powershell
   cd "Z:\Engineering Team\10.1 Obstacle avoidance\camera_check\oa_pipeline"
   .\run.bat
   ```

5. Open **http://localhost:8501** in the browser.

6. In the sidebar:
   - Uncheck **Force demo mode** if you want the real camera
   - Click **Start pipeline**

7. Watch tabs: **Live Pipeline** → **Avoidance** → **Detections** → **VIO / Pose** → **Sessions**.

8. **Stop:** click **Stop** in the UI, then close the Streamlit terminal (or Ctrl+C).

#### Checklist (Path A)

- [ ] OAK-D plugged in (USB3)
- [ ] `usbipd list` → device **not** Attached
- [ ] http://localhost:8501 loads
- [ ] **Start pipeline** shows live preview (not only demo)

---

### Path B — vio_docker on local host (Windows Docker)

Full VINS-Fusion stack. On this PC it may still fail after attach; keep Path A as fallback.

#### First-time only

| Step | Action |
| ---- | ------ |
| 1 | Double-click `windows\install_prereqs.bat` (UAC) — WSL2, Docker Desktop, usbipd |
| 2 | Reboot if Windows asks |
| 3 | Open **Docker Desktop** → wait until Engine is green (WSL 2) |
| 4 | `windows\build.bat` — builds `oak-d-vio:latest` (long first build) |

#### Every session (step-by-step)

1. **Close Path A** — stop Streamlit on :8501 so Windows releases the OAK-D.

2. **Plug in** OAK-D (USB3).

3. **Attach camera into docker-desktop** (Admin / UAC):

   ```powershell
   cd "Z:\Engineering Team\10.1 Obstacle avoidance\camera_check\vio_docker"
   .\windows\attach_oak.bat
   ```

   - Leave the **AUTO-ATTACH** PowerShell window **open**
   - Confirm: `usbipd list` shows **Attached**
   - Confirm: `wsl -d docker-desktop -e lsusb` shows `03e7`

4. **Run VIO** (feature_tracker + vins_fusion):

   ```powershell
   .\windows\run.bat
   ```

   - Log windows open for `feature_tracker` and `vins_fusion`
   - Press **`s`** in the launcher terminal to stop

5. **Check health**
   - Good: `feature_tracker` keeps running; files appear under `outputs\session_*`
   - Bad: `X_LINK_DEVICE_NOT_FOUND` / exit 139 → Windows usbipd limit; switch to **Path A**

6. **After Docker VIO** — free the camera for Path A again:

   ```powershell
   usbipd detach --busid <BUSID>
   ```

#### Checklist (Path B)

- [ ] Docker Desktop green
- [ ] `docker images oak-d-vio` shows `oak-d-vio:latest`
- [ ] Streamlit / other DepthAI apps closed
- [ ] `attach_oak.bat` → Attached + `03e7` in docker-desktop `lsusb`
- [ ] AUTO-ATTACH window left open
- [ ] `run.bat` → no `X_LINK_DEVICE_NOT_FOUND`

#### Manual USB attach (optional)

```powershell
usbipd list
usbipd bind --busid <BUSID>
usbipd attach --wsl docker-desktop --auto-attach --busid <BUSID>
wsl -d docker-desktop -e lsusb   # must show 03e7
```

---

### Quick decision flow

```text
Need live camera UI on this laptop?
  └─ YES → Path A (oa_pipeline / run.bat) → http://localhost:8501
Need full C++ VINS-Fusion outputs?
  └─ Linux PC/vehicle → ubuntu/run.sh (best)
  └─ This Windows PC → Path B (may fail) → if X_LINK → Path A
```

---

## Quick Start

### Linux (Ubuntu)

To run the environment on Linux, you need **Docker Engine** installed.

#### Prerequisites

1. **Docker Engine**: The `install.sh` script will install Docker and configure user groups automatically. Alternatively, install [Docker Engine](https://docs.docker.com/engine/install/ubuntu/) manually.
2. **USB Permissions (Required for OAK-D)**: The OAK-D camera requires udev rules. See the [DepthAI USB setup guide](https://docs.luxonis.com/software/depthai/manual-install/) for details.

#### Script Reference

The repository includes `.sh` scripts in the `ubuntu/` folder:

| File                | What it does                                                                                          |
| ------------------- | ----------------------------------------------------------------------------------------------------- |
| `ubuntu/install.sh` | Installs Docker and adds the current user to the `docker` group (run once)                            |
| `ubuntu/build.sh`   | Ensures Docker is running, then builds the Docker image                                               |
| `ubuntu/run.sh`     | Ensures Docker is running, starts all containers + opens log terminal windows (Press **`s`** to stop) |
| `ubuntu/stop.sh`    | Stops all containers (alternative fallback)                                                           |

#### Build and Run

```bash
# 1. Clone the repository
git clone --branch docker --single-branch https://github.com/REUDE-Technologies/REUDE_KIIF_GPS_Denied_OAK_D_Project vio_docker
cd vio_docker

# 2. Make the scripts executable
chmod +x ubuntu/*.sh

# 3. Install Docker and configure user groups (run once)
./ubuntu/install.sh

# IMPORTANT: Please log out and log back in (or restart your terminal)
# for the docker group changes to take effect!

# 4. Build the Docker image (auto-starts Docker if needed)
./ubuntu/build.sh

# 5. Run the containers (auto-starts Docker if needed)
./ubuntu/run.sh
```

_(Three log windows open automatically for `feature_tracker`, `vins_fusion`, and `mavlink_udp`. To stop recording and shut down all containers, press the **`s`** key in the launcher terminal.)_

**Stop** the containers (alternative):

```bash
./ubuntu/stop.sh
```

---

### Windows

To run the environment on Windows, you can use **Docker Desktop** (with the WSL 2 backend).

#### First-time install (required once)

This PC needs **WSL 2**, **Docker Desktop**, and **usbipd-win** before the VIO image can build or see the OAK-D.

> ⚠️ **Do NOT double-click `.ps1` files.** Windows opens them in Notepad by default.
> Use the `.bat` launchers below (they request Administrator / UAC when needed).

| Step | Double-click / run | What it does |
| ---- | ------------------ | ------------ |
| 1 | `windows\install_prereqs.bat` | Installs WSL 2, Docker Desktop, usbipd-win; creates `outputs\` |
| 2 | Reboot if Windows asks | Required after the first WSL install |
| 3 | Open **Docker Desktop** once | Wait until the engine is green (WSL 2 backend) |
| 4 | Plug in OAK-D → `windows\attach_oak.bat` | Binds + attaches the camera USB into WSL |
| 5 | `windows\build.bat` | Builds `oak-d-vio:latest` (VINS-Fusion + feature tracker + MAVLink) |
| 6 | `windows\run.bat` | Starts live camera VIO; press **`s`** to stop |

Manual alternative for step 1 (Administrator PowerShell):

```powershell
wsl --install
winget install -e --id Docker.DockerDesktop --accept-package-agreements
winget install -e --id dorssel.usbipd-win --accept-package-agreements
```

#### USB Device Pass-through (Required for OAK-D)

Prefer `windows\attach_oak.bat`. Manual steps:

```powershell
# List USB devices to find the BUSID of the OAK-D camera
usbipd list

# Bind the device (required only once)
usbipd bind --busid <BUSID>

# Attach the device to WSL
usbipd attach --wsl --busid <BUSID>
```

#### Build and Run

**Option A — Double-click launchers (easiest)**

The repository includes `.bat` files in the `windows\` folder. Just double-click them in File Explorer:

| File                         | What it does                                                                  |
| ---------------------------- | ----------------------------------------------------------------------------- |
| `windows\install_prereqs.bat`| One-time: WSL 2 + Docker Desktop + usbipd-win                                 |
| `windows\attach_oak.bat`     | Attach OAK-D USB to WSL (before each run if detached)                         |
| `windows\build.bat`          | Builds the Docker image (run once after cloning / after Docker is ready)      |
| `windows\run.bat`            | Starts all containers + opens log windows (Press 's' in the terminal to stop) |
| `windows\stop.bat`           | Stops all containers (alternative fallback)                                   |

**Option B — PowerShell terminal**

1. One-time prerequisites (Administrator PowerShell, then reboot if asked):
   ```powershell
   cd "Z:\Engineering Team\10.1 Obstacle avoidance\camera_check\vio_docker"
   .\windows\install_prereqs.bat
   ```
2. Open Docker Desktop; wait until the engine is green.
3. Plug in the OAK-D, then attach it to WSL:
   ```powershell
   .\windows\attach_oak.bat
   ```
4. **Build** the VIO image (first build compiles Ceres + VINS-Fusion + DepthAI + trackers — often 30–90+ minutes):
   ```powershell
   .\windows\build.bat
   ```
5. **Run** live camera VIO (obstacle / navigation sensing):
   ```powershell
   .\windows\run.bat
   ```
   Press **`s`** in the launcher terminal to stop.
6. **Stop** (alternative):
   ```powershell
   .\windows\stop.bat
   ```

---

## Camera-feed / obstacle sensing signals

This Docker stack is **Visual-Inertial Odometry + stereo depth**, not YOLO.
For real-time testing on this PC, prefer the **Local host workflow → Path A** above
(native dashboard includes detection + avoidance).

| Signal | Where it comes from | Use |
| ------ | ------------------- | --- |
| 6-DOF pose + velocity | `vins_fusion` → `outputs/.../pose/trajectory.csv` | Ego-motion / navigation |
| Per-pixel depth (mm) | `feature_tracker` → `outputs/.../depth/` | Range / free space |
| Point clouds | `outputs/.../pointclouds/*.ply` | 3-D obstacle geometry |
| Tracked features + IMU | `features/`, `imu/` | Debug VIO health |
| MAVLink vision pose | `mavlink/` | Feed ArduPilot EKF3 (optional FC) |

After a successful Path B run, confirm `outputs\session_*` contains `raw/`, `depth/`,
`pose/trajectory.csv`, and `imu/imu_log.csv`.

---

## Outputs

All three containers write structured data files to the `./outputs/` directory on your host machine. They automatically synchronize to write inside the same timestamped session subfolder (e.g. `./outputs/session_YYYYMMDD_HHMMSS/`). A new session folder is created automatically on each run.

### Output Directory Structure

```
outputs/
├── session_YYYYMMDD_HHMMSS/          ← one folder per run
│   ├── raw/
│   │   ├── raw_left.mp4              ← raw left camera feed
│   │   ├── raw_right.mp4             ← raw right camera feed
│   │   ├── raw_rgb.mp4               ← RGB camera feed (1080p)
│   │   └── depth.mp4                 ← colorized depth feed
│   ├── session_info.json             ← camera calibration + metadata
│   ├── depth/
│   │   ├── frame_000001_depth.png    ← colorized depth map (JET palette)
│   │   └── frame_000001_depth.csv    ← raw depth in mm, 400 rows × 640 cols
│   ├── pointclouds/
│   │   └── frame_000001.ply          ← ASCII PLY point cloud (X,Y,Z in metres)
│   ├── features/
│   │   ├── frame_000001_features.png ← left image with tracked feature dots
│   │   └── features_log.csv          ← per-feature log
│   └── imu/
│       └── imu_log.csv               ← continuous IMU log
├── pose/
│   └── trajectory.csv                ← VIO 6-DOF pose from VINS-Fusion
└── mavlink/
    └── mavlink_log.csv               ← MAVLink VISION_POSITION_ESTIMATE log
```

### Output Reference Table

| File                            | Source Process    | Content                                                            | Format                      |
| ------------------------------- | ----------------- | ------------------------------------------------------------------ | --------------------------- |
| `raw/raw_left.mp4`              | `feature_tracker` | Raw left camera feed                                               | MP4 (mp4v), 640×400         |
| `raw/raw_right.mp4`             | `feature_tracker` | Raw right camera feed                                              | MP4 (mp4v), 640×400         |
| `raw/raw_rgb.mp4`               | `feature_tracker` | Raw RGB camera feed                                                | MP4 (mp4v), 1920×1080       |
| `raw/depth.mp4`                 | `feature_tracker` | Colorized depth map video                                          | MP4 (mp4v), 640×400         |
| `depth/frame_N_depth.png`       | `feature_tracker` | Colorized stereo disparity map                                     | PNG, 640×400, JET palette   |
| `depth/frame_N_depth.csv`       | `feature_tracker` | Per-pixel depth in millimetres                                     | CSV, 400×640 floats         |
| `pointclouds/frame_N.ply`       | `feature_tracker` | 3-D point cloud from stereo                                        | ASCII PLY (X Y Z in metres) |
| `features/frame_N_features.png` | `feature_tracker` | Left camera + tracked feature dots                                 | PNG, 640×400                |
| `features/features_log.csv`     | `feature_tracker` | `timestamp_ns, feature_id, pixel_x, pixel_y, depth_mm`             | CSV                         |
| `imu/imu_log.csv`               | `feature_tracker` | `timestamp_ns, acc_x/y/z (m/s²), gyro_x/y/z (rad/s)`               | CSV                         |
| `pose/trajectory.csv`           | `vins_fusion`     | `timestamp_s, x, y, z (m), qw, qx, qy, qz, vx, vy, vz (m/s)`       | CSV                         |
| `mavlink/mavlink_log.csv`       | `mavlink_udp`     | `timestamp_us, x, y, z (m), roll, pitch, yaw (rad), reset_counter` | CSV                         |
| `session_info.json`             | `feature_tracker` | Camera focal length, baseline, principal point, resolution         | JSON                        |

### Notes

- **Depth units**: All depth values are in **millimetres**. Valid range for OAK-D: ~300 mm – 10,000 mm.
- **Point cloud frame**: Right-handed camera frame — Z forward, X right, Y down.
- **Trajectory frame**: VIO world frame initialised at first keyframe. Not geo-referenced.
- **Frame rate**: Depth/features logged at camera frame rate (20 fps). IMU at ~200 Hz. Pose at ~20 Hz.
- **Disk space**: Each depth CSV is ~1.2 MB; each PLY is ~1–3 MB. Budget ~300 MB/min at 20 fps.
