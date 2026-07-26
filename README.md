# KIIF_Obstacle_Avoidance_VIO

Unified Windows-native stack:

1. **Detect camera** (Luxonis OAK-D via DepthAI)
2. **VIO** — stereo features + IMU ego-motion estimate (VINS-Fusion-style outputs)
3. **Object detection** — YOLOv8
4. **Obstacle avoidance** — depth ROI + detections → STOP / SLOW / TURN / GO

## Why not Docker VINS on this PC?

Docker Desktop + `usbipd` loses the OAK-D during Myriad firmware USB re-enumeration
(`X_LINK_DEVICE_NOT_FOUND`). This app talks to the camera **natively on Windows**.

Full C++ **VINS-Fusion** lives in [`vio_docker/`](vio_docker/) (Linux / vehicle target).
Windows Docker Desktop + `usbipd` is not reliable for OAK-D boot; use native `run.bat` here,
or Linux with `vio_docker/ubuntu/`.

This app produces compatible trajectory-style CSV for analysis.

## Run

```powershell
cd C:\Users\rkraj\oa_obstacle_avoidance
.\run.bat
```

Open http://localhost:8501

## Tabs

| Tab | Purpose |
| --- | --- |
| Live Pipeline | Start/stop camera, VIO, detection, avoidance |
| Avoidance | Command + depth clearance plot |
| Detections | Latest YOLO overlay |
| VIO / Pose | Trajectory XY + velocity |
| Sessions | Saved outputs |

## Outputs

`outputs/session_YYYYMMDD_HHMMSS/`

- `trajectory.csv` — `t,x,y,z,qw,qx,qy,qz,vx,vy,vz`
- `detections.jsonl` — per-frame boxes
- `avoidance.csv` — command + min_depth_m
- `preview.jpg` — last annotated frame

## Deploy on Render (demo only)

Same Render service: [oak-obstacle-avoidance](https://oak-obstacle-avoidance.onrender.com)  
Dashboard: `srv-d9inor7avr4c73b5mtm0`

Cloud has no USB camera — demo feed only. See **[RENDER_DEPLOY.md](RENDER_DEPLOY.md)**.

`vio_docker/` is for local/Linux builds; it is **not** started on Render.

## VIO Docker (local / Linux)

```text
vio_docker/windows/   # attach_oak, build, run (Windows + Docker Desktop)
vio_docker/ubuntu/    # native Linux USB path (recommended for full VINS)
```

## Copy back to team share

When `Z:\Engineering Team\...` is available:

```powershell
xcopy /E /I /Y C:\Users\rkraj\oa_obstacle_avoidance "Z:\Engineering Team\10.1 Obstacle avoidance\camera_check\oa_pipeline"
```
