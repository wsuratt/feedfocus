# Deployment Guide

This guide covers deploying the Insight Feed application to production.

## Prerequisites

- ✅ API keys for Anthropic and Groq
- ✅ Domain name (optional, but recommended)
- ✅ Git repository (GitHub recommended)

---

## Option 1: Railway (Recommended - Easiest)

**Best for:** Quick deployment, automatic scaling, PostgreSQL support

### Steps:

1. **Create Railway account**: https://railway.app
2. **Install Railway CLI**:
   ```bash
   npm install -g @railway/cli
   railway login
   ```

3. **Deploy from root directory**:
   ```bash
   cd /Users/williamsuratt/Documents/slm-crawl
   railway init
   railway up
   ```

4. **Set environment variables** in Railway dashboard:
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   GROQ_API_KEY=gsk_...
   ENABLE_POST_COLLECTION_FILTER=true
   ```

5. **Deploy frontend separately** or use Railway's Nixpacks auto-detection

**Cost:** Free tier includes 500 hours/month, $5/month for more

---

## Option 2: Render.com (Great for Full-Stack Apps)

**Best for:** Free tier, easy setup, supports SQLite

### Steps:

1. **Create account**: https://render.com

2. **Push code to GitHub** (if not already):
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin <your-github-repo>
   git push -u origin main
   ```

3. **Create Web Service**:
   - Connect GitHub repo
   - Build command: `pip install -r requirements.txt`
   - Start command: `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`
   - Environment: Python 3.11

4. **Add environment variables**:
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   GROQ_API_KEY=gsk_...
   ENABLE_POST_COLLECTION_FILTER=true
   ```

5. **Deploy frontend** as Static Site:
   - Build command: `cd frontend && npm install && npm run build`
   - Publish directory: `frontend/dist`

**Cost:** Free tier available, $7/month for paid

---

## Option 3: Vercel + Render (Best UX)

**Best for:** Blazing-fast frontend, serverless edge

### Frontend (Vercel):

1. **Install Vercel CLI**:
   ```bash
   npm install -g vercel
   ```

2. **Deploy frontend**:
   ```bash
   cd frontend
   vercel
   ```

3. **Update API URL** in `frontend/src/components/InsightFeed.tsx`:
   ```typescript
   const API_URL = process.env.VITE_API_URL || 'http://localhost:8000';
   // Change all fetch calls to use API_URL
   ```

### Backend (Render):
- Follow Render.com steps above

**Cost:** Free for both

---

## Option 4: DigitalOcean App Platform

**Best for:** Production-grade deployment, full control

### Steps:

1. **Create account**: https://cloud.digitalocean.com

2. **Create new app** from GitHub repo

3. **Configure services**:
   
   **Backend:**
   ```yaml
   Name: insight-feed-backend
   Type: Web Service
   Build Command: pip install -r requirements.txt
   Run Command: cd backend && uvicorn main:app --host 0.0.0.0 --port 8080
   Port: 8080
   ```
   
   **Frontend:**
   ```yaml
   Name: insight-feed-frontend
   Type: Static Site
   Build Command: cd frontend && npm install && npm run build
   Output Directory: frontend/dist
   ```

4. **Add environment variables**

**Cost:** $5/month minimum

---

## Option 5: Self-Hosted (VPS)

**Best for:** Full control, lowest cost at scale

### Requirements:
- Ubuntu 22.04 VPS (DigitalOcean, Linode, AWS EC2)
- Domain name + SSL certificate

### Setup:

1. **Install dependencies**:
   ```bash
   ssh user@your-server
   sudo apt update
   sudo apt install python3-pip nodejs npm nginx certbot
   ```

2. **Clone repo**:
   ```bash
   git clone <your-repo>
   cd slm-crawl
   ```

3. **Setup backend**:
   ```bash
   pip3 install -r requirements.txt
   cp .env.example .env
   # Edit .env with your keys
   
   # Install PM2 to keep backend running
   sudo npm install -g pm2
   cd backend
   pm2 start "uvicorn main:app --host 0.0.0.0 --port 8000" --name insight-feed
   pm2 save
   pm2 startup
   ```

4. **Build frontend**:
   ```bash
   cd ../frontend
   npm install
   npm run build
   ```

5. **Configure Nginx**:
   ```bash
   sudo nano /etc/nginx/sites-available/insight-feed
   ```
   
   ```nginx
   server {
       listen 80;
       server_name yourdomain.com;
       
       # Frontend
       location / {
           root /home/user/slm-crawl/frontend/dist;
           try_files $uri $uri/ /index.html;
       }
       
       # Backend API
       location /api {
           proxy_pass http://localhost:8000;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection 'upgrade';
           proxy_set_header Host $host;
           proxy_cache_bypass $http_upgrade;
       }
   }
   ```
   
   ```bash
   sudo ln -s /etc/nginx/sites-available/insight-feed /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl reload nginx
   ```

6. **Add SSL**:
   ```bash
   sudo certbot --nginx -d yourdomain.com
   ```

**Cost:** $4-6/month for VPS

---

## Quick Start (Railway - Recommended)

**Fastest way to deploy in 5 minutes:**

```bash
# 1. Install Railway CLI
npm install -g @railway/cli

# 2. Login
railway login

# 3. Initialize project
cd /Users/williamsuratt/Documents/slm-crawl
railway init

# 4. Deploy
railway up

# 5. Set environment variables (in Railway dashboard)
# - ANTHROPIC_API_KEY
# - GROQ_API_KEY
# - ENABLE_POST_COLLECTION_FILTER=true

# 6. Get your URL
railway open
```

**Done!** Your app is live 🎉

---

## Post-Deployment Checklist

- [ ] Set environment variables
- [ ] Run database initialization: `python db/init_db.py`
- [ ] Test API: `curl https://your-app.com/`
- [ ] Test frontend: Visit your domain
- [ ] Add first interest and verify feed works
- [ ] Check training data logs are being created
- [ ] Setup monitoring (Railway/Render have built-in)
- [ ] Add custom domain (optional)

---

## Environment Variables

Required:
```bash
ANTHROPIC_API_KEY=sk-ant-...        # Required for extraction
GROQ_API_KEY=gsk_...                # Required for quality filtering
```

Optional:
```bash
ENABLE_POST_COLLECTION_FILTER=true  # Enable final quality filters (default: true)
PORT=8000                            # Backend port (default: 8000)
```

---

## Troubleshooting

### Database not found
```bash
# Initialize database first
python db/init_db.py
```

### CORS errors
Add your frontend domain to CORS origins in `backend/main.py`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-frontend-domain.com"],
    # ...
)
```

### API calls failing
Check that frontend API URL matches your backend:
```typescript
// frontend/src/components/InsightFeed.tsx
const API_URL = 'https://your-backend.railway.app';
```

### ChromaDB issues on serverless
ChromaDB requires persistent storage. Use Railway or DigitalOcean, not Vercel/Netlify for backend.

---

## Monitoring

**Railway/Render include:**
- Automatic logs
- Metrics dashboard
- Alerts

**For self-hosted:**
```bash
# View backend logs
pm2 logs insight-feed

# View Nginx logs
sudo tail -f /var/log/nginx/access.log
```

---

## Scaling

### Current limits:
- SQLite: ~100K requests/day
- ChromaDB: ~10K insights
- FastAPI: ~1K concurrent users

### When to scale:
- Move to PostgreSQL (Railway provides this)
- Add Redis for caching
- Use separate vector DB (Pinecone, Weaviate)
- Split backend into microservices

---

## Recommended: Railway Deployment

Railway is the easiest option and has everything you need:
- ✅ Auto-deployments from Git
- ✅ Environment variables
- ✅ Persistent storage for SQLite/ChromaDB
- ✅ Free $5/month credit
- ✅ Custom domains
- ✅ Built-in monitoring

**Deploy now:**
```bash
npm install -g @railway/cli
railway login
cd /Users/williamsuratt/Documents/slm-crawl
railway up
```

Your app will be live in < 5 minutes! 🚀
