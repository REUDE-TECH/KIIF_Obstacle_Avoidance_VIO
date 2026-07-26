# KIIF_Obstacle_Avoidance_VIO

Unified Windows-native stack:

1. **Detect camera** (Luxonis OAK-D via DepthAI)
2. **VIO** — stereo features + IMU ego-motion estimate (VINS-Fusion-style outputs)
3. **Object detection** — YOLOv8
4. **Obstacle avoidance** — depth ROI + detections → STOP / SLOW / TURN / GO

## Why not Docker VINS on this PC?

Docker Desktop + `usbipd` loses the OAK-D during Myriad firmware USB re-enumeration
(`X_LINK_DEVICE_NOT_FOUND`). This app talks to the camera **natively on Windows**.

Full C++ **VINS-Fusion** (`vio_docker`) remains the Linux / vehicle target.
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

Cloud has no USB camera. Use the lightweight demo build:

See **[RENDER_DEPLOY.md](RENDER_DEPLOY.md)** — `render.yaml` + `requirements-render.txt`.

On the live site: click **Start demo**.

## Copy back to team share

When `Z:\Engineering Team\...` is available:

```powershell
xcopy /E /I /Y C:\Users\rkraj\oa_obstacle_avoidance "Z:\Engineering Team\10.1 Obstacle avoidance\camera_check\oa_pipeline"
```
