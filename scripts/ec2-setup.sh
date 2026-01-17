#!/bin/bash
# =============================================================================
# EC2 Initial Setup Script for Flask Transcription App
# Run this ONCE when setting up a new EC2 instance
# 
# Usage: 
#   chmod +x ec2-setup.sh
#   ./ec2-setup.sh
# =============================================================================

set -e  # Exit on any error

echo "🚀 Starting EC2 Setup for Transcription App..."
echo "=============================================="

# Update system packages
echo "📦 Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y

# Install Docker
echo "🐳 Installing Docker..."
sudo apt-get install -y ca-certificates curl gnupg lsb-release

# Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add Docker repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Add ubuntu user to docker group (so we don't need sudo)
echo "👤 Adding ubuntu user to docker group..."
sudo usermod -aG docker ubuntu

# Create application directory (matching GitHub repo name)
echo "📁 Creating application directory..."
APP_DIR=~/translator-from-zoom
mkdir -p $APP_DIR
cd $APP_DIR

# Create required subdirectories
mkdir -p downloads uploads logs

# Fix permissions explicitly for the app
chmod -R 755 downloads uploads logs
chown -R ubuntu:ubuntu downloads uploads logs
echo "✅ Folders created with correct permissions"

# Create nginx.conf
echo "🔧 Creating nginx configuration..."
cat > nginx.conf << 'EOF'
events {
    worker_connections 1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;
    
    # Logging
    access_log /var/log/nginx/access.log;
    error_log /var/log/nginx/error.log;

    # Gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;

    # Upstream Flask app
    upstream flask_app {
        server web:5000;
    }

    server {
        listen 80;
        server_name _;

        # Max upload size (for audio/video files)
        client_max_body_size 500M;
        
        # Timeouts for long transcriptions
        proxy_connect_timeout 600s;
        proxy_send_timeout 600s;
        proxy_read_timeout 600s;

        location / {
            proxy_pass http://flask_app;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Health check endpoint
        location /health {
            proxy_pass http://flask_app/health;
        }
    }
}
EOF

# Create placeholder .env file
echo "🔐 Creating placeholder .env file..."
cat > .env << 'EOF'
# These will be populated by GitHub Actions during deployment
HF_TOKEN=your_huggingface_token_here
GOOGLE_API_KEY=your_google_api_key_here
FLASK_ENV=production

# Flask Security - Generate your own key with: python3 -c "import secrets; print(secrets.token_hex(32))"
FLASK_SECRET_KEY=REPLACE_WITH_SECURE_KEY

# Auto-Shutdown Configuration (AWS cost savings)
AUTO_SHUTDOWN=true
SHUTDOWN_DRY_RUN=false
IDLE_TIMEOUT_MINUTES=15
EOF

echo ""
echo "=============================================="
echo "✅ EC2 Setup Complete!"
echo "=============================================="
echo ""
echo "📋 Next Steps:"
echo "1. Log out and log back in (for docker group to take effect)"
echo "   Run: exit"
echo "   Then SSH back in"
echo ""
echo "2. Verify Docker is working:"
echo "   Run: docker --version"
echo ""
echo "3. Push your code to GitHub - the Actions workflow will deploy automatically!"
echo ""
echo "4. Your app will be available at: http://YOUR_ELASTIC_IP"
echo ""
