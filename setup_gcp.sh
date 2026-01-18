#!/bin/bash

# =============================================================================
# GCP Setup Script for Transcription Server
# Target Instance: n2-highmem-8 (Ubuntu 22.04 LTS)
# =============================================================================

echo "🚀 Starting GCP Server Setup..."

# 1. Update & Install Dependencies
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    htop \
    git \
    ffmpeg

# 2. Install Docker & Docker Compose (Official Script)
if ! command -v docker &> /dev/null; then
    echo "🐳 Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
    
    # Enable non-root docker usage
    sudo usermod -aG docker $USER
    echo "✅ Docker installed."
else
    echo "✅ Docker already installed."
fi

# 3. Optimize System for AI Workloads
# Increase max map count for large models
sudo sysctl -w vm.max_map_count=262144
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf

# 4. Create Project Directories
mkdir -p downloads uploads
chmod 777 downloads uploads

echo ""
echo "=========================================="
echo "🎉 Setup Complete!"
echo "=========================================="
echo ""
echo "📋 Next Steps:"
echo "1. Log out and log back in (to apply Docker group)"
echo "2. Clone your repo or copy files to this directory"
echo "3. Create .env file with your API keys:"
echo "   cp .env.example .env && nano .env"
echo "4. Build and run:"
echo "   docker compose up -d --build"
echo ""
echo "🔗 Verify: curl http://localhost/health"
echo ""
