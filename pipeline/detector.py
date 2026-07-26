"""YOLOv8 object detection on RGB frames."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np


@dataclass
class Detection:
    cls_id: int
    label: str
    conf: float
    x1: int
    y1: int
    x2: int
    y2: int
    depth_m: Optional[float] = None


class ObjectDetector:
    def __init__(self, model_name: str = "yolov8n.pt", conf: float = 0.35):
        self.model_name = model_name
        self.conf = conf
        self._model = None
        self._error: Optional[str] = None

    @property
    def ready(self) -> bool:
        return self._model is not None

    @property
    def error(self) -> Optional[str]:
        return self._error

    def load(self) -> None:
        try:
            from ultralytics import YOLO

            self._model = YOLO(self.model_name)
            self._error = None
        except Exception as exc:  # noqa: BLE001
            self._model = None
            self._error = str(exc)

    def infer(self, bgr: np.ndarray) -> List[Detection]:
        if self._model is None:
            return []
        # Ultralytics expects RGB
        rgb = bgr[:, :, ::-1]
        results = self._model.predict(rgb, conf=self.conf, verbose=False)
        dets: List[Detection] = []
        if not results:
            return dets
        r0 = results[0]
        names = r0.names or {}
        if r0.boxes is None:
            return dets
        for box in r0.boxes:
            xyxy = box.xyxy[0].tolist()
            cls_id = int(box.cls[0].item())
            conf = float(box.conf[0].item())
            dets.append(
                Detection(
                    cls_id=cls_id,
                    label=str(names.get(cls_id, str(cls_id))),
                    conf=conf,
                    x1=int(xyxy[0]),
                    y1=int(xyxy[1]),
                    x2=int(xyxy[2]),
                    y2=int(xyxy[3]),
                )
            )
        return dets


def attach_depths(dets: List[Detection], depth_mm: np.ndarray) -> List[Detection]:
    if depth_mm is None or depth_mm.size == 0:
        return dets
    h, w = depth_mm.shape[:2]
    out: List[Detection] = []
    for d in dets:
        cx = int(np.clip((d.x1 + d.x2) / 2, 0, w - 1))
        cy = int(np.clip((d.y1 + d.y2) / 2, 0, h - 1))
        # sample small patch
        x0, x1 = max(0, cx - 2), min(w, cx + 3)
        y0, y1 = max(0, cy - 2), min(h, cy + 3)
        patch = depth_mm[y0:y1, x0:x1].astype(np.float32)
        valid = patch[patch > 0]
        depth_m = float(np.median(valid) / 1000.0) if valid.size else None
        out.append(
            Detection(
                cls_id=d.cls_id,
                label=d.label,
                conf=d.conf,
                x1=d.x1,
                y1=d.y1,
                x2=d.x2,
                y2=d.y2,
                depth_m=depth_m,
            )
        )
    return out
