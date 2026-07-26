/*
 * output_writer.h
 *
 * GPS-Denied Navigation Output Recorder
 * Injected into: feature_tracker.cpp, visualization.cpp, my_mavlink_udp.cpp
 *
 * Produces on /outputs/session_YYYYMMDD_HHMMSS/ (host-mounted volume):
 *   raw/          - raw camera videos (left, right, rgb, depth)
 *   depth/        - depth map PNG (colorized) + CSV (mm per pixel)
 *   pointclouds/  - PLY point cloud per frame
 *   features/     - feature overlay PNG + CSV (id, px, py, depth_mm)
 *   imu/          - IMU CSV (timestamp, accel xyz, gyro xyz)
 *   pose/         - VIO trajectory CSV (timestamp, xyz, quaternion, velocity)
 *   mavlink/      - MAVLink VISION_POSITION_ESTIMATE CSV
 *   session_info.json - session metadata
 */

#pragma once

#include <cstdio>
#include <cstdint>
#include <cstring>
#include <ctime>
#include <cmath>
#include <string>
#include <vector>
#include <fstream>
#include <sstream>
#include <iomanip>
#include <sys/stat.h>
#include <sys/types.h>
#ifdef VIO_HAS_OPENCV
#include <opencv2/opencv.hpp>
#endif

// ─────────────────────────────────────────────────────────────────────────────
// Directory helpers
// ─────────────────────────────────────────────────────────────────────────────
static inline void vio_mkdir(const std::string& path) {
    mkdir(path.c_str(), 0777);
}

static inline std::string vio_get_or_create_session(const std::string& base) {
    std::string session_file = base + "/current_session.txt";
    
    // Try to read existing session
    std::ifstream infile(session_file);
    if (infile.is_open()) {
        std::string existing_session;
        if (std::getline(infile, existing_session) && !existing_session.empty()) {
            // Check if the directory actually exists
            struct stat info;
            if (stat(existing_session.c_str(), &info) == 0 && (info.st_mode & S_IFDIR)) {
                return existing_session;
            }
        }
        infile.close();
    }

    // Create a new session
    time_t now = time(nullptr);
    char buf[64];
    strftime(buf, sizeof(buf), "session_%Y%m%d_%H%M%S", localtime(&now));
    std::string session = base + "/" + std::string(buf);
    
    vio_mkdir(base);
    vio_mkdir(session);
    vio_mkdir(session + "/depth");
    vio_mkdir(session + "/pointclouds");
    vio_mkdir(session + "/features");
    vio_mkdir(session + "/imu");
    vio_mkdir(session + "/pose");
    vio_mkdir(session + "/mavlink");

    // Save it to current_session.txt
    std::ofstream outfile(session_file, std::ios::out | std::ios::trunc);
    if (outfile.is_open()) {
        outfile << session << "\n";
        outfile.close();
    }

    return session;
}

static inline std::string vio_frame_id(int n) {
    char buf[16];
    snprintf(buf, sizeof(buf), "%06d", n);
    return std::string(buf);
}

#ifdef VIO_HAS_OPENCV
// ─────────────────────────────────────────────────────────────────────────────
// Feature Tracker outputs  (called from feature_tracker.cpp)
// ─────────────────────────────────────────────────────────────────────────────

// Global state for feature_tracker outputs
namespace vio_ft_out {
    static std::string session_dir;
    static std::ofstream imu_csv;
    static std::ofstream feat_csv;
    static int frame_num = 0;
    static double focal_px  = 0.0;   // rectified focal length in pixels
    static double cx_px     = 0.0;   // principal point x
    static double cy_px     = 0.0;   // principal point y
    static double baseline_m = 0.075; // OAK-D stereo baseline (m) — default 7.5 cm

    static cv::VideoWriter vw_left;
    static cv::VideoWriter vw_right;
    static cv::VideoWriter vw_rgb;
    static cv::VideoWriter vw_depth;

    static void init(const std::string& out_base,
                     double f, double cx, double cy, double b) {
        focal_px   = f;
        cx_px      = cx;
        cy_px      = cy;
        baseline_m = b;
        session_dir = vio_get_or_create_session(out_base);

        imu_csv.open(session_dir + "/imu/imu_log.csv", std::ios::out);
        imu_csv << "timestamp_ns,acc_x_ms2,acc_y_ms2,acc_z_ms2,"
                   "gyro_x_rads,gyro_y_rads,gyro_z_rads\n";

        feat_csv.open(session_dir + "/features/features_log.csv", std::ios::out);
        feat_csv << "timestamp_ns,feature_id,pixel_x,pixel_y,depth_mm\n";

        // Write session metadata JSON
        std::ofstream meta(session_dir + "/session_info.json");
        meta << "{\n"
             << "  \"focal_px\": "   << std::fixed << std::setprecision(4) << f    << ",\n"
             << "  \"cx_px\": "      << cx   << ",\n"
             << "  \"cy_px\": "      << cy   << ",\n"
             << "  \"baseline_m\": " << b    << ",\n"
             << "  \"cam_width\": 640,\n"
             << "  \"cam_height\": 400,\n"
             << "  \"source\": \"oak_d_vins_cpp apm_wiki\"\n"
             << "}\n";

        int fcc = cv::VideoWriter::fourcc('m','p','4','v');
        vw_left.open(session_dir + "/raw_left.mp4", fcc, 20.0, cv::Size(640, 400), false);
        vw_right.open(session_dir + "/raw_right.mp4", fcc, 20.0, cv::Size(640, 400), false);
        vw_rgb.open(session_dir + "/raw_rgb.mp4", fcc, 20.0, cv::Size(1920, 1080), true);
        vw_depth.open(session_dir + "/depth.mp4", fcc, 20.0, cv::Size(640, 400), true);
    }

    // Write one IMU sample row
    static void write_imu(int64_t ts_ns,
                          float ax, float ay, float az,
                          float gx, float gy, float gz) {
        if (!imu_csv.is_open()) return;
        imu_csv << ts_ns << ","
                << std::fixed << std::setprecision(6)
                << ax << "," << ay << "," << az << ","
                << gx << "," << gy << "," << gz << "\n";
        imu_csv.flush();
    }

    // Write depth map PNG + CSV + point cloud PLY for one disparity frame
    // disp: CV_16UC1 (raw disparity in 1/16 sub-pixel units from StereoDepth)
    // left_frame: CV_8UC1 grayscale image (for feature overlay)
    static void write_depth_and_cloud(int64_t ts_ns,
                                      const cv::Mat& disp,
                                      const cv::Mat& left_frame) {
        if (session_dir.empty() || disp.empty()) return;
        std::string fid = vio_frame_id(frame_num);

        // ── 1. Depth map PNG (colorized TURBO/JET) ──────────────────────────
        // StereoDepth outputs disparity in 1/16 pixel units (uint16).
        // Normalize to 0-255 for display.
        cv::Mat disp_norm;
        double max_disp = 96.0 * 16.0;  // max disparity * sub-pixel factor
        disp.convertTo(disp_norm, CV_8U, 255.0 / max_disp);
        cv::Mat disp_color;
        cv::applyColorMap(disp_norm, disp_color, cv::COLORMAP_JET);
        cv::imwrite(session_dir + "/depth/frame_" + fid + "_depth.png", disp_color);
        
        if (vw_depth.isOpened()) {
            vw_depth.write(disp_color);
        }

        // ── 2. Depth CSV (depth in mm per pixel) ────────────────────────────
        // depth_mm = focal_px * baseline_m * 1000 / (disparity / 16)
        std::ofstream dcsv(session_dir + "/depth/frame_" + fid + "_depth.csv");
        std::vector<cv::Point3f> pts;  // reuse for PLY
        pts.reserve(disp.rows * disp.cols / 4);

        for (int r = 0; r < disp.rows; r++) {
            for (int c = 0; c < disp.cols; c++) {
                uint16_t raw_d = disp.at<uint16_t>(r, c);
                float depth_mm = 0.0f;
                if (raw_d > 0 && focal_px > 0.0) {
                    double d_px = raw_d / 16.0;  // real disparity in pixels
                    depth_mm = (float)(focal_px * baseline_m * 1000.0 / d_px);
                    // Build 3D point (in metres)
                    float Z = (float)(focal_px * baseline_m / d_px);
                    float X = (float)((c - cx_px) * Z / focal_px);
                    float Y = (float)((r - cy_px) * Z / focal_px);
                    pts.push_back({X, Y, Z});
                }
                dcsv << std::fixed << std::setprecision(1) << depth_mm;
                if (c < disp.cols - 1) dcsv << ",";
            }
            dcsv << "\n";
        }

        // ── 3. Point cloud PLY ───────────────────────────────────────────────
        std::ofstream ply(session_dir + "/pointclouds/frame_" + fid + ".ply");
        ply << "ply\nformat ascii 1.0\n"
            << "element vertex " << pts.size() << "\n"
            << "property float x\nproperty float y\nproperty float z\n"
            << "end_header\n"
            << std::fixed << std::setprecision(4);
        for (auto& p : pts)
            ply << p.x << " " << p.y << " " << p.z << "\n";
    }

    // Write tracked feature overlay PNG + append to feature CSV
    // features: vector of (feature_id, cv::Point2f pixel_pos)
    static void write_features(int64_t ts_ns,
                               const cv::Mat& left_frame,
                               const cv::Mat& disp,
                               const std::vector<std::pair<int, cv::Point2f>>& features) {
        if (session_dir.empty()) return;
        std::string fid = vio_frame_id(frame_num);

        // ── Feature overlay PNG ──────────────────────────────────────────────
        cv::Mat overlay;
        if (!left_frame.empty()) {
            if (left_frame.channels() == 1)
                cv::cvtColor(left_frame, overlay, cv::COLOR_GRAY2BGR);
            else
                overlay = left_frame.clone();

            for (auto& f : features) {
                cv::circle(overlay, f.second, 3,
                           cv::Scalar(0, 255, 0), cv::FILLED);
                cv::circle(overlay, f.second, 4,
                           cv::Scalar(0, 0, 255), 1);
            }
            // Feature count HUD
            char hud[64];
            snprintf(hud, sizeof(hud), "Features: %d  Frame: %s",
                     (int)features.size(), fid.c_str());
            cv::putText(overlay, hud, {5, 20},
                        cv::FONT_HERSHEY_SIMPLEX, 0.5,
                        cv::Scalar(255, 255, 0), 1);
            cv::imwrite(session_dir + "/features/frame_" + fid + "_features.png",
                        overlay);
        }

        // ── Features CSV rows ────────────────────────────────────────────────
        for (auto& f : features) {
            int px = (int)f.second.x, py = (int)f.second.y;
            float depth_mm = 0.0f;
            if (!disp.empty() && py >= 0 && py < disp.rows &&
                px >= 0 && px < disp.cols && focal_px > 0.0) {
                uint16_t raw_d = disp.at<uint16_t>(py, px);
                if (raw_d > 0) {
                    double d_px = raw_d / 16.0;
                    depth_mm = (float)(focal_px * baseline_m * 1000.0 / d_px);
                }
            }
            feat_csv << ts_ns << "," << f.first << ","
                     << std::fixed << std::setprecision(2)
                     << f.second.x << "," << f.second.y << ","
                     << std::setprecision(1) << depth_mm << "\n";
        }
        feat_csv.flush();

        frame_num++;
    }

    static void write_raw_video(const std::string& type, const cv::Mat& frame) {
        if (frame.empty()) return;
        if (type == "left" && vw_left.isOpened()) vw_left.write(frame);
        else if (type == "right" && vw_right.isOpened()) vw_right.write(frame);
        else if (type == "rgb" && vw_rgb.isOpened()) vw_rgb.write(frame);
    }
}  // namespace vio_ft_out
#endif  // VIO_HAS_OPENCV

// ─────────────────────────────────────────────────────────────────────────────
// VIO Estimator outputs  (called from visualization.cpp / pubOdometry)
// ─────────────────────────────────────────────────────────────────────────────
namespace vio_pose_out {
    static std::ofstream traj_csv;

    static void init(const std::string& out_base) {
        std::string session_dir = vio_get_or_create_session(out_base);
        traj_csv.open(session_dir + "/pose/trajectory.csv", std::ios::out);
        traj_csv << "timestamp_s,x_m,y_m,z_m,qw,qx,qy,qz,vx_ms,vy_ms,vz_ms\n";
    }

    static void write(double t,
                      double px, double py, double pz,
                      double qw, double qx, double qy, double qz,
                      double vx, double vy, double vz) {
        if (!traj_csv.is_open()) return;
        traj_csv << std::fixed << std::setprecision(9) << t << ","
                 << std::setprecision(6)
                 << px << "," << py << "," << pz << ","
                 << qw << "," << qx << "," << qy << "," << qz << ","
                 << vx << "," << vy << "," << vz << "\n";
        traj_csv.flush();
    }
}  // namespace vio_pose_out

// ─────────────────────────────────────────────────────────────────────────────
// MAVLink outputs  (called from my_mavlink_udp.cpp)
// ─────────────────────────────────────────────────────────────────────────────
namespace vio_mav_out {
    static std::ofstream mav_csv;

    static void init(const std::string& out_base) {
        std::string session_dir = vio_get_or_create_session(out_base);
        mav_csv.open(session_dir + "/mavlink/mavlink_log.csv", std::ios::out);
        mav_csv << "timestamp_us,x_m,y_m,z_m,roll_rad,pitch_rad,yaw_rad,"
                   "reset_counter\n";
    }

    static void write(int64_t ts_us,
                      float x, float y, float z,
                      float roll, float pitch, float yaw,
                      uint8_t reset_counter) {
        if (!mav_csv.is_open()) return;
        mav_csv << ts_us << ","
                << std::fixed << std::setprecision(6)
                << x << "," << y << "," << z << ","
                << roll << "," << pitch << "," << yaw << ","
                << (int)reset_counter << "\n";
        mav_csv.flush();
    }
}  // namespace vio_mav_out
