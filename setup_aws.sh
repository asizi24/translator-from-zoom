#!/bin/bash
# AWS EC2 Setup Script for Zoom Transcription App

set -e

echo "=== Installing Docker ==="
sudo apt-get update
sudo apt-get install -y apt-transport-https ca-certificates curl software-properties-common
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

echo "=== Configuring Docker ==="
sudo usermod -aG docker $USER
sudo systemctl enable docker
sudo systemctl start docker

echo "=== Creating Application Directories ==="
sudo mkdir -p /opt/zoom-transcription/{downloads,uploads,logs}
sudo chown -R $USER:$USER /opt/zoom-transcription
chmod -R 755 /opt/zoom-transcription

echo "=== Setup Complete! ==="
echo "1. Clone your repository to /opt/zoom-transcription"
echo "2. Create .env file with your API keys"
echo "3. Run: docker-compose up -d"
