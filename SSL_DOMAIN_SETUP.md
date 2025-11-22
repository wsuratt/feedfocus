# SSL & Custom Domain Setup Guide

Complete guide to setting up a custom domain with SSL/HTTPS for your Insight Feed application.

---

## Overview

**What you'll accomplish:**
- ✅ Register a custom domain (e.g., insightfeed.com)
- ✅ Point domain to your EC2 instance
- ✅ Get free SSL certificate from Let's Encrypt
- ✅ Configure automatic HTTPS redirect
- ✅ Set up auto-renewal for SSL certificates

**Time required:** ~30 minutes  
**Cost:** ~$10-15/year for domain

---

## Step 1: Register a Domain

### Recommended Registrars

**Option A: Namecheap** (Easiest)
- Cost: ~$10/year
- URL: https://www.namecheap.com
- Pros: Simple interface, good support

**Option B: Google Domains**
- Cost: ~$12/year  
- URL: https://domains.google
- Pros: Clean UI, Google integration

**Option C: AWS Route 53**
- Cost: ~$12/year + $0.50/month hosting
- URL: AWS Console → Route 53
- Pros: Integrated with EC2

**Option D: Cloudflare**
- Cost: ~$10/year
- URL: https://www.cloudflare.com
- Pros: Free CDN and DDoS protection included

### Registration Steps

1. Search for your desired domain
2. Add to cart and checkout
3. Complete registration
4. **Save your login credentials!**

---

## Step 2: Point Domain to EC2

### Get Your EC2 Public IP

```bash
# SSH to your EC2 instance
ssh -i ~/Downloads/feed-focus.pem ubuntu@YOUR_CURRENT_IP

# Get public IP
curl http://169.254.169.254/latest/meta-data/public-ipv4
```

**Save this IP** - you'll need it for DNS configuration.

### Configure DNS Records

#### If Using Namecheap:

1. Log in to Namecheap
2. Dashboard → **Domain List** → Click **Manage** next to your domain
3. Go to **Advanced DNS** tab
4. Add these records:

```
Type: A Record
Host: @
Value: YOUR_EC2_IP
TTL: Automatic (or 300)

Type: A Record  
Host: www
Value: YOUR_EC2_IP
TTL: Automatic (or 300)
```

#### If Using Google Domains:

1. Go to **My domains**
2. Click your domain → **DNS**
3. Scroll to **Custom records**
4. Add:

```
Host name: @
Type: A
TTL: 5 minutes
Data: YOUR_EC2_IP

Host name: www
Type: A
TTL: 5 minutes
Data: YOUR_EC2_IP
```

#### If Using AWS Route 53:

1. **Route 53** → **Hosted zones** → Create hosted zone
2. Domain name: `yourdomain.com` → Create
3. **Create record**:

```
Record name: (leave blank for root)
Record type: A
Value: YOUR_EC2_IP
TTL: 300

Click "Add another record":
Record name: www
Record type: A
Value: YOUR_EC2_IP
TTL: 300
```

4. **Update nameservers** at your registrar:
   - Copy the 4 NS records from Route 53
   - Paste them in your registrar's nameserver settings

### Verify DNS Propagation

**Wait 5-15 minutes**, then test:

```bash
# On your laptop
nslookup yourdomain.com

# Should return your EC2 IP
```

Or use online tools:
- https://dnschecker.org
- https://www.whatsmydns.net

---

## Step 3: Get SSL Certificate

### Stop Docker Temporarily

```bash
# SSH to EC2
cd ~/feedfocus
sudo docker-compose down
```

### Install Certbot

```bash
sudo apt update
sudo apt install certbot -y
```

### Obtain SSL Certificate

```bash
# Replace yourdomain.com with your actual domain
sudo certbot certonly --standalone \
  -d yourdomain.com \
  -d www.yourdomain.com \
  --email your@email.com \
  --agree-tos \
  --no-eff-email
```

**Follow the prompts:**
- Enter your email
- Agree to Terms of Service
- Decline marketing emails (optional)

**Certificates will be saved to:**
```
/etc/letsencrypt/live/yourdomain.com/fullchain.pem
/etc/letsencrypt/live/yourdomain.com/privkey.pem
```

---

## Step 4: Configure Nginx for SSL

### Create Certbot Directories

```bash
cd ~/feedfocus
mkdir -p certbot/conf certbot/www
```

### Update nginx.conf

Edit `~/feedfocus/nginx.conf`:

```bash
nano ~/feedfocus/nginx.conf
```

**Replace the entire `http` block with:**

```nginx
events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    upstream backend {
        server backend:8000;
    }

    # HTTP - Redirect to HTTPS
    server {
        listen 80;
        server_name yourdomain.com www.yourdomain.com;  # ← CHANGE THIS
        
        # Let's Encrypt challenge
        location /.well-known/acme-challenge/ {
            root /var/www/certbot;
        }
        
        # Redirect all other traffic to HTTPS
        location / {
            return 301 https://$host$request_uri;
        }
    }

    # HTTPS - Main application
    server {
        listen 443 ssl http2;
        server_name yourdomain.com www.yourdomain.com;  # ← CHANGE THIS

        # SSL certificates
        ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;  # ← CHANGE THIS
        ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;  # ← CHANGE THIS
        
        # SSL configuration
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;
        ssl_prefer_server_ciphers on;
        ssl_session_cache shared:SSL:10m;
        ssl_session_timeout 10m;

        # Frontend - Serve static files
        location / {
            root /usr/share/nginx/html;
            try_files $uri $uri/ /index.html;
            
            # Set proper MIME types
            types {
                text/html html;
                text/css css;
                application/javascript js;
            }
        }

        # Backend API - Proxy to FastAPI
        location /api {
            proxy_pass http://backend;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection 'upgrade';
            proxy_cache_bypass $http_upgrade;
        }

        # Health check endpoint
        location /health {
            proxy_pass http://backend;
        }
    }
}
```

**Important:** Replace all instances of `yourdomain.com` with your actual domain!

### Update docker-compose.yml

The file already has SSL support. Verify it looks like this:

```yaml
nginx:
  image: nginx:alpine
  ports:
    - "80:80"
    - "443:443"
  volumes:
    - ./nginx.conf:/etc/nginx/nginx.conf:ro
    - ./frontend/dist:/usr/share/nginx/html:ro
    - /etc/letsencrypt:/etc/letsencrypt:ro  # ← SSL certificates
    - ./certbot/www:/var/www/certbot:ro
  depends_on:
    - backend
  restart: unless-stopped
```

---

## Step 5: Deploy with SSL

### Commit Changes

```bash
cd ~/feedfocus
git add nginx.conf
git commit -m "Add SSL configuration for production"
git push
```

### Restart Docker with SSL

```bash
sudo docker-compose up -d --build
```

**Wait 3-5 minutes for build to complete.**

### Verify Containers Running

```bash
sudo docker-compose ps

# Should show both containers as "Up"
```

---

## Step 6: Test Your Site

### Access Your Domain

**Open in browser:**
```
https://yourdomain.com
```

**You should see:**
- ✅ 🔒 Padlock icon in address bar
- ✅ "Connection is secure"
- ✅ Your Insight Feed application loads

**Test HTTP redirect:**
```
http://yourdomain.com
```
Should automatically redirect to `https://yourdomain.com`

### Test SSL Grade

Check your SSL configuration:
- https://www.ssllabs.com/ssltest/
- Enter your domain
- Should get an **A** or **A+** rating

---

## Step 7: Set Up Auto-Renewal

SSL certificates expire every 90 days. Set up automatic renewal:

### Create Renewal Script

```bash
sudo nano /usr/local/bin/renew-ssl.sh
```

**Paste this:**

```bash
#!/bin/bash
# Renew SSL certificates and reload nginx

certbot renew --quiet

# Reload nginx in Docker
cd /home/ubuntu/feedfocus
docker-compose restart nginx

# Log the renewal
echo "$(date): SSL certificates renewed" >> /home/ubuntu/ssl-renewal.log
```

**Save and make executable:**

```bash
sudo chmod +x /usr/local/bin/renew-ssl.sh
```

### Add Cron Job

```bash
sudo crontab -e
```

**Add this line** (runs daily at 2 AM, renews if < 30 days left):

```bash
0 2 * * * /usr/local/bin/renew-ssl.sh
```

**Save and exit.**

### Test Renewal (Dry Run)

```bash
sudo certbot renew --dry-run
```

Should show: "Congratulations, all simulated renewals succeeded"

---

## Troubleshooting

### Issue: "Certificate not found"

**Solution:**
```bash
# Verify certificates exist
sudo ls -l /etc/letsencrypt/live/yourdomain.com/

# Should show:
# fullchain.pem
# privkey.pem
```

### Issue: "nginx: configuration file test failed"

**Solution:**
```bash
# Test nginx config
sudo docker-compose exec nginx nginx -t

# Check for typos in domain names
grep "server_name" ~/feedfocus/nginx.conf
```

### Issue: Browser shows "Not Secure"

**Possible causes:**
1. DNS not propagated yet (wait 15 minutes)
2. Wrong domain in nginx.conf (check spelling)
3. Certificate not mounted in Docker (check docker-compose.yml volumes)

**Debug:**
```bash
# Check Docker logs
sudo docker-compose logs nginx

# Verify certificates mounted
sudo docker-compose exec nginx ls -l /etc/letsencrypt/live/
```

### Issue: Mixed content warnings

**Cause:** Frontend making HTTP requests

**Solution:** Ensure API URLs use relative paths:
```javascript
// frontend/src/components/InsightFeed.tsx
const API_URL = import.meta.env.VITE_API_URL || '';  // ← Empty for relative URLs
```

---

## Security Best Practices

### Force HTTPS Everywhere

Already configured in nginx.conf with `return 301 https://...`

### Use HSTS (Recommended)

Add to `nginx.conf` in the `server` block listening on 443:

```nginx
# Add HSTS header
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
```

### Enable Security Headers

Add to `nginx.conf` in HTTPS server block:

```nginx
# Security headers
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "no-referrer-when-downgrade" always;
```

### Update EC2 Security Group

Ensure port 443 is open:

**AWS Console:**
1. EC2 → Security Groups
2. Select your security group
3. **Inbound rules** → Edit
4. Add rule:
   - Type: HTTPS
   - Protocol: TCP
   - Port: 443
   - Source: 0.0.0.0/0

---

## Costs Summary

| Item | Cost | Frequency |
|------|------|-----------|
| Domain registration | $10-15 | Yearly |
| SSL certificate | FREE | Auto-renews |
| EC2 instance | $15-30 | Monthly |
| **Total** | **$10-15 + $15-30/mo** | - |

---

## Quick Reference

### Renew Certificate Manually

```bash
sudo certbot renew
sudo docker-compose restart nginx
```

### Check Certificate Expiry

```bash
sudo certbot certificates
```

### View Nginx Logs

```bash
sudo docker-compose logs -f nginx
```

### Restart After Config Changes

```bash
sudo docker-compose restart nginx
```

---

## Additional Resources

- **Let's Encrypt Documentation:** https://letsencrypt.org/docs/
- **Certbot User Guide:** https://eff-certbot.readthedocs.io/
- **SSL Labs Test:** https://www.ssllabs.com/ssltest/
- **Nginx SSL Configuration:** https://ssl-config.mozilla.org/

---

## Next Steps

After SSL is set up:

1. ✅ Update GitHub Actions workflow with your domain
2. ✅ Set up monitoring (CloudWatch, StatusCake)
3. ✅ Configure daily content refresh cron jobs
4. ✅ Set up database backups
5. ✅ Consider CDN (CloudFront) for better performance

---

**Your site is now live with HTTPS!** 🔒✨

For questions or issues, check the troubleshooting section or open an issue on GitHub.
