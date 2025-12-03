# Requirements Files Guide

## 📦 File Structure

### `requirements-backend.txt` (Lightweight - ~500MB)
**Use for:** Docker backend API server

**Includes:**
- FastAPI, Uvicorn (API server)
- ChromaDB, sentence-transformers (vector search)
- Groq (SLM API)
- Python-jose (JWT auth)

**Does NOT include:**
- crawl4ai (huge web scraping dependencies)
- anthropic (Claude API - not needed for runtime)
- ddgs (DuckDuckGo search)
- PyPDF2

---

### `requirements-automation.txt` (Full - ~2GB+)
**Use for:** Running automation scripts locally

**Includes:**
- All backend requirements
- crawl4ai (web scraping)
- anthropic (Claude API)
- ddgs (search)
- PyPDF2 (PDF processing)

---

## 🚀 Usage

### Docker Backend (Production)
```bash
# Dockerfile uses requirements-backend.txt automatically
docker-compose build backend
```

### Local Development (Automation Scripts)
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install full automation dependencies
pip install -r requirements-automation.txt

# Run automation scripts
python automation/collector.py
```

### Server-side Automation (Cron Job)
```bash
# On your server, install automation requirements separately
pip install -r requirements-automation.txt

# Run via cron
0 */6 * * * cd /home/ubuntu/feedfocus && python automation/collector.py
```

---

## 💾 Disk Space Comparison

| Requirements File | Docker Image Size | Disk Usage |
|------------------|------------------|------------|
| requirements-backend.txt | ~800MB | Minimal |
| requirements-automation.txt | ~2.5GB | Heavy |

**Splitting saves ~1.7GB on Docker image!** 🎉
