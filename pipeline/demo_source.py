"""Synthetic camera / VIO / detection feed for cloud deploy (Render) without OAK-D."""

from __future__ import annotations

import math
import time
from typing import List, Tuple

import cv2
import numpy as np

from .detector import Detection


class DemoSource:
    """Generates RGB, depth, features, IMU-like signals for dashboard demo."""

    def __init__(self, width: int = 640, height: int = 360):
        self.w = width
        self.h = height
        self.t0 = time.time()
        self._feat_id = 0

    def tick(self) -> tuple[np.ndarray, np.ndarray, list[tuple[int, float, float]], float, tuple[float, float, float], List[Detection]]:
        t = time.time() - self.t0
        # Moving scene
        rgb = np.zeros((self.h, self.w, 3), dtype=np.uint8)
        rgb[:] = (40, 44, 52)
        # Floor strip
        cv2.rectangle(rgb, (0, int(self.h * 0.55)), (self.w, self.h), (70, 70, 70), -1)
        # "Obstacle" blob oscillating in depth
        cx = int(self.w * (0.5 + 0.25 * math.sin(t * 0.7)))
        cy = int(self.h * 0.55)
        radius = 40 + int(10 * math.sin(t * 1.3))
        cv2.circle(rgb, (cx, cy), radius, (80, 80, 200), -1)
        cv2.putText(rgb, "DEMO MODE (no OAK-D)", (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 220, 255), 2)

        # Depth: nearer in center blob
        ys, xs = np.mgrid[0 : self.h, 0 : self.w]
        dist = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2)
        depth = np.full((self.h, self.w), 3500.0, dtype=np.float32)
        near = 600 + 400 * (0.5 + 0.5 * math.sin(t * 0.7))
        depth = np.where(dist < radius * 1.2, near, depth).astype(np.uint16)

        features: list[tuple[int, float, float]] = []
        for i in range(40):
            ang = t * 0.5 + i * 0.4
            fx = self.w * 0.5 + 120 * math.cos(ang + i)
            fy = self.h * 0.45 + 60 * math.sin(ang * 1.2 + i)
            features.append((i, float(fx), float(fy)))

        gyro_z = 0.15 * math.sin(t * 0.4)
        accel = (0.0, 0.0, 9.8)

        dets = [
            Detection(
                cls_id=0,
                label="obstacle",
                conf=0.85,
                x1=cx - radius,
                y1=cy - radius,
                x2=cx + radius,
                y2=cy + radius,
                depth_m=float(near) / 1000.0,
            )
        ]
        return rgb, depth, features, gyro_z, accel, dets
