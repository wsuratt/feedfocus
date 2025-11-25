# FeedFocus Production Deployment

Domain: `feed-focus.com`
API Subdomain: `api.feed-focus.com`
Server IP: `3.17.64.149`

---

## Step 1: Configure DNS (Do this first!)

Go to your domain registrar (where you bought feed-focus.com):

1. Add an **A record**:
   - **Name/Host**: `api`
   - **Type**: A
   - **Value**: `3.17.64.149`
   - **TTL**: 3600 (or automatic)

Wait 5-10 minutes for DNS to propagate. Test with:
```bash
dig api.feed-focus.com
# or
nslookup api.feed-focus.com
```

---

## Step 2: SSH into Your Server

```bash
ssh ubuntu@3.17.64.149
```

---

## Step 3: Install Nginx & Certbot

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install nginx
sudo apt install nginx -y

# Install certbot for SSL
sudo apt install certbot python3-certbot-nginx -y
```

---

## Step 4: Create Nginx Configuration

```bash
sudo nano /etc/nginx/sites-available/feedfocus
```

Paste this:

```nginx
server {
    listen 80;
    server_name api.feed-focus.com;

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
        
        # Timeout settings for slow responses
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Health check endpoint
    location /health {
        proxy_pass http://localhost:8000/health;
    }
}
```

Enable the site:
```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/feedfocus /etc/nginx/sites-enabled/

# Remove default site
sudo rm /etc/nginx/sites-enabled/default

# Test config
sudo nginx -t

# Restart nginx
sudo systemctl restart nginx
```

---

## Step 5: Get SSL Certificate (HTTPS)

```bash
# Get SSL certificate
sudo certbot --nginx -d api.feed-focus.com

# Follow prompts:
# 1. Enter your email
# 2. Agree to terms
# 3. Choose option 2 to redirect HTTP to HTTPS
```

Certbot will automatically update your nginx config with SSL settings.

---

## Step 6: Generate API Key

```bash
# Generate a secure random API key
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Copy this key!** You'll need it for both server and mobile app.

---

## Step 7: Add API Key Authentication to FastAPI

Edit your backend:
```bash
cd /path/to/your/feedfocus/backend
nano main.py
```

Add this near the top:

```python
from fastapi import FastAPI, Header, HTTPException, Depends
import os

app = FastAPI()

# Load API key from environment
API_KEY = os.getenv("FEEDFOCUS_API_KEY", "")

async def verify_api_key(x_api_key: str = Header(None)):
    """Verify API key from request header"""
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
    return x_api_key

# Add to your existing routes:
@app.get("/api/feed", dependencies=[Depends(verify_api_key)])
async def get_feed(interests: str = "", limit: int = 50):
    # Your existing code
    pass

@app.post("/api/feed/engage", dependencies=[Depends(verify_api_key)])
async def record_engagement(data: dict):
    # Your existing code
    pass

# Health check (no auth needed)
@app.get("/health")
async def health():
    return {"status": "ok"}
```

---

## Step 8: Set Environment Variable

```bash
# Add to your shell profile
echo 'export FEEDFOCUS_API_KEY="your-generated-key-here"' >> ~/.bashrc
source ~/.bashrc

# Or create a .env file
nano ~/feedfocus/.env
```

Add:
```
FEEDFOCUS_API_KEY=your-generated-key-here
```

---

## Step 9: Run Backend with Systemd

Create service file:
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
WorkingDirectory=/home/ubuntu/feedfocus
Environment="PATH=/home/ubuntu/.local/bin:/usr/bin"
Environment="FEEDFOCUS_API_KEY=your-generated-key-here"
ExecStart=/usr/bin/python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Replace `your-generated-key-here` with your actual API key!**

Enable and start:
```bash
sudo systemctl enable feedfocus
sudo systemctl start feedfocus
sudo systemctl status feedfocus
```

---

## Step 10: Update AWS Security Group

Remove port 8000, only allow:
- **Port 80** (HTTP - redirects to HTTPS)
- **Port 443** (HTTPS)
- **Port 22** (SSH)

Backend now only accessible via nginx on port 80/443.

---

## Step 11: Update Mobile App

Update `.env` with your generated API key:
```
API_BASE_URL=https://api.feed-focus.com
API_KEY=your-generated-key-here
```

Restart Metro:
```bash
npx expo start -c
```

Reload your app and test!

---

## Testing

```bash
# Test health endpoint (no auth)
curl https://api.feed-focus.com/health

# Test feed endpoint (with auth)
curl -H "X-API-Key: your-key" https://api.feed-focus.com/api/feed?limit=5
```

---

## Monitoring & Logs

```bash
# View backend logs
sudo journalctl -u feedfocus -f

# View nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# Restart backend
sudo systemctl restart feedfocus

# Restart nginx
sudo systemctl restart nginx
```

---

## SSL Auto-Renewal

Certbot automatically renews. Test it:
```bash
sudo certbot renew --dry-run
```

---

## Troubleshooting

**Can't connect to API:**
1. Check DNS: `nslookup api.feed-focus.com`
2. Check backend: `sudo systemctl status feedfocus`
3. Check nginx: `sudo systemctl status nginx`
4. Check logs: `sudo journalctl -u feedfocus -n 50`

**403 Forbidden:**
- Check API key in mobile app `.env`
- Check API key in backend environment variable
- Make sure they match!

**Timeout errors:**
- Check backend is running: `curl localhost:8000/health`
- Check nginx can reach backend: `sudo tail -f /var/log/nginx/error.log`
