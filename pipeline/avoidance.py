"""Obstacle avoidance from center depth + YOLO detections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from .detector import Detection


@dataclass
class AvoidanceCommand:
    action: str  # GO | SLOW | STOP | TURN_LEFT | TURN_RIGHT
    min_depth_m: float
    reason: str
    urgency: float  # 0..1


def _roi_min_depth_m(depth_mm: np.ndarray) -> float:
    h, w = depth_mm.shape[:2]
    x0, x1 = int(w * 0.30), int(w * 0.70)
    y0, y1 = int(h * 0.35), int(h * 0.85)
    roi = depth_mm[y0:y1, x0:x1].astype(np.float32)
    valid = roi[(roi > 300) & (roi < 10000)]
    if valid.size == 0:
        return 99.0
    # robust near percentile
    return float(np.percentile(valid, 10) / 1000.0)


def _lane_balance(depth_mm: np.ndarray) -> tuple[float, float]:
    h, w = depth_mm.shape[:2]
    y0, y1 = int(h * 0.40), int(h * 0.85)
    left = depth_mm[y0:y1, int(w * 0.10) : int(w * 0.40)].astype(np.float32)
    right = depth_mm[y0:y1, int(w * 0.60) : int(w * 0.90)].astype(np.float32)
    lv = left[(left > 300) & (left < 10000)]
    rv = right[(right > 300) & (right < 10000)]
    lmin = float(np.percentile(lv, 15) / 1000.0) if lv.size else 99.0
    rmin = float(np.percentile(rv, 15) / 1000.0) if rv.size else 99.0
    return lmin, rmin


def plan_avoidance(
    depth_mm: Optional[np.ndarray],
    detections: List[Detection],
    stop_m: float = 0.8,
    slow_m: float = 1.6,
) -> AvoidanceCommand:
    if depth_mm is None or depth_mm.size == 0:
        return AvoidanceCommand("STOP", 0.0, "no depth", 1.0)

    min_d = _roi_min_depth_m(depth_mm)
    left_d, right_d = _lane_balance(depth_mm)

    # Nearby detections in center
    near_labels = []
    for det in detections:
        if det.depth_m is None:
            continue
        if det.depth_m < slow_m and det.label.lower() in {
            "person",
            "car",
            "truck",
            "bus",
            "bicycle",
            "motorcycle",
            "chair",
            "couch",
            "obstacle",
        }:
            near_labels.append(f"{det.label}@{det.depth_m:.1f}m")
            min_d = min(min_d, det.depth_m)

    if min_d <= stop_m:
        # Turn toward freer side if possible
        if left_d > right_d + 0.3 and left_d > stop_m:
            return AvoidanceCommand(
                "TURN_LEFT",
                min_d,
                "obstacle ahead; left clearer" + (f" ({', '.join(near_labels)})" if near_labels else ""),
                1.0,
            )
        if right_d > left_d + 0.3 and right_d > stop_m:
            return AvoidanceCommand(
                "TURN_RIGHT",
                min_d,
                "obstacle ahead; right clearer" + (f" ({', '.join(near_labels)})" if near_labels else ""),
                1.0,
            )
        return AvoidanceCommand(
            "STOP",
            min_d,
            "obstacle too close" + (f" ({', '.join(near_labels)})" if near_labels else ""),
            1.0,
        )

    if min_d <= slow_m:
        return AvoidanceCommand(
            "SLOW",
            min_d,
            "obstacle in path" + (f" ({', '.join(near_labels)})" if near_labels else ""),
            float(np.clip((slow_m - min_d) / max(slow_m - stop_m, 1e-3), 0, 1)),
        )

    return AvoidanceCommand("GO", min_d, "path clear", 0.0)
