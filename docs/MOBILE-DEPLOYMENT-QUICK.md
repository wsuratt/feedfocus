# Quick Mobile API Deployment (5 minutes)

Since you already have `feed-focus.com` running with nginx + SSL, adding mobile API support is super easy!

---

## Step 1: Add DNS Record (2 min)

Go to your domain registrar and add:
- **Type**: A
- **Name**: `api`
- **Value**: `3.17.64.149`
- **TTL**: Auto

This creates `api.feed-focus.com` pointing to your server.

Wait 5 minutes, then test:
```bash
nslookup api.feed-focus.com
```

---

## Step 2: Update Nginx Config (1 min)

SSH into your server:
```bash
ssh ubuntu@3.17.64.149
```

Edit your nginx config:
```bash
sudo nano /etc/nginx/sites-available/feedfocus
# (or wherever your config is)
```

**Add the mobile API server block** from `nginx-mobile-update.conf` (I created this file for you) to the END of your config file.

Test the config:
```bash
sudo nginx -t
```

Reload nginx:
```bash
sudo systemctl reload nginx
```

---

## Step 3: Get SSL for Mobile Subdomain (1 min)

```bash
sudo certbot --nginx -d api.feed-focus.com
```

Choose option 2 (redirect HTTP to HTTPS). Done!

---

## Step 4: Add API Key (Optional but Recommended)

Generate key:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Update your backend `main.py`:
```python
from fastapi import Header, HTTPException, Depends
import os

# At the top of your file
API_KEY = os.getenv("FEEDFOCUS_API_KEY", "")

async def verify_api_key(x_api_key: str = Header(None)):
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return x_api_key

# Add to your endpoints:
@app.get("/api/feed", dependencies=[Depends(verify_api_key)])
async def get_feed(...):
    # existing code
```

Set the API key environment variable:
```bash
export FEEDFOCUS_API_KEY="your-generated-key"
# Add to your backend startup script or systemd service
```

Update mobile app `.env`:
```
API_KEY=your-generated-key
```

---

## Step 5: Test Mobile App

Restart Metro:
```bash
npx expo start -c
```

Reload your app. It should now connect to `https://api.feed-focus.com/api/feed`!

---

## Architecture

Your setup now looks like:

```
feed-focus.com (web frontend)
    ↓ HTTPS
    └─> nginx
        ├─> / → Static files (your web app)
        └─> /api → Backend (port 8000)

api.feed-focus.com (mobile API)
    ↓ HTTPS
    └─> nginx
        └─> /api → Same backend (port 8000)
```

Both web and mobile use the **same backend**, just different domains!

---

## Benefits

✅ **Same backend serves both** web and mobile
✅ **No code changes** to your existing web deployment
✅ **Separate subdomain** for mobile (easier to manage, monitor, rate-limit)
✅ **HTTPS everywhere**
✅ **5 minute setup**

---

## Troubleshooting

**Mobile app can't connect:**
1. Check DNS: `nslookup api.feed-focus.com`
2. Check SSL: `curl https://api.feed-focus.com/health`
3. Check nginx: `sudo nginx -t && sudo systemctl status nginx`
4. Check backend: Your existing backend logs

**403 errors:**
- Check API key in mobile `.env`
- Check API key in backend environment
