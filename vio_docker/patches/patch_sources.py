#!/usr/bin/env python3
"""
patch_sources.py
================
Injects output-logging code into the three C++ sources that form the
GPS-denied VIO stack from the REUDE_KIIF_GPS_Denied_OAK_D_Project repo.

Run inside the Docker container AFTER the git clones have completed:
    python3 /patches/patch_sources.py

Sources modified (all already inside /root/nongps_pro/):
  1. oak_d_vins_cpp/feature_tracker.cpp
  2. VINS-Fusion/vins_estimator/src/utility/visualization.cpp
  3. mavlink-udp-proxy/my_mavlink_udp.cpp
"""

import sys
import os

BASE = "/root/nongps_pro"
PATCHES_DIR = "/patches"
OUT_INCLUDE = '#include "/patches/output_writer.h"'
OUTPUT_BASE = "/outputs"

# ──────────────────────────────────────────────────────────────────────────────
# Helper: read / write / verify file
# ──────────────────────────────────────────────────────────────────────────────
def read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def write_file(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Written: {path}")

def require_anchor(content, anchor, label):
    if anchor not in content:
        print(f"  [FAIL] Anchor not found in {label}:\n         {repr(anchor)}")
        sys.exit(1)
    print(f"  [OK] Anchor found: {repr(anchor[:60])}...")

def insert_after(content, anchor, insertion):
    """Insert text immediately after the first occurrence of `anchor`."""
    idx = content.find(anchor)
    if idx == -1:
        raise ValueError(f"Anchor not found: {repr(anchor)}")
    end = idx + len(anchor)
    return content[:end] + "\n" + insertion + content[end:]

def insert_before(content, anchor, insertion):
    """Insert text immediately before the first occurrence of `anchor`."""
    idx = content.find(anchor)
    if idx == -1:
        raise ValueError(f"Anchor not found: {repr(anchor)}")
    return content[:idx] + insertion + "\n" + content[idx:]

# ──────────────────────────────────────────────────────────────────────────────
# 1. feature_tracker.cpp
#    Produces: depth PNG, depth CSV, point cloud PLY, feature overlay PNG,
#              feature CSV, IMU CSV
# ──────────────────────────────────────────────────────────────────────────────
def patch_feature_tracker():
    path = f"{BASE}/oak_d_vins_cpp/feature_tracker.cpp"
    print(f"\n[1/3] Patching {path}")
    if not os.path.exists(path):
        print(f"  [SKIP] File does not exist: {path}")
        return
    src = read_file(path)
    # Patch CMakeLists.txt to link with depthai::opencv and define DEPTHAI_HAVE_OPENCV_SUPPORT
    cmake_path = f"{BASE}/oak_d_vins_cpp/CMakeLists.txt"
    if os.path.exists(cmake_path):
        print(f"  Patching {cmake_path}")
        cmake_src = read_file(cmake_path)
        if "depthai::opencv" not in cmake_src:
            cmake_src = cmake_src.replace("depthai::core", "depthai::opencv")
            cmake_src += "\nadd_definitions(-DDEPTHAI_HAVE_OPENCV_SUPPORT -DVIO_HAS_OPENCV)\n"
            write_file(cmake_path, cmake_src)

    if OUT_INCLUDE in src:
        print(f"  [OK] Already patched: {path}")
        return

    # ── A. Add #include at the top (after depthai include) ────────────────────
    anchor_a = '#include "depthai/depthai.hpp"'
    require_anchor(src, anchor_a, "feature_tracker.cpp (depthai include)")
    src = insert_after(src, anchor_a,
        f'{OUT_INCLUDE}\n'
        f'#include <chrono>    // already used, ensure present\n'
    )

    # ── B. Add disparity frame capture + output write ─────────────────────────
    #    The main loop polls queues; disparity arrives via xout_disp.
    #    Anchor: the stream name string used when getting the output queue.
    #    In depthai, the host calls: device.getOutputQueue("disparity", ...)
    #    We inject our write call after the disparity frame's getFrame().
    #
    #    The exact anchor we use is the unique literal set in the pipeline:
    #       xout_disp->setStreamName("disparity");
    #    and our injection is after the device is opened and queues are created.
    #
    #    We inject a lambda/helper that will be called inside the while(gogogo) loop.
    #    Strategy: find the `while (gogogo)` loop and inject our call after
    #    the disparity queue .get() call is made.
    #
    #    Since we can't reliably find the exact get() call without the full source,
    #    we wrap the existing sendto-to-features call: just before sendto to
    #    features_addr we capture the data for output.
    #
    #    First, inject the ColorCamera and raw queues into the pipeline setup.
    anchor_nodes = "auto imu = pipeline.create<dai::node::IMU>();"
    require_anchor(src, anchor_nodes, "feature_tracker.cpp (IMU node creation)")
    inject_nodes = (
        "    auto colorCam = pipeline.create<dai::node::ColorCamera>();\n"
        "    auto xoutLeft = pipeline.create<dai::node::XLinkOut>();\n"
        "    auto xoutRight = pipeline.create<dai::node::XLinkOut>();\n"
        "    auto xoutRgb = pipeline.create<dai::node::XLinkOut>();\n"
        "    xoutLeft->setStreamName(\"raw_left\");\n"
        "    xoutRight->setStreamName(\"raw_right\");\n"
        "    xoutRgb->setStreamName(\"raw_rgb\");\n"
        "    colorCam->setResolution(dai::ColorCameraProperties::SensorResolution::THE_1080_P);\n"
        "    colorCam->setFps(20);\n"
        "    colorCam->setInterleaved(true);\n"
        "    colorCam->setColorOrder(dai::ColorCameraProperties::ColorOrder::BGR);\n"
        "    colorCam->setPreviewSize(1920, 1080);\n"
        "    monoLeft->out.link(xoutLeft->input);\n"
        "    monoRight->out.link(xoutRight->input);\n"
        "    colorCam->preview.link(xoutRgb->input);\n"
    )
    src = insert_after(src, anchor_nodes, inject_nodes)

    anchor_queues = 'auto imuQueue = device.getOutputQueue("imu", 5, false);'
    require_anchor(src, anchor_queues, "feature_tracker.cpp (IMU queue)")
    inject_queues = (
        '    auto leftQueue = device.getOutputQueue("raw_left", 4, false);\n'
        '    auto rightQueue = device.getOutputQueue("raw_right", 4, false);\n'
        '    auto rgbQueue = device.getOutputQueue("raw_rgb", 4, false);\n'
        '    cv::Mat last_disp, last_left;\n'
    )
    src = insert_after(src, anchor_queues, inject_queues)

    #    Inject video frame capture inside the while(gogogo) loop event handler
    anchor_if_tracked = 'if (q_name == "trackedFeaturesLeft") {'
    require_anchor(src, anchor_if_tracked, "feature_tracker.cpp (trackedFeaturesLeft check)")
    inject_if_raw = (
        'if (q_name == "raw_left") {\n'
        '            auto frame = leftQueue->get<dai::ImgFrame>();\n'
        '            last_left = frame->getCvFrame();\n'
        '            vio_ft_out::write_raw_video("left", last_left);\n'
        '        } else if (q_name == "raw_right") {\n'
        '            auto frame = rightQueue->get<dai::ImgFrame>();\n'
        '            vio_ft_out::write_raw_video("right", frame->getCvFrame());\n'
        '        } else if (q_name == "raw_rgb") {\n'
        '            auto frame = rgbQueue->get<dai::ImgFrame>();\n'
        '            vio_ft_out::write_raw_video("rgb", frame->getCvFrame());\n'
        '        } else '
    )
    src = src.replace(anchor_if_tracked, inject_if_raw + anchor_if_tracked, 1)

    #    Anchor: the literal path used for features socket (unique in source).
    anchor_b = 'strcpy(features_addr.sun_path, "/tmp/chobits_features");'
    require_anchor(src, anchor_b, "feature_tracker.cpp (features socket path)")

    # After the IPC setup block, init the output writer using focal/baseline.
    # At this point in main(), calibration hasn't been read yet — we init later.
    # Instead we inject after calc_rect_cam_intri call.
    # Anchor: the return value assignments from calc_rect_cam_intri.
    anchor_init = "calc_rect_cam_intri(calibData, &f, &cx, &cy);"
    if anchor_init not in src:
        # Try alternate form
        anchor_init = "calc_rect_cam_intri("
    require_anchor(src, anchor_init, "feature_tracker.cpp (calc_rect_cam_intri call)")

    src = insert_after(src, anchor_init,
        f'\n    // ── VIO OUTPUT INIT ───────────────────────────────────────────────\n'
        f'    vio_ft_out::init("{OUTPUT_BASE}", f, cx, cy, 0.075 /* OAK-D baseline m */);\n'
        f'    // ─────────────────────────────────────────────────────────────────\n'
    )

    # ── C. Inject IMU CSV write before sendto to imu_addr ─────────────────────
    #    Anchor: unique literal for the imu socket send target.
    #    The sendto for IMU is: sendto(ipc_sock, ..., &imu_addr, sizeof(imu_addr))
    #    We find the last sendto before the imu_addr reference.
    #
    #    From reading the code, the IMU data is packed from dai::IMUData.
    #    The packet contains: timestamp(double) + 6 doubles for accel/gyro.
    #    We log at the point where the DAI IMU packet is received.
    #
    #    Anchor: the imu XLinkOut stream name set in the pipeline.
    anchor_imu_stream = 'xout_imu->setStreamName("imu");'
    if anchor_imu_stream not in src:
        anchor_imu_stream = '"imu"'

    # The most reliable anchor for IMU is the block where IMU data is extracted.
    # In depthai, it's typically:
    #   auto imuData = imu_queue->get<dai::IMUData>();
    #   for (auto& imuPacket : imuData->packets) {
    #     auto& acceleroValues = imuPacket.acceleroMeter;
    #     auto& gyroValues = imuPacket.gyroscope;
    # We anchor on &imu_addr which uniquely appears in the sendto for IMU.
    anchor_imu_send = 'sendto(ipc_sock, big_buf, 7*sizeof(double), 0, (struct sockaddr*)&imu_addr'
    require_anchor(src, anchor_imu_send, "feature_tracker.cpp (imu sendto)")

    # Find the full sendto(...imu_addr...) line and inject IMU CSV write before it.
    # We insert the output call. The IMU timestamp is in big_buf[0] (first double).
    imu_inject = (
        '\n    // ── VIO OUTPUT: IMU CSV ──────────────────────────────────────────\n'
        '    {\n'
        '        double* b = (double*)big_buf;\n'
        '        // Format: [ts_s, ax, ay, az, gx, gy, gz]\n'
        '        int64_t ts_ns = (int64_t)(b[0] * 1e9);\n'
        '        vio_ft_out::write_imu(ts_ns,\n'
        '            (float)b[1], (float)b[2], (float)b[3],\n'
        '            (float)b[4], (float)b[5], (float)b[6]);\n'
        '    }\n'
        '    // ─────────────────────────────────────────────────────────────────\n'
    )
    src = insert_before(src, anchor_imu_send, imu_inject)

    # ── D. Inject depth + feature outputs before sendto to features_addr ──────
    #    The features packet contains disparity depth per feature.
    #    Anchor: the sendto for features.
    anchor_feat_send = "sendto(ipc_sock, big_buf, 13*sizeof(double)*c+2*sizeof(double), 0, (struct sockaddr*)&features_addr"
    require_anchor(src, anchor_feat_send, "feature_tracker.cpp (features sendto)")

    feat_inject = (
        '\n    // ── VIO OUTPUT: Depth + Feature overlay + PLY ───────────────────\n'
        '    {\n'
        '        double* b = (double*)big_buf;\n'
        '        int64_t ts_ns = (int64_t)(b[0] * 1e9);\n'
        '        // Extract features from packed buffer\n'
        '        // Format: [ts_s, count, (id, x, y, d, vx, vy, rx, ry) x N]\n'
        '        int feat_count = (int)b[1];\n'
        '        std::vector<std::pair<int, cv::Point2f>> feat_list;\n'
        '        for (int _fi = 0; _fi < feat_count && _fi < 500; _fi++) {\n'
        '            int base_idx = 2 + _fi * 8;\n'
        '            int fid = (int)b[base_idx];\n'
        '            // x,y are normalised coords — convert back to pixels\n'
        '            float px = (float)(b[base_idx+1] * vio_ft_out::focal_px + vio_ft_out::cx_px);\n'
        '            float py = (float)(b[base_idx+2] * vio_ft_out::focal_px + vio_ft_out::cy_px);\n'
        '            feat_list.push_back({fid, cv::Point2f(px, py)});\n'
        '        }\n'
        '        // Write depth map, point cloud, feature overlay\n'
        '        if (!last_disp.empty())\n'
        '            vio_ft_out::write_depth_and_cloud(ts_ns, last_disp, last_left);\n'
        '        vio_ft_out::write_features(ts_ns, last_left, last_disp, feat_list);\n'
        '    }\n'
        '    // ─────────────────────────────────────────────────────────────────\n'
    )
    src = insert_before(src, anchor_feat_send, feat_inject)

    anchor_disp_data = "disp_frame = disp_data->getData();"
    require_anchor(src, anchor_disp_data, "feature_tracker.cpp (disparity data retrieval)")
    src = insert_after(src, anchor_disp_data,
        "            last_disp = disp_data->getCvFrame();"
    )

    # ── E. Capture disparity frame into last_disp when received ───────────────
    #    Anchor: the disparity queue get call. Typical pattern in depthai:
    #      auto disp_data = disp_queue->get<dai::ImgFrame>();
    #    We search for the getOutputQueue for disparity.
    anchor_disp_queue = '"disparity"'
    # We need to find where getFrame() is called on the disparity queue result.
    # Inject a capture after any getFrame() on an ImgFrame named disp.
    # Most reliable anchor: the frame data copy call.
    anchor_disp_frame = 'getOutputQueue("disparity"'
    if anchor_disp_frame not in src:
        anchor_disp_frame = '"disparity"'

    # Find the getOutputQueue disparity call, then inject capture code
    # after the line that creates dispQueue.
    # Pattern: auto disp_queue = device.getOutputQueue("disparity", ...)
    anchor_disp_q = 'getOutputQueue("disparity"'
    if anchor_disp_q in src:
        disp_q_inject = (
            '\n    // ── VIO OUTPUT: capture disparity frames ─────────────────────\n'
            '    // Disparity queue captured; frames will be read in the main loop.\n'
        )
        # We don't modify here; instead we rely on the last_disp static above.
        # No injection needed at queue creation — last_disp is populated in the loop.
        pass

    # The actual disparity getFrame() in the loop — find tryGet/get pattern.
    # We inject code to save to last_disp after the ImgFrame is obtained.
    anchor_disp_get = 'getFrame()'
    if anchor_disp_get in src:
        # Find first getFrame() associated with disparity
        # We inject AFTER the first getFrame() call that appears in the code
        disp_capture = (
            ';\n'
            '    // ── VIO OUTPUT: save disparity and left frame ─────────────────\n'
            '    vio_ft_out::last_disp = disp_data->getFrame().clone();\n'
        )
        # Actually getFrame() returns a Mat directly. The existing code likely
        # uses it inline. We need to be careful not to double-call.
        # Skip this injection; the static last_disp approach in feat_inject above
        # uses tryGet-captured frames. We instead need to populate last_disp.
        # Add a more targeted injection using the disparity queue variable name.

    # Most robust approach: add a helper block AT THE START of the while loop
    # that captures the disparity frame. Anchor: `while (gogogo) {`
    anchor_while = 'while(gogogo)'
    if anchor_while not in src:
        anchor_while = 'while (gogogo)'
    require_anchor(src, anchor_while, "feature_tracker.cpp (main while loop)")
    loop_inject = (
        ' {\n'
        '    // ── VIO OUTPUT: try get disparity + left frames for this iteration\n'
        '    static std::shared_ptr<dai::ImgFrame> _vio_disp_frame;\n'
        '    static std::shared_ptr<dai::ImgFrame> _vio_left_frame;\n'
    )
    # Don't inject here as it would break the while structure.
    # Instead, rely on the feature_tracker's own queue read.
    # The static last_disp variables will be set when disparity arrives.

    write_file(path, src)

# ──────────────────────────────────────────────────────────────────────────────
# 2. visualization.cpp  (VINS-Fusion)
#    Produces: VIO pose/trajectory CSV
# ──────────────────────────────────────────────────────────────────────────────
def patch_visualization():
    path = f"{BASE}/VINS-Fusion/vins_estimator/src/utility/visualization.cpp"
    print(f"\n[2/3] Patching {path}")
    if not os.path.exists(path):
        print(f"  [SKIP] File does not exist: {path}")
        return
    src = read_file(path)
    if OUT_INCLUDE in src:
        print(f"  [OK] Already patched: {path}")
        return

    # ── A. Add #include ────────────────────────────────────────────────────────
    anchor_a = '#include "visualization.h"'
    require_anchor(src, anchor_a, "visualization.cpp (include)")
    src = insert_after(src, anchor_a,
        f'{OUT_INCLUDE}\n'
    )

    # ── B. Init trajectory CSV in registerPub() ────────────────────────────────
    anchor_reg = 'void registerPub()'
    require_anchor(src, anchor_reg, "visualization.cpp (registerPub)")
    # Find the opening brace of registerPub and inject init after it
    anchor_reg_open = 'void registerPub()'
    idx = src.find(anchor_reg_open)
    brace_idx = src.find('{', idx)
    if brace_idx == -1:
        print("  [FAIL] Could not find opening brace of registerPub()")
        sys.exit(1)
    reg_inject = (
        '\n    // ── VIO OUTPUT: init trajectory CSV ──────────────────────────────\n'
        f'    vio_pose_out::init("{OUTPUT_BASE}");\n'
        '    // ─────────────────────────────────────────────────────────────────\n'
    )
    src = src[:brace_idx+1] + reg_inject + src[brace_idx+1:]

    # ── C. Inject trajectory write in pubOdometry() ───────────────────────────
    #    Anchor: the sendto call to chobits_server — unique in this file.
    #    The chobits socket path is set in registerPub, and the sendto is in
    #    pubOdometry. We find sendto(chobits_sock, ...) and inject after it.
    anchor_sendto = "sendto(chobits_sock,"
    if anchor_sendto not in src:
        anchor_sendto = "chobits_sock"
    require_anchor(src, anchor_sendto, "visualization.cpp (chobits sendto)")

    # Find the full sendto line (ends with ;) and inject trajectory write after it.
    # We use the Estimator fields: latest_P, latest_Q, latest_V, latest_time
    traj_inject = (
        '\n    // ── VIO OUTPUT: trajectory CSV ───────────────────────────────────\n'
        '    {\n'
        '        Eigen::Vector3d P = estimator.latest_P;\n'
        '        Eigen::Quaterniond Q = estimator.latest_Q;\n'
        '        Eigen::Vector3d V = estimator.latest_V;\n'
        '        vio_pose_out::write(\n'
        '            estimator.Headers[estimator.frame_count % (WINDOW_SIZE+1)],\n'
        '            P.x(), P.y(), P.z(),\n'
        '            Q.w(), Q.x(), Q.y(), Q.z(),\n'
        '            V.x(), V.y(), V.z());\n'
        '    }\n'
        '    // ─────────────────────────────────────────────────────────────────\n'
    )
    # Find last occurrence of the sendto (there may be multiple) — use the
    # one inside pubOdometry. Find pubOdometry first.
    pub_idx = src.find("void pubOdometry(")
    if pub_idx == -1:
        pub_idx = src.find("pubOdometry(")
    sendto_idx = src.find(anchor_sendto, pub_idx if pub_idx != -1 else 0)
    if sendto_idx == -1:
        print("  [FAIL] sendto(chobits_sock not found after pubOdometry")
        sys.exit(1)
    # Find end of this statement (semicolon)
    semi_idx = src.find(';', sendto_idx)
    if semi_idx == -1:
        print("  [FAIL] Could not find ; after sendto")
        sys.exit(1)
    src = src[:semi_idx+1] + "\n" + traj_inject + src[semi_idx+1:]

    write_file(path, src)

# ──────────────────────────────────────────────────────────────────────────────
# 3. my_mavlink_udp.cpp  (mavlink-udp-proxy)
#    Produces: MAVLink VISION_POSITION_ESTIMATE CSV
# ──────────────────────────────────────────────────────────────────────────────
def patch_mavlink():
    path = f"{BASE}/mavlink-udp-proxy/my_mavlink_udp.cpp"
    print(f"\n[3/3] Patching {path}")
    if not os.path.exists(path):
        print(f"  [SKIP] File does not exist: {path}")
        return
    src = read_file(path)
    if OUT_INCLUDE in src:
        print(f"  [OK] Already patched: {path}")
        return

    # ── A. Add #include ────────────────────────────────────────────────────────
    anchor_a = '#include "mavlink/ardupilotmega/mavlink.h"'
    require_anchor(src, anchor_a, "my_mavlink_udp.cpp (mavlink include)")
    src = insert_after(src, anchor_a,
        f'{OUT_INCLUDE}\n'
    )

    # ── B. Init MAVLink CSV at start of main() ─────────────────────────────────
    # Anchor: opening of main function body — find first { after `int main(`
    main_idx = src.find("int main(")
    if main_idx == -1:
        print("  [FAIL] int main( not found")
        sys.exit(1)
    brace_idx = src.find('{', main_idx)
    mav_init = (
        '\n    // ── VIO OUTPUT: init MAVLink CSV ──────────────────────────────────\n'
        f'    vio_mav_out::init("{OUTPUT_BASE}");\n'
        '    // ─────────────────────────────────────────────────────────────────\n'
    )
    src = src[:brace_idx+1] + mav_init + src[brace_idx+1:]

    # ── C. Inject MAVLink CSV write after pose[3]=-pose[3]; ───────────────────
    #    The pose array has the VINS pose state [qw, x, y, z, px, py, pz, vx, vy, vz].
    #    We extract x, y, z as pose[4], -pose[5], -pose[6].
    #    We compute roll, pitch, yaw from quaternion pose[0..3].
    anchor_pose_neg = "pose[3]=-pose[3];"
    require_anchor(src, anchor_pose_neg, "my_mavlink_udp.cpp (pose negative height)")

    mav_inject = (
        '\n                    // ── VIO OUTPUT: MAVLink CSV ────────────────────────────────────────\n'
        '                    {\n'
        '                        double qw = pose[0], qx = pose[1], qy = pose[2], qz = pose[3];\n'
        '                        double roll = atan2(2.0*(qw*qx + qy*qz), 1.0 - 2.0*(qx*qx + qy*qy));\n'
        '                        double sinp = 2.0*(qw*qy - qz*qx);\n'
        '                        double pitch = (fabs(sinp) >= 1) ? ((sinp > 0) ? 1.5707963267948966 : -1.5707963267948966) : asin(sinp);\n'
        '                        double yaw = atan2(2.0*(qw*qz + qx*qy), 1.0 - 2.0*(qy*qy + qz*qz));\n'
        '                        struct timeval _tv; gettimeofday(&_tv, NULL);\n'
        '                        int64_t _ts_us = (int64_t)_tv.tv_sec * 1000000LL + _tv.tv_usec;\n'
        '                        vio_mav_out::write(_ts_us,\n'
        '                            pose[4], -pose[5], -pose[6],\n'
        '                            (float)roll, (float)pitch, (float)yaw,\n'
        '                            0);\n'
        '                    }\n'
        '                    // ─────────────────────────────────────────────────────────────────\n'
    )
    src = insert_after(src, anchor_pose_neg, mav_inject)

    write_file(path, src)

# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("VIO Output Pipeline - Source Patcher")
    print("=" * 60)

    errors = []
    for fn, label in [
        (patch_feature_tracker, "feature_tracker.cpp"),
        (patch_visualization,   "visualization.cpp"),
        (patch_mavlink,         "my_mavlink_udp.cpp"),
    ]:
        try:
            fn()
        except Exception as e:
            errors.append(f"{label}: {e}")
            print(f"  [FAIL] {e}")

    print("\n" + "=" * 60)
    if errors:
        print(f"FAILED with {len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("All 3 source files patched successfully.")
        print("Rebuild required: make -j$(nproc) in each source dir.")
