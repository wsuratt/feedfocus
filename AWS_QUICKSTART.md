# AWS Deployment - Quick Start

## Step 1: Push to GitHub

```bash
# Create GitHub repo at: https://github.com/new

# Add remote and push
git remote add origin git@github.com:yourusername/slm-crawl.git
git branch -M main
git push -u origin main
```

## Step 2: Launch EC2 Instance

1. **AWS Console** → EC2 → Launch Instance
2. **Configuration:**
   - Name: `insight-feed-server`
   - AMI: Ubuntu 22.04 LTS
   - Instance type: t3.small ($15/month)
   - Create new key pair (download .pem file)
   - Security group: Allow ports 22, 80, 443, 8000

3. **Launch** and note your public IP

## Step 3: Initial Server Setup

```bash
# Connect to server
chmod 400 ~/Downloads/your-key.pem
ssh -i ~/Downloads/your-key.pem ubuntu@YOUR_EC2_IP

# Run setup script
curl -s https://raw.githubusercontent.com/yourusername/slm-crawl/main/setup-server.sh | bash
```

## Step 4: Deploy Your App

```bash
# On server
cd ~
git clone git@github.com:yourusername/slm-crawl.git
cd slm-crawl

# Install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Setup environment
cp .env.example .env
nano .env  # Add your API keys

# Initialize database
python db/init_db.py

# Install PM2
sudo npm install -g pm2

# Start backend
cd backend
pm2 start "uvicorn main:app --host 0.0.0.0 --port 8000" --name insight-feed
pm2 save
pm2 startup  # Run the command it gives you

# Build frontend
cd ../frontend
npm install
npm run build

# Configure Nginx (copy from AWS_DEPLOYMENT.md)
```

## Step 5: Setup GitHub Actions

1. **GitHub repo** → Settings → Secrets → New secret

Add these secrets:
```
AWS_EC2_HOST = your_ec2_ip
AWS_EC2_USER = ubuntu
AWS_EC2_KEY = paste_your_pem_file_contents
ANTHROPIC_API_KEY = your_key
GROQ_API_KEY = your_key
```

2. **Push to main branch** → Auto-deploys!

## Quick Commands

```bash
# View logs
pm2 logs insight-feed

# Restart backend
pm2 restart insight-feed

# Manual deploy
ssh -i your-key.pem ubuntu@YOUR_IP
cd ~/slm-crawl && git pull && pm2 restart insight-feed
```

## Next Steps

- Add domain name (Route 53)
- Setup SSL (certbot)
- Configure CloudWatch
- Scale to ECS Fargate

See DEPLOYMENT.md for full guide.
