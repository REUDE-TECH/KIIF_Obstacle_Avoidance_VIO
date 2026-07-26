"""OAK-D device discovery and DepthAI pipeline (RGB + stereo depth + IMU + features)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

_DAI = None
_DAI_ERROR: Optional[str] = None


def _dai():
    global _DAI, _DAI_ERROR
    if _DAI is not None:
        return _DAI
    if _DAI_ERROR is not None:
        return None
    try:
        import depthai as dai

        _DAI = dai
        return _DAI
    except Exception as exc:  # noqa: BLE001
        _DAI_ERROR = str(exc)
        return None


@dataclass
class DeviceInfo:
    mxid: str
    name: str
    state: str
    protocol: str


def depthai_available() -> bool:
    return _dai() is not None


def depthai_import_error() -> Optional[str]:
    _dai()
    return _DAI_ERROR


def list_oak_devices() -> list[DeviceInfo]:
    dai = _dai()
    if dai is None:
        return []
    out: list[DeviceInfo] = []
    try:
        for d in dai.Device.getAllAvailableDevices():
            out.append(
                DeviceInfo(
                    mxid=str(d.getMxId()),
                    name=str(getattr(d, "name", "") or "OAK"),
                    state=str(d.state),
                    protocol=str(d.protocol),
                )
            )
    except Exception:  # noqa: BLE001
        return []
    return out


def build_pipeline(fps: float = 20.0):
    dai = _dai()
    if dai is None:
        raise RuntimeError(f"depthai not available: {_DAI_ERROR}")

    pipeline = dai.Pipeline()

    cam_rgb = pipeline.create(dai.node.ColorCamera)
    cam_rgb.setBoardSocket(dai.CameraBoardSocket.CAM_A)
    cam_rgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
    cam_rgb.setPreviewSize(640, 360)
    cam_rgb.setInterleaved(False)
    cam_rgb.setFps(fps)
    cam_rgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)

    mono_l = pipeline.create(dai.node.MonoCamera)
    mono_r = pipeline.create(dai.node.MonoCamera)
    mono_l.setBoardSocket(dai.CameraBoardSocket.CAM_B)
    mono_r.setBoardSocket(dai.CameraBoardSocket.CAM_C)
    mono_l.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
    mono_r.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
    mono_l.setFps(fps)
    mono_r.setFps(fps)

    stereo = pipeline.create(dai.node.StereoDepth)
    stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.HIGH_DENSITY)
    stereo.setLeftRightCheck(True)
    stereo.setSubpixel(True)
    stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A)
    mono_l.out.link(stereo.left)
    mono_r.out.link(stereo.right)

    tracker = pipeline.create(dai.node.FeatureTracker)
    mono_l.out.link(tracker.inputImage)
    tracker.setHardwareResources(1, 2)

    imu = pipeline.create(dai.node.IMU)
    imu.enableIMUSensor(dai.IMUSensor.ACCELEROMETER_RAW, 200)
    imu.enableIMUSensor(dai.IMUSensor.GYROSCOPE_RAW, 200)
    imu.setBatchReportThreshold(1)
    imu.setMaxBatchReports(10)

    x_rgb = pipeline.create(dai.node.XLinkOut)
    x_rgb.setStreamName("rgb")
    cam_rgb.preview.link(x_rgb.input)

    x_depth = pipeline.create(dai.node.XLinkOut)
    x_depth.setStreamName("depth")
    stereo.depth.link(x_depth.input)

    x_feat = pipeline.create(dai.node.XLinkOut)
    x_feat.setStreamName("features")
    tracker.outputFeatures.link(x_feat.input)

    x_imu = pipeline.create(dai.node.XLinkOut)
    x_imu.setStreamName("imu")
    imu.out.link(x_imu.input)

    x_left = pipeline.create(dai.node.XLinkOut)
    x_left.setStreamName("left")
    mono_l.out.link(x_left.input)

    return pipeline


def colorize_depth(depth_mm: np.ndarray, max_mm: float = 8000.0) -> np.ndarray:
    depth = np.clip(depth_mm.astype(np.float32), 0, max_mm)
    norm = np.zeros_like(depth, dtype=np.uint8)
    valid = depth > 0
    if np.any(valid):
        scaled = (depth[valid] / max_mm * 255.0).astype(np.uint8)
        norm[valid] = scaled
    color = cv2.applyColorMap(norm, cv2.COLORMAP_JET)
    color[~valid] = 0
    return color


def open_device(mxid: Optional[str] = None, fps: float = 20.0):
    dai = _dai()
    if dai is None:
        raise RuntimeError(f"depthai not available: {_DAI_ERROR}")
    devices = list_oak_devices()
    if not devices:
        raise RuntimeError(
            "No OAK-D found. Unplug from WSL/usbipd (usbipd detach), "
            "use a USB3 port, close other apps using the camera."
        )
    pipeline = build_pipeline(fps=fps)
    if mxid:
        device = dai.Device(pipeline, dai.DeviceInfo(mxid))
    else:
        device = dai.Device(pipeline)
    return device, pipeline
