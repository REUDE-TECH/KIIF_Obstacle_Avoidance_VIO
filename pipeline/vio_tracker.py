"""Lightweight visual-inertial ego-motion (VINS-Fusion-style outputs on Windows).

Uses DepthAI tracked features + stereo depth + IMU gyro/accel to estimate
planar pose. This is NOT the full Ceres VINS-Fusion optimizer (that remains
in vio_docker on Linux). Outputs match trajectory.csv schema for analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

import numpy as np


@dataclass
class VioState:
    t: float = 0.0
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    qw: float = 1.0
    qx: float = 0.0
    qy: float = 0.0
    qz: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0
    n_features: int = 0
    quality: float = 0.0  # 0..1


@dataclass
class VioTracker:
    """Integrate forward motion from feature disparity change + IMU yaw rate."""

    focal_px: float = 450.0
    yaw: float = 0.0
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    _prev_pts: Dict[int, Tuple[float, float]] = field(default_factory=dict)
    _prev_t: Optional[float] = None
    _gyro_bias_z: float = 0.0
    _calib_samples: int = 0

    def reset(self) -> None:
        self.yaw = 0.0
        self.x = self.y = self.z = 0.0
        self.vx = self.vy = 0.0
        self._prev_pts.clear()
        self._prev_t = None

    def update(
        self,
        t: float,
        features: list[tuple[int, float, float]],
        depth_mm: Optional[np.ndarray],
        gyro_z: float,
        accel: tuple[float, float, float],
    ) -> VioState:
        # Warm-up gyro bias (~0.5 s at 200 Hz would be ideal; we approximate)
        if self._calib_samples < 40:
            self._gyro_bias_z += gyro_z
            self._calib_samples += 1
            if self._calib_samples == 40:
                self._gyro_bias_z /= 40.0
            return VioState(t=t, n_features=len(features), quality=0.0)

        dt = 0.05 if self._prev_t is None else max(1e-3, t - self._prev_t)
        self._prev_t = t

        yaw_rate = gyro_z - self._gyro_bias_z
        self.yaw += float(yaw_rate) * dt

        # Forward speed from tracked feature optical flow + depth
        speed = 0.0
        used = 0
        cur = {int(i): (float(u), float(v)) for i, u, v in features}
        if depth_mm is not None and self._prev_pts:
            h, w = depth_mm.shape[:2]
            for fid, (u, v) in cur.items():
                if fid not in self._prev_pts:
                    continue
                u0, v0 = self._prev_pts[fid]
                du = u - u0
                # Focus on center features; expanding FOV ≈ approaching
                if abs(u - w / 2) > w * 0.35:
                    continue
                ix, iy = int(np.clip(u, 0, w - 1)), int(np.clip(v, 0, h - 1))
                d_mm = float(depth_mm[iy, ix])
                if d_mm < 300 or d_mm > 10000:
                    continue
                # Radial flow outward → approaching (positive forward)
                radial = (u - w / 2.0) * du
                # Convert rough pixel motion to m/s using depth / focal
                z_m = d_mm / 1000.0
                flow_mps = (-du) * (z_m / max(self.focal_px, 1.0)) / dt
                # Prefer center-column motion
                speed += float(np.clip(flow_mps, -2.0, 2.0))
                used += 1
                _ = radial
        if used > 0:
            speed /= used
        else:
            # Hold last speed with decay
            speed = self.vx * 0.8

        # Low-pass
        self.vx = 0.7 * self.vx + 0.3 * speed
        self.vy = 0.0
        self.x += self.vx * np.cos(self.yaw) * dt
        self.y += self.vx * np.sin(self.yaw) * dt

        # Accel Z roughly for height stability (not full VINS)
        az = accel[2]
        if abs(az) > 0.5:
            self.z += 0.0  # keep planar for avoidance demo

        self._prev_pts = cur
        n = len(cur)
        quality = float(np.clip(n / 80.0, 0.0, 1.0))

        # Yaw → quaternion (about Z)
        half = 0.5 * self.yaw
        qw, qz = float(np.cos(half)), float(np.sin(half))

        return VioState(
            t=t,
            x=float(self.x),
            y=float(self.y),
            z=float(self.z),
            qw=qw,
            qx=0.0,
            qy=0.0,
            qz=qz,
            vx=float(self.vx),
            vy=float(self.vy),
            vz=0.0,
            n_features=n,
            quality=quality,
        )
