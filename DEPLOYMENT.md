# AWS Deployment Guide

Complete guide to deploying Insight Feed on AWS with Docker and GitHub Actions.

## Prerequisites

- AWS Account
- GitHub account  
- API keys for Anthropic and Groq
- Domain name (optional, recommended for SSL)

---

## Quick Start: EC2 + Docker

**Cost:** ~$15/month for t3.small

### Step 1: Push Code to GitHub

```bash
# Create repo at https://github.com/new
git remote add origin git@github.com:YOUR_USERNAME/feedfocus.git
git push -u origin main
```

### Step 2: Launch EC2 Instance

1. **AWS Console** → EC2 → Launch Instance
2. **Configuration:**
   - Name: insight-feed-server
   - AMI: Ubuntu 22.04 LTS
   - Instance type: t3.small (2 vCPU, 2GB RAM)
   - Create new key pair → Download .pem file
   - Storage: 20GB gp3

3. **Security Group** - Allow inbound:
   - Port 22 (SSH) from your IP
   - Port 80 (HTTP) from anywhere
   - Port 443 (HTTPS) from anywhere
   - Port 8000 (API) from anywhere

4. **Launch** and note your public IP

### Step 3: Connect and Setup Server

```bash
# Connect
chmod 400 ~/Downloads/your-key.pem
ssh -i ~/Downloads/your-key.pem ubuntu@YOUR_EC2_IP

# Install Docker
sudo apt update && sudo apt upgrade -y
sudo apt install -y docker.io docker-compose nginx
sudo systemctl enable docker
sudo usermod -aG docker ubuntu
newgrp docker

# Install Node.js
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Setup firewall
sudo ufw allow 22
sudo ufw allow 80
sudo ufw allow 443
sudo ufw --force enable
```

### Step 4: Clone and Configure

```bash
# Generate SSH key for GitHub
ssh-keygen -t ed25519 -C "your-email@example.com" -f ~/.ssh/id_ed25519 -N ""
cat ~/.ssh/id_ed25519.pub
# Copy and add to GitHub Settings → SSH Keys

# Clone repo
git clone git@github.com:YOUR_USERNAME/feedfocus.git
cd feedfocus

# Configure environment
cp .env.example .env
nano .env
# Add ANTHROPIC_API_KEY and GROQ_API_KEY
```

### Step 5: Deploy with Docker

```bash
# Start services
docker-compose up -d

# Initialize database
docker-compose exec backend python db/init_db.py

# Check status
docker-compose ps
docker-compose logs -f
```

### Step 6: Configure Nginx

```bash
sudo nano /etc/nginx/sites-available/insight-feed
```

Paste this:

```nginx
server {
    listen 80;
    server_name YOUR_EC2_IP;

    location / {
        proxy_pass http://localhost:8000\;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_cache_bypass $http_upgrade;
    }
}
```

Enable:

```bash
sudo ln -s /etc/nginx/sites-available/insight-feed /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

### Step 7: GitHub Actions Auto-Deploy

1. GitHub repo → Settings → Secrets → Add:
   - AWS_EC2_HOST = Your EC2 IP
   - AWS_EC2_USER = ubuntu
   - AWS_EC2_KEY = Contents of .pem file
   - ANTHROPIC_API_KEY = Your key
   - GROQ_API_KEY = Your key

2. Push to main → Auto-deploys!

**Your app is live at:** http://YOUR_EC2_IP

---

## Add SSL Certificate

```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d yourdomain.com
sudo certbot renew --dry-run
```

---

## Daily Commands

```bash
# View logs
docker-compose logs -f

# Restart
docker-compose restart

# Manual deploy
cd ~/feedfocus
git pull
docker-compose up -d --build

# Stop/Start
docker-compose down
docker-compose up -d
```

---

## Troubleshooting

**Container won't start:**
```bash
docker-compose logs backend
docker-compose restart
```

**Can't connect:**
- Check security group allows port 80
- Check: docker-compose ps
- Check: sudo systemctl status nginx

**Database issues:**
```bash
docker-compose exec backend python db/init_db.py
```

---

## Upgrade to ECS Fargate

**When you need auto-scaling and zero-downtime deploys.**

Cost: ~$50-70/month

1. Create ECR repository
2. Push Docker image
3. Create ECS cluster and service
4. GitHub Actions handles deployments

See .github/workflows/deploy-aws-ecs.yml

---

## Cost Breakdown

| Service | Monthly Cost |
|---------|-------------|
| EC2 t3.small | $15 |
| EBS Storage | $2 |
| Data Transfer | $4 |
| **Total** | **~$21/month** |

---

## Security Checklist

- [ ] SSH key-based auth only
- [ ] Firewall configured
- [ ] SSL certificate installed
- [ ] Regular updates
- [ ] Database backups
- [ ] CloudWatch monitoring

---

**Ready to deploy!** Follow the Quick Start above.
