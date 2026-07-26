# Setup Guide

This document provides a comprehensive guide to setting up the VIO Docker environment.

## Prerequisites
- A compatible Linux environment (tested on Ubuntu)
- Basic terminal knowledge
- Internet connection for downloading Docker and images

## Installation Process
1. Clone the repository to your local machine.
2. Navigate to the `vio_docker` directory.
3. Make all scripts executable using `chmod +x scripts/*.sh`.
4. Run `./scripts/install.sh`. This script will update packages, install Docker and Docker Compose, start the Docker daemon, and add your user to the `docker` group.
5. Log out and log back in, or restart your machine. This is crucial for the group changes to take effect.
6. Run `./scripts/build.sh` to build the required Docker images.
7. Run `./scripts/run.sh` to start the environment.

For any issues during this process, please refer to the `troubleshooting.md` document.
