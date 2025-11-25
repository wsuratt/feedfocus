# Secure Production Setup for FeedFocus Backend

## Prerequisites
- Domain name pointing to your EC2 instance (e.g., api.feedfocus.com)
- SSH access to your EC2 instance

## Step 1: Install Nginx and Certbot

```bash
# SSH into your EC2 instance
ssh ubuntu@3.17.64.149

# Update system
sudo apt update
sudo apt upgrade -y

# Install nginx
sudo apt install nginx -y

# Install certbot for Let's Encrypt SSL
sudo apt install certbot python3-certbot-nginx -y
```

## Step 2: Configure Nginx (Initial HTTP Config)

```bash
# Create nginx config
sudo nano /etc/nginx/sites-available/feedfocus
```

Paste this configuration:

```nginx
server {
    listen 80;
    server_name api.feedfocus.com;  # Replace with your domain

    # Proxy API requests to FastAPI backend
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    # Health check endpoint
    location /health {
        proxy_pass http://localhost:8000/health;
    }
}
```

Enable the site:
```bash
# Create symbolic link
sudo ln -s /etc/nginx/sites-available/feedfocus /etc/nginx/sites-enabled/

# Remove default site
sudo rm /etc/nginx/sites-enabled/default

# Test nginx config
sudo nginx -t

# Restart nginx
sudo systemctl restart nginx
```

## Step 3: Get SSL Certificate (HTTPS)

```bash
# Get SSL certificate from Let's Encrypt
sudo certbot --nginx -d api.feedfocus.com

# Follow prompts:
# - Enter email
# - Agree to terms
# - Choose to redirect HTTP to HTTPS (option 2)
```

Certbot will automatically:
- Get SSL certificate
- Update nginx config for HTTPS
- Set up auto-renewal

## Step 4: Add Authentication to FastAPI

Update your FastAPI backend to require API keys:

```python
# backend/main.py
from fastapi import FastAPI, Header, HTTPException, Depends
from typing import Optional
import os

app = FastAPI()

# Load API key from environment variable
API_KEY = os.getenv("API_KEY", "your-secret-key-here")

async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return x_api_key

@app.get("/api/feed", dependencies=[Depends(verify_api_key)])
async def get_feed(interests: str = "", limit: int = 50):
    # Your existing feed logic
    pass

@app.post("/api/feed/engage", dependencies=[Depends(verify_api_key)])
async def record_engagement(data: dict):
    # Your existing engagement logic
    pass

# Health check (no auth needed)
@app.get("/health")
async def health():
    return {"status": "ok"}
```

## Step 5: Set Environment Variables on Server

```bash
# Create .env file on server
sudo nano /var/www/feedfocus/.env
```

Add:
```
API_KEY=your-secure-random-key-here
DATABASE_URL=your-database-url
```

Generate a secure API key:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Step 6: Run Backend as a Service

Create systemd service:
```bash
sudo nano /etc/systemd/system/feedfocus.service
```

Paste:
```ini
[Unit]
Description=FeedFocus FastAPI Backend
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/var/www/feedfocus
Environment="PATH=/home/ubuntu/.local/bin:/usr/bin"
EnvironmentFile=/var/www/feedfocus/.env
ExecStart=/usr/bin/python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable feedfocus
sudo systemctl start feedfocus
sudo systemctl status feedfocus
```

## Step 7: Final Nginx Security Configuration

After certbot, your config will look like this:

```nginx
server {
    server_name api.feedfocus.com;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # CORS for mobile app
    add_header 'Access-Control-Allow-Origin' '*' always;
    add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS' always;
    add_header 'Access-Control-Allow-Headers' 'Content-Type, X-API-Key' always;

    location /api/ {
        # Rate limiting (optional but recommended)
        limit_req zone=api_limit burst=10 nodelay;
        
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        
        # Handle preflight
        if ($request_method = 'OPTIONS') {
            return 204;
        }
    }

    location /health {
        proxy_pass http://localhost:8000/health;
    }

    listen 443 ssl; # managed by Certbot
    ssl_certificate /etc/letsencrypt/live/api.feedfocus.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.feedfocus.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
}

server {
    if ($host = api.feedfocus.com) {
        return 301 https://$host$request_uri;
    }

    listen 80;
    server_name api.feedfocus.com;
    return 404;
}

# Rate limiting zone (add at top of nginx.conf)
http {
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
}
```

## Step 8: Update Mobile App

Update `.env`:
```
API_BASE_URL=https://api.feedfocus.com
API_KEY=your-secure-random-key-here
```

Update `src/services/api.ts`:
```typescript
import { API_BASE_URL, API_KEY } from '@env';

const apiClient = axios.create({
  baseURL: API_BASE_URL || 'https://api.feedfocus.com',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': API_KEY, // Add API key to all requests
  },
});
```

## Step 9: AWS Security Group

Update inbound rules:
- **Remove**: Port 8000 (backend only accessible via nginx)
- **Keep**: Port 80 (HTTP - will redirect to HTTPS)
- **Keep**: Port 443 (HTTPS)
- **Keep**: Port 22 (SSH)

## Maintenance

### Auto-renewal of SSL
Certbot sets up auto-renewal. Test it:
```bash
sudo certbot renew --dry-run
```

### Monitor logs
```bash
# Nginx logs
sudo tail -f /var/log/nginx/error.log

# Backend logs
sudo journalctl -u feedfocus -f
```

### Update backend
```bash
cd /var/www/feedfocus
git pull
sudo systemctl restart feedfocus
```

## Security Checklist

- ✅ HTTPS with Let's Encrypt SSL
- ✅ API key authentication
- ✅ Security headers (HSTS, X-Frame-Options, etc.)
- ✅ CORS configured properly
- ✅ Rate limiting
- ✅ Backend not exposed directly (only via nginx)
- ✅ Environment variables for secrets
- ✅ Automatic SSL renewal
- ✅ Backend runs as systemd service (auto-restart)
