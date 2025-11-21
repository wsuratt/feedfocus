#!/bin/bash
# AWS EC2 Server Setup Script
# Run with: curl -s https://raw.githubusercontent.com/yourusername/slm-crawl/main/setup-server.sh | bash

set -e

echo "🚀 Setting up Insight Feed server..."

# Update system
echo "📦 Updating system..."
sudo apt update && sudo apt upgrade -y

# Install Python
echo "🐍 Installing Python..."
sudo apt install -y python3-pip python3-venv

# Install Node.js
echo "📗 Installing Node.js..."
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Install Nginx
echo "🌐 Installing Nginx..."
sudo apt install -y nginx

# Install Docker
echo "🐳 Installing Docker..."
sudo apt install -y docker.io
sudo systemctl enable docker
sudo usermod -aG docker ubuntu

# Install Docker Compose
echo "🔧 Installing Docker Compose..."
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Setup firewall
echo "🔒 Configuring firewall..."
sudo ufw allow 22
sudo ufw allow 80
sudo ufw allow 443
sudo ufw allow 8000
echo "y" | sudo ufw enable

# Generate SSH key for GitHub
echo "🔑 Generating SSH key..."
if [ ! -f ~/.ssh/id_ed25519 ]; then
    ssh-keygen -t ed25519 -C "server@insight-feed" -f ~/.ssh/id_ed25519 -N ""
    echo ""
    echo "✅ SSH key generated! Add this to GitHub:"
    echo "   https://github.com/settings/ssh/new"
    echo ""
    cat ~/.ssh/id_ed25519.pub
    echo ""
fi

echo ""
echo "✅ Server setup complete!"
echo ""
echo "Next steps:"
echo "1. Add SSH key to GitHub (shown above)"
echo "2. Clone your repo: git clone git@github.com:yourusername/slm-crawl.git"
echo "3. Follow AWS_QUICKSTART.md for deployment"
echo ""
