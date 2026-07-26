FROM ubuntu:22.04

# Avoid interactive prompts during package installations
ENV DEBIAN_FRONTEND=noninteractive

# Use bash with pipefail for RUN instructions to catch piped command failures
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Update & Upgrade Ubuntu
RUN apt-get update && apt-get upgrade -y

# Install Essential Build Tools
RUN apt-get install -y build-essential cmake git wget curl python3

# Workspace setup
RUN mkdir -p /root/nongps_pro /outputs
WORKDIR /root/nongps_pro

# Copy output patches into the image (must be done before clones so
# the Python injector can run after each clone)
COPY patches/ /patches/

# Install and Build VINS-Fusion
# Install Ceres Solver dependencies
RUN apt-get install -y libeigen3-dev libgoogle-glog-dev libgflags-dev libsuitesparse-dev libopencv-dev

# Clone and Build Ceres Solver 2.1.0
RUN git clone https://ceres-solver.googlesource.com/ceres-solver && \
    cd ceres-solver && \
    git checkout 2.1.0 && \
    mkdir build && \
    cd build && \
    cmake .. \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_CXX_STANDARD=17 \
        -DBUILD_TESTING=OFF \
        -DBUILD_EXAMPLES=OFF && \
    make -j2 && \
    make install && \
    ldconfig

# Clone and Build VINS-Fusion (apm_wiki branch)
# -- inject trajectory CSV output into visualization.cpp before building --
RUN git clone https://github.com/chobitsfan/VINS-Fusion.git && \
    cd VINS-Fusion && \
    git switch apm_wiki && \
    python3 /patches/patch_sources.py 2>&1 | grep -E "\[2/3\]|\[OK\]|\[FAIL\]|FAILED|success" && \
    cd vins_estimator && \
    cmake . && \
    make -j2

# Install and Build OAK-D
# Install and Build the Dependency - Depthai-Core
RUN git clone https://github.com/luxonis/depthai-core.git && \
    cd depthai-core && \
    git checkout v2.25.0 && \
    git submodule update --init --recursive && \
    apt-get install -y libusb-1.0-0-dev libopencv-dev libspdlog-dev libglfw3-dev && \
    cmake -S. -Bbuild -DDEPTHAI_OPENCV_SUPPORT=ON && \
    cmake --build build --target install && \
    ldconfig

# Clone and Build OAK-D Package (oak_d_vins_cpp)
# -- inject depth/feature/IMU CSV+PNG+PLY output into feature_tracker.cpp before building --
RUN git clone https://github.com/chobitsfan/oak_d_vins_cpp.git && \
    cd oak_d_vins_cpp && \
    git switch apm_wiki && \
    python3 /patches/patch_sources.py 2>&1 | grep -E "\[1/3\]|\[OK\]|\[FAIL\]|FAILED|success" && \
    cmake -D'depthai_DIR=../depthai-core/build/install/lib/cmake/depthai' . && \
    make

# Install and Build mavlink-udp-proxy
# -- inject MAVLink CSV output into my_mavlink_udp.cpp before building --
RUN git clone https://github.com/chobitsfan/mavlink-udp-proxy.git && \
    cd mavlink-udp-proxy && \
    git switch apm_wiki && \
    git submodule update --init --recursive && \
    python3 /patches/patch_sources.py 2>&1 | grep -E "\[3/3\]|\[OK\]|\[FAIL\]|FAILED|success" && \
    ./build_it

CMD ["/bin/bash"]
