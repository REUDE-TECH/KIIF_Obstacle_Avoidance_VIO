"""Threaded pipeline: camera → VIO → detection → avoidance → session logs."""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np

from .avoidance import AvoidanceCommand, plan_avoidance
from .camera_device import colorize_depth, depthai_available, list_oak_devices, open_device
from .demo_source import DemoSource
from .detector import Detection, ObjectDetector, attach_depths
from .vio_tracker import VioState, VioTracker


def cloud_demo_default() -> bool:
    return os.environ.get("DEMO_MODE", "").lower() in {"1", "true", "yes"} or bool(
        os.environ.get("RENDER")
    )


@dataclass
class PipelineState:
    running: bool = False
    error: Optional[str] = None
    device_mxid: str = ""
    fps: float = 0.0
    mode: str = "idle"  # live | demo
    vio: VioState = field(default_factory=VioState)
    avoidance: AvoidanceCommand = field(
        default_factory=lambda: AvoidanceCommand("STOP", 0.0, "idle", 0.0)
    )
    detections: List[Detection] = field(default_factory=list)
    preview_jpeg: Optional[bytes] = None
    session_dir: Optional[Path] = None
    frames: int = 0


class PipelineRunner:
    def __init__(self, output_root: Path, detect_every: int = 2):
        self.output_root = Path(output_root)
        self.detect_every = max(1, detect_every)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.state = PipelineState()
        self.detector = ObjectDetector()
        self.vio = VioTracker()

    def snapshot(self) -> PipelineState:
        with self._lock:
            return PipelineState(
                running=self.state.running,
                error=self.state.error,
                device_mxid=self.state.device_mxid,
                fps=self.state.fps,
                mode=self.state.mode,
                vio=self.state.vio,
                avoidance=self.state.avoidance,
                detections=list(self.state.detections),
                preview_jpeg=self.state.preview_jpeg,
                session_dir=self.state.session_dir,
                frames=self.state.frames,
            )

    def start(
        self,
        mxid: Optional[str] = None,
        fps: float = 15.0,
        force_demo: Optional[bool] = None,
    ) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, args=(mxid, fps, force_demo), daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=8.0)
            self._thread = None
        with self._lock:
            self.state.running = False

    def _open_session(self, meta: dict) -> Path:
        session = self.output_root / datetime.now().strftime("session_%Y%m%d_%H%M%S")
        session.mkdir(parents=True, exist_ok=True)
        (session / "device.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        return session

    def _run(
        self,
        mxid: Optional[str],
        fps: float,
        force_demo: Optional[bool],
    ) -> None:
        use_demo = force_demo if force_demo is not None else cloud_demo_default()
        if not use_demo:
            if not depthai_available() or not list_oak_devices():
                use_demo = True

        if use_demo:
            self._run_demo()
        else:
            self._run_live(mxid, fps)

    def _run_demo(self) -> None:
        traj_f = det_f = avoid_f = None
        try:
            session = self._open_session(
                {
                    "mode": "demo",
                    "note": "Cloud/demo feed — no physical OAK-D on Render",
                }
            )
            traj_f = open(session / "trajectory.csv", "w", encoding="utf-8")
            traj_f.write(
                "timestamp_s,x_m,y_m,z_m,qw,qx,qy,qz,vx_ms,vy_ms,vz_ms,n_features,quality\n"
            )
            det_f = open(session / "detections.jsonl", "w", encoding="utf-8")
            avoid_f = open(session / "avoidance.csv", "w", encoding="utf-8")
            avoid_f.write("timestamp_s,action,min_depth_m,urgency,reason\n")

            src = DemoSource()
            self.vio.reset()
            with self._lock:
                self.state.running = True
                self.state.error = None
                self.state.device_mxid = "DEMO"
                self.state.mode = "demo"
                self.state.session_dir = session
                self.state.frames = 0

            t0 = time.time()
            last_fps_t = t0
            fps_count = 0
            inst_fps = 0.0
            frame_i = 0

            while not self._stop.is_set():
                rgb, depth_mm, features, gyro_z, accel, dets = src.tick()
                now = time.time()
                t = now - t0
                vio = self.vio.update(t, features, depth_mm, gyro_z, accel)
                cmd = plan_avoidance(depth_mm, dets)

                vis = rgb.copy()
                depth_c = colorize_depth(depth_mm)
                vis = cv2.addWeighted(vis, 0.75, depth_c, 0.25, 0)
                for d in dets:
                    cv2.rectangle(vis, (d.x1, d.y1), (d.x2, d.y2), (0, 165, 255), 2)
                    cv2.putText(
                        vis,
                        f"{d.label} {d.depth_m:.1f}m",
                        (d.x1, max(16, d.y1 - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 165, 255),
                        1,
                        cv2.LINE_AA,
                    )
                cv2.putText(
                    vis,
                    f"{cmd.action}  d={cmd.min_depth_m:.2f}m",
                    (12, 56),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 255),
                    2,
                    cv2.LINE_AA,
                )
                ok, buf = cv2.imencode(".jpg", vis, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                jpeg = buf.tobytes() if ok else None
                if jpeg:
                    (session / "preview.jpg").write_bytes(jpeg)

                traj_f.write(
                    f"{vio.t:.6f},{vio.x:.6f},{vio.y:.6f},{vio.z:.6f},"
                    f"{vio.qw:.6f},{vio.qx:.6f},{vio.qy:.6f},{vio.qz:.6f},"
                    f"{vio.vx:.6f},{vio.vy:.6f},{vio.vz:.6f},{vio.n_features},{vio.quality:.3f}\n"
                )
                avoid_f.write(
                    f"{t:.6f},{cmd.action},{cmd.min_depth_m:.4f},{cmd.urgency:.3f},"
                    f"{cmd.reason.replace(',', ';')}\n"
                )
                det_f.write(
                    json.dumps(
                        {
                            "t": t,
                            "dets": [
                                {
                                    "label": d.label,
                                    "conf": d.conf,
                                    "xyxy": [d.x1, d.y1, d.x2, d.y2],
                                    "depth_m": d.depth_m,
                                }
                                for d in dets
                            ],
                        }
                    )
                    + "\n"
                )

                fps_count += 1
                if now - last_fps_t >= 1.0:
                    inst_fps = fps_count / (now - last_fps_t)
                    last_fps_t = now
                    fps_count = 0

                with self._lock:
                    self.state.vio = vio
                    self.state.avoidance = cmd
                    self.state.detections = dets
                    self.state.preview_jpeg = jpeg
                    self.state.fps = inst_fps
                    self.state.frames = frame_i + 1
                frame_i += 1
                time.sleep(0.07)

        except Exception as exc:  # noqa: BLE001
            with self._lock:
                self.state.error = str(exc)
                self.state.running = False
        finally:
            for f in (traj_f, det_f, avoid_f):
                if f is not None:
                    f.flush()
                    f.close()
            with self._lock:
                self.state.running = False

    def _run_live(self, mxid: Optional[str], fps: float) -> None:
        device = None
        traj_f = det_f = avoid_f = None
        try:
            enable_yolo = os.environ.get("ENABLE_YOLO", "1").lower() not in {
                "0",
                "false",
                "no",
            }
            if enable_yolo and not self.detector.ready:
                self.detector.load()

            devices = list_oak_devices()
            if not devices:
                raise RuntimeError(
                    "No OAK-D detected. Detach from WSL (usbipd detach), "
                    "use USB3, close other camera apps — or Start in Demo mode."
                )

            device, _ = open_device(mxid=mxid, fps=fps)
            mx = device.getMxId()

            session = self._open_session(
                {
                    "mode": "live",
                    "mxid": mx,
                    "cameras": [d.__dict__ for d in devices],
                    "detector": self.detector.model_name if enable_yolo else "off",
                    "detector_error": self.detector.error,
                    "vio": "stereo_feature_imu_lite",
                }
            )
            traj_f = open(session / "trajectory.csv", "w", encoding="utf-8")
            traj_f.write(
                "timestamp_s,x_m,y_m,z_m,qw,qx,qy,qz,vx_ms,vy_ms,vz_ms,n_features,quality\n"
            )
            det_f = open(session / "detections.jsonl", "w", encoding="utf-8")
            avoid_f = open(session / "avoidance.csv", "w", encoding="utf-8")
            avoid_f.write("timestamp_s,action,min_depth_m,urgency,reason\n")

            q_rgb = device.getOutputQueue("rgb", 4, False)
            q_depth = device.getOutputQueue("depth", 4, False)
            q_feat = device.getOutputQueue("features", 4, False)
            q_imu = device.getOutputQueue("imu", 8, False)

            self.vio.reset()
            with self._lock:
                self.state.running = True
                self.state.error = None
                self.state.device_mxid = mx
                self.state.mode = "live"
                self.state.session_dir = session
                self.state.frames = 0

            t0 = time.time()
            last_fps_t = t0
            fps_count = 0
            inst_fps = 0.0
            gyro_z = 0.0
            accel = (0.0, 0.0, 9.8)
            depth_mm = None
            frame_i = 0

            while not self._stop.is_set():
                in_imu = q_imu.tryGet()
                if in_imu is not None:
                    for pkt in in_imu.packets:
                        g = pkt.gyroscope
                        a = pkt.acceleroMeter
                        gyro_z = float(g.z)
                        accel = (float(a.x), float(a.y), float(a.z))

                in_depth = q_depth.tryGet()
                if in_depth is not None:
                    depth_mm = in_depth.getFrame()

                in_feat = q_feat.tryGet()
                features = []
                if in_feat is not None:
                    for f in in_feat.trackedFeatures:
                        features.append(
                            (int(f.id), float(f.position.x), float(f.position.y))
                        )

                in_rgb = q_rgb.tryGet()
                if in_rgb is None:
                    time.sleep(0.002)
                    continue

                rgb = in_rgb.getCvFrame()
                now = time.time()
                t = now - t0

                depth_for_rgb = depth_mm
                if depth_mm is not None and (
                    depth_mm.shape[0] != rgb.shape[0]
                    or depth_mm.shape[1] != rgb.shape[1]
                ):
                    depth_for_rgb = cv2.resize(
                        depth_mm,
                        (rgb.shape[1], rgb.shape[0]),
                        interpolation=cv2.INTER_NEAREST,
                    )

                vio = self.vio.update(t, features, depth_for_rgb, gyro_z, accel)

                dets: List[Detection] = []
                if (
                    enable_yolo
                    and frame_i % self.detect_every == 0
                    and self.detector.ready
                ):
                    dets = self.detector.infer(rgb)
                    dets = attach_depths(
                        dets,
                        depth_for_rgb
                        if depth_for_rgb is not None
                        else np.zeros((1, 1)),
                    )
                else:
                    with self._lock:
                        dets = list(self.state.detections)

                cmd = plan_avoidance(depth_for_rgb, dets)

                vis = rgb.copy()
                if depth_for_rgb is not None:
                    depth_c = colorize_depth(depth_for_rgb)
                    if depth_c.shape[:2] == vis.shape[:2]:
                        vis = cv2.addWeighted(vis, 0.75, depth_c, 0.25, 0)

                for d in dets:
                    color = (0, 165, 255) if (d.depth_m or 99) < 1.6 else (0, 255, 0)
                    cv2.rectangle(vis, (d.x1, d.y1), (d.x2, d.y2), color, 2)
                    label = f"{d.label} {d.conf:.2f}"
                    if d.depth_m is not None:
                        label += f" {d.depth_m:.1f}m"
                    cv2.putText(
                        vis,
                        label,
                        (d.x1, max(16, d.y1 - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        color,
                        1,
                        cv2.LINE_AA,
                    )

                action_color = {
                    "GO": (0, 200, 0),
                    "SLOW": (0, 200, 255),
                    "STOP": (0, 0, 255),
                    "TURN_LEFT": (255, 128, 0),
                    "TURN_RIGHT": (255, 128, 0),
                }.get(cmd.action, (255, 255, 255))
                cv2.putText(
                    vis,
                    f"{cmd.action}  d={cmd.min_depth_m:.2f}m  VIO q={vio.quality:.2f}",
                    (12, 28),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    action_color,
                    2,
                    cv2.LINE_AA,
                )

                ok, buf = cv2.imencode(
                    ".jpg", vis, [int(cv2.IMWRITE_JPEG_QUALITY), 80]
                )
                jpeg = buf.tobytes() if ok else None
                if jpeg:
                    (session / "preview.jpg").write_bytes(jpeg)

                traj_f.write(
                    f"{vio.t:.6f},{vio.x:.6f},{vio.y:.6f},{vio.z:.6f},"
                    f"{vio.qw:.6f},{vio.qx:.6f},{vio.qy:.6f},{vio.qz:.6f},"
                    f"{vio.vx:.6f},{vio.vy:.6f},{vio.vz:.6f},{vio.n_features},{vio.quality:.3f}\n"
                )
                avoid_f.write(
                    f"{t:.6f},{cmd.action},{cmd.min_depth_m:.4f},{cmd.urgency:.3f},"
                    f"{cmd.reason.replace(',', ';')}\n"
                )
                if enable_yolo and frame_i % self.detect_every == 0:
                    det_f.write(
                        json.dumps(
                            {
                                "t": t,
                                "dets": [
                                    {
                                        "label": d.label,
                                        "conf": d.conf,
                                        "xyxy": [d.x1, d.y1, d.x2, d.y2],
                                        "depth_m": d.depth_m,
                                    }
                                    for d in dets
                                ],
                            }
                        )
                        + "\n"
                    )

                fps_count += 1
                if now - last_fps_t >= 1.0:
                    inst_fps = fps_count / (now - last_fps_t)
                    last_fps_t = now
                    fps_count = 0

                with self._lock:
                    self.state.vio = vio
                    self.state.avoidance = cmd
                    if enable_yolo and frame_i % self.detect_every == 0:
                        self.state.detections = dets
                    self.state.preview_jpeg = jpeg
                    self.state.fps = inst_fps
                    self.state.frames = frame_i + 1

                frame_i += 1

        except Exception as exc:  # noqa: BLE001
            with self._lock:
                self.state.error = str(exc)
                self.state.running = False
        finally:
            for f in (traj_f, det_f, avoid_f):
                if f is not None:
                    f.flush()
                    f.close()
            if device is not None:
                device.close()
            with self._lock:
                self.state.running = False
