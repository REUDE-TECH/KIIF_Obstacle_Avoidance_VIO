"""Unified dashboard: Detect camera → VIO → Object detection → Obstacle avoidance."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from pipeline.camera_device import depthai_available, depthai_import_error, list_oak_devices
from pipeline.runner import PipelineRunner, cloud_demo_default

ROOT = Path(__file__).resolve().parent
OUTPUTS = ROOT / "outputs"
OUTPUTS.mkdir(parents=True, exist_ok=True)

st.set_page_config(
    page_title="OAK-D Obstacle Avoidance",
    page_icon="🛡️",
    layout="wide",
)

st.title("OAK-D Obstacle Avoidance")
st.caption(
    "Sequence: **Detect camera → VIO → detection → avoidance**. "
    "Live OAK-D on a local PC; **Demo mode** on Render (no USB camera in the cloud)."
)

on_render = bool(os.environ.get("RENDER")) or cloud_demo_default()
if on_render:
    st.info(
        "**Running on Render (or DEMO_MODE)** — physical OAK-D is not available in the cloud. "
        "Use **Start demo pipeline** to exercise VIO + avoidance with a synthetic feed."
    )


def _runner() -> PipelineRunner:
    if "runner" not in st.session_state:
        st.session_state.runner = PipelineRunner(OUTPUTS)
    return st.session_state.runner


runner = _runner()
state = runner.snapshot()

with st.sidebar:
    st.header("Controls")
    devices = list_oak_devices()
    if devices:
        st.success(f"Cameras found: {len(devices)}")
        for d in devices:
            st.write(f"- `{d.mxid}` · {d.state}")
        mx_options = ["(auto)"] + [d.mxid for d in devices]
    else:
        st.warning("No OAK-D detected (expected on Render)")
        if not depthai_available():
            st.caption(f"depthai: {depthai_import_error() or 'not installed (cloud build)'}")
        else:
            st.caption("Detach from WSL locally: `usbipd detach --busid <ID>`")
        mx_options = ["(auto)"]

    mx_choice = st.selectbox("Device", mx_options)
    mxid = None if mx_choice == "(auto)" else mx_choice
    fps = st.selectbox("Camera FPS", [10, 15, 20], index=1)
    force_demo = st.checkbox(
        "Force demo mode (no hardware)",
        value=on_render or not devices,
    )

    c1, c2 = st.columns(2)
    with c1:
        label = "Start demo" if force_demo else "Start pipeline"
        if st.button(label, type="primary", use_container_width=True, disabled=state.running):
            if (not force_demo) and (not runner.detector.ready):
                with st.spinner("Loading YOLOv8n (first run)..."):
                    runner.detector.load()
            runner.start(mxid=mxid, fps=float(fps), force_demo=force_demo)
            st.rerun()
    with c2:
        if st.button("Stop", use_container_width=True, disabled=not state.running):
            runner.stop()
            st.rerun()

    if st.button("Refresh", use_container_width=True):
        st.rerun()

    st.divider()
    st.caption(f"Mode: `{state.mode}` · Outputs: `{OUTPUTS}`")

if state.running:
    time.sleep(0.7)
    st.rerun()

tab_live, tab_avoid, tab_det, tab_vio, tab_sess = st.tabs(
    ["Live Pipeline", "Avoidance", "Detections", "VIO / Pose", "Sessions"]
)

with tab_live:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Pipeline", "RUNNING" if state.running else "STOPPED")
    m2.metric("FPS", f"{state.fps:.1f}" if state.running else "—")
    m3.metric("Frames", state.frames if state.running else "—")
    m4.metric("Device", state.device_mxid or "—")

    if state.error:
        st.error(state.error)

    if state.preview_jpeg:
        st.image(
            state.preview_jpeg,
            caption="RGB + depth tint + detections + avoidance",
            width=960,
        )
    else:
        st.info("Start the pipeline (or demo) to see live annotated video.")

with tab_avoid:
    a = state.avoidance
    st.subheader(f"Command: {a.action}")
    st.write(f"Min depth: **{a.min_depth_m:.2f} m** · Urgency: **{a.urgency:.2f}**")
    st.write(f"Reason: {a.reason}")
    color = {
        "GO": "green",
        "SLOW": "orange",
        "STOP": "red",
        "TURN_LEFT": "blue",
        "TURN_RIGHT": "blue",
    }.get(a.action, "gray")
    st.markdown(
        f"<div style='padding:1rem;border-radius:8px;background:{color};"
        f"color:white;font-size:1.4rem'>{a.action}</div>",
        unsafe_allow_html=True,
    )

with tab_det:
    if not state.detections:
        st.info("No detections yet.")
    else:
        rows = [
            {
                "label": d.label,
                "conf": round(d.conf, 3),
                "depth_m": None if d.depth_m is None else round(d.depth_m, 2),
                "box": f"{d.x1},{d.y1},{d.x2},{d.y2}",
            }
            for d in state.detections
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True)

with tab_vio:
    v = state.vio
    c1, c2, c3 = st.columns(3)
    c1.metric("X (m)", f"{v.x:.2f}")
    c2.metric("Y (m)", f"{v.y:.2f}")
    c3.metric("Vx (m/s)", f"{v.vx:.2f}")
    if state.session_dir and (state.session_dir / "trajectory.csv").is_file():
        try:
            df = pd.read_csv(state.session_dir / "trajectory.csv")
            if len(df) > 2:
                fig = go.Figure(
                    go.Scatter(x=df["x_m"], y=df["y_m"], mode="lines", name="path")
                )
                fig.update_layout(
                    title="VIO trajectory (XY)",
                    xaxis_title="X (m)",
                    yaxis_title="Y (m)",
                    yaxis_scaleanchor="x",
                    height=420,
                )
                st.plotly_chart(fig, use_container_width=True)
        except Exception as exc:  # noqa: BLE001
            st.warning(f"Trajectory plot: {exc}")

with tab_sess:
    sessions = sorted(
        [p for p in OUTPUTS.iterdir() if p.is_dir() and p.name.startswith("session_")],
        key=lambda p: p.name,
        reverse=True,
    )
    if not sessions:
        st.info("No sessions yet.")
    else:
        pick = st.selectbox("Session", [p.name for p in sessions])
        path = OUTPUTS / pick
        st.code(str(path), language=None)
        prev = path / "preview.jpg"
        if prev.is_file():
            st.image(str(prev), width=800)
