#!/bin/bash
set -e
cd "$(dirname "$0")/.."

if command -v docker &> /dev/null
then
    echo "Docker already installed."
else
    echo "Installing Docker..."
    sudo apt update
    sudo apt install -y docker.io docker-compose-v2
fi

sudo systemctl enable docker
sudo systemctl start docker

sudo usermod -aG docker $USER

echo ""
echo "Installation Complete."
echo "Please logout/login before running ./ubuntu/build.sh"
