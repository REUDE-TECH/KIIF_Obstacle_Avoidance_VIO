# Architecture

## Overview

The VIO Docker stack provides a GPS-denied navigation solution for ArduPilot-based vehicles using a Luxonis OAK-D camera. The system runs as three coordinated Docker containers and is extended with a file-based output pipeline for logging, debugging, and analysis.

All inter-process communication uses **Unix domain sockets** — there is no ROS dependency.

---

## Component Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Docker Host (./outputs/)                     │
│  depth/  pointclouds/  features/  imu/  pose/  mavlink/             │
└──────────┬──────────────────┬──────────────────────┬────────────────┘
           │ volume mount     │ volume mount          │ volume mount
           ▼                  ▼                       ▼
┌────────────────┐   ┌─────────────────┐   ┌──────────────────────┐
│ feature_tracker│   │  vins_fusion    │   │   mavlink_udp        │
│                │   │                 │   │                      │
│ OAK-D Camera   │   │  VIO Estimator  │   │  MAVLink Bridge      │
│ FeatureTracker │──▶│  (VINS-Fusion   │──▶│  (mavlink-udp-proxy  │
│ StereoDepth    │   │   apm_wiki)     │   │   apm_wiki)          │
│ IMU            │   │                 │   │                      │
│                │   │                 │   │        │             │
│ Writes:        │   │ Writes:         │   │ Writes:│             │
│  depth PNG/CSV │   │  pose/          │   │  mavlink/            │
│  pointclouds/  │   │  trajectory.csv │   │  mavlink_log.csv     │
│  features/     │   │                 │   │        │             │
│  imu/          │   │                 │   │        ▼             │
└───────┬────────┘   └────────┬────────┘   └────────┬─────────────┘
        │                     │                     │
        │ /tmp/chobits_imu    │ /tmp/chobits_server │ UART
        │ /tmp/chobits_       │ (Unix socket)       │ /dev/ttyAMA0
        │ features            │                     │
        │ (Unix sockets)      │                     ▼
        └────────────────────▶│             ArduPilot Flight
                              │             Controller (EKF3)
                              └─────────────────────────────▶
```

---

## Containers

### 1. `feature_tracker` (`oak_d_vins_cpp` / `apm_wiki`)

**Source:** `chobitsfan/oak_d_vins_cpp` (branch `apm_wiki`)

Connects to the OAK-D camera and runs the full sensor processing pipeline:

| OAK-D Node | Purpose |
|---|---|
| `MonoCamera` (left + right) | 640×400 @ 20 fps grayscale stereo |
| `FeatureTracker` (left + right) | Hardware-accelerated optical flow — tracks up to 150 corners |
| `StereoDepth` | SGM stereo matching → 16-bit disparity (1/16 sub-pixel units) |
| `IMU` | Accelerometer + gyroscope @ ~400 Hz |

**IPC outputs (Unix sockets):**
- `/tmp/chobits_imu` → IMU packets (timestamp + accel + gyro) at ~200 Hz
- `/tmp/chobits_features` → Feature bundles (timestamp + feature IDs + normalised coords + per-feature disparity depth)

**File outputs (via injected output_writer.h):**
- `outputs/depth/frame_XXXXXX_depth.png` — colorized disparity map (JET palette)
- `outputs/depth/frame_XXXXXX_depth.csv` — raw depth in mm per pixel (640×400 matrix)
- `outputs/pointclouds/frame_XXXXXX.ply` — ASCII PLY point cloud (X,Y,Z in metres)
- `outputs/features/frame_XXXXXX_features.png` — left grayscale + tracked feature dots
- `outputs/features/features_log.csv` — per-feature log: `timestamp_ns, feature_id, pixel_x, pixel_y, depth_mm`
- `outputs/imu/imu_log.csv` — continuous IMU log: `timestamp_ns, acc_x/y/z (m/s²), gyro_x/y/z (rad/s)`
- `outputs/session_info.json` — camera calibration and session metadata

### 2. `vins_fusion` (`VINS-Fusion` / `apm_wiki`)

**Source:** `chobitsfan/VINS-Fusion` (branch `apm_wiki`)

Runs the Visual-Inertial Odometry estimator. Consumes IMU and feature data from the Unix sockets and optimises the 6-DOF pose using a sliding-window bundle adjustment (Ceres Solver).

**IPC inputs:** `/tmp/chobits_imu`, `/tmp/chobits_features`

**IPC output:** `/tmp/chobits_server` → pose packet (position + quaternion + velocity)

**File outputs (via injected output_writer.h):**
- `outputs/pose/trajectory.csv` — continuous VIO state: `timestamp_s, x_m, y_m, z_m, qw, qx, qy, qz, vx_ms, vy_ms, vz_ms`

### 3. `mavlink_udp` (`mavlink-udp-proxy` / `apm_wiki`)

**Source:** `chobitsfan/mavlink-udp-proxy` (branch `apm_wiki`)

Reads the VIO pose from `/tmp/chobits_server` and forwards it to the ArduPilot flight controller as MAVLink `VISION_POSITION_ESTIMATE` messages over UART at 1.5 Mbaud.

**File outputs (via injected output_writer.h):**
- `outputs/mavlink/mavlink_log.csv` — every message sent: `timestamp_us, x_m, y_m, z_m, roll_rad, pitch_rad, yaw_rad, reset_counter`

---

## Output File Formats

### Depth CSV (`depth/frame_XXXXXX_depth.csv`)
- 400 rows × 640 columns
- Each cell: depth in **millimetres** (float, 1 decimal place)
- `0.0` = invalid / no stereo match
- Computed as: `depth_mm = focal_px × baseline_m × 1000 / (raw_disparity / 16)`

### Point Cloud PLY (`pointclouds/frame_XXXXXX.ply`)
- ASCII PLY format, one vertex per valid depth pixel
- Coordinates in **metres**, right-handed camera frame (Z forward, X right, Y down)

### Trajectory CSV (`pose/trajectory.csv`)
```
timestamp_s, x_m, y_m, z_m, qw, qx, qy, qz, vx_ms, vy_ms, vz_ms
```
- `timestamp_s` — seconds (nanosecond precision float)
- `x,y,z` — position in the VIO world frame (metres)
- `qw,qx,qy,qz` — orientation quaternion
- `vx,vy,vz` — linear velocity (m/s)

### IMU CSV (`imu/imu_log.csv`)
```
timestamp_ns, acc_x_ms2, acc_y_ms2, acc_z_ms2, gyro_x_rads, gyro_y_rads, gyro_z_rads
```

### MAVLink CSV (`mavlink/mavlink_log.csv`)
```
timestamp_us, x_m, y_m, z_m, roll_rad, pitch_rad, yaw_rad, reset_counter
```
Mirrors the exact fields of the MAVLink `VISION_POSITION_ESTIMATE` (#102) message.

---

## Output Implementation

All file output is implemented in a single header file (`/patches/output_writer.h`) that is copied into the Docker image at build time. A Python script (`/patches/patch_sources.py`) injects `#include "/patches/output_writer.h"` and the appropriate logging calls into the three C++ source files *after* `git clone` and *before* `make`, so the output code is compiled directly into each executable.

No additional processes, containers, or libraries are required.
