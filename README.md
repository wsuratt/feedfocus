# FeedFocus

A personalized insight feed platform with ML-powered recommendations. Discover content from topics you follow through a unified feed interface.

## Overview

FeedFocus provides a unified feed experience with two modes:
- **For You**: ML-scored personalized recommendations
- **Following**: Latest insights from topics you follow

Users can follow topics, engage with insights (like, save, dismiss), and the system learns from engagement to improve recommendations.

## Features

- **Topic-Based**: Follow topics you care about (AI, startups, investing, etc.)
- **Unified Feed**: Two-tab interface with For You and Following feeds
- **Engagement Tracking**: Like, save, and dismiss insights
- **Personalized**: ML-based scoring and ranking
- **Cross-Platform**: Web and mobile (React Native) applications

## Quick Start

### 1. Install Dependencies

**Backend:**
```bash
pip install -r requirements.txt
```

**Frontend:**
```bash
cd frontend
npm install
cd ..
```

### 2. Set Environment Variables

Copy the example environment file and add your API keys:
```bash
cp .env.example .env
# Edit .env and add your API keys
```

Get your API keys:
- **Anthropic**: https://console.anthropic.com/ (required for extraction)
- **Groq**: https://console.groq.com/keys (required for quality evaluation)

**Optional: Configure filtering**
- `ENABLE_POST_COLLECTION_FILTER=true` - Apply final quality filters to feed (default)
- `ENABLE_POST_COLLECTION_FILTER=false` - Show all insights that passed initial quality checks

### 3. Initialize Database

```bash
python db/init_db.py
```

### 4. Start the Application

**Terminal 1 - Backend:**
```bash
cd backend
python main.py
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

Visit **http://localhost:3000**

## How to Use

### Step 1: Add Your Interests

1. Visit http://localhost:3000/interests
2. Add 1+ topics you're curious about:
   - "AI agents & automation"
   - "Startup ideas & trends"
   - "Value investing"
   - "Design trends"
   - etc.

### Step 2: Generate Your Feed

```bash
# In a new terminal
python api/feed_generator.py
```

This will:
- Create AI agents for each interest
- Discover high-quality sources
- Evaluate and extract insights
- Populate your personalized feed queue

**Note**: First run takes 5-10 minutes as it creates agents and discovers sources.

### Step 3: Browse Insights

1. Visit http://localhost:3000
2. Browse through insights
3. Like insights that resonate
4. Bookmark to save for later
5. Dismiss insights you're not interested in

Your engagement helps the feed learn what you find valuable.

## Project Structure

```
slm-crawl/
├── automation/          # Core insight pipeline
│   ├── topic_handler.py       # Pipeline orchestrator
│   ├── discover_sources.py    # Source discovery
│   ├── extraction.py          # Insight extraction (Claude)
│   ├── semantic_db.py         # Vector storage + filtering
│   └── content_fetcher.py     # Web scraping
├── backend/
│   └── main.py                 # FastAPI server (feed endpoints)
├── frontend/
│   └── src/
│       ├── components/
│       │   └── InsightFeed.tsx      # Main feed UI
│       └── App.tsx             # React router
├── db/
│   ├── schema.sql              # Database schema
│   └── init_db.py              # Database initialization
├── tests/               # Testing scripts
│   ├── test_quality.py         # End-to-end pipeline test
│   └── test_manual_extraction.py  # Debug specific URLs
├── training_data/       # Training data collection
│   ├── extraction_logs.jsonl   # LLM inputs/outputs
│   ├── feedback_logs.jsonl     # User engagement
│   └── view_training_data.py   # View/export data
├── docs/                # Documentation
│   ├── README.md               # Documentation index
│   ├── architecture.md         # System design
│   └── api.md                  # API reference
├── insights.db                 # SQLite database
├── chroma_db/                  # ChromaDB vector storage
├── requirements.txt            # Python dependencies
└── .env                        # API keys (create this)
```

## Database Schema

### Key Tables

- **`user_interests`** - Topics you care about
- **`agents`** - AI agents for each interest
- **`agent_configs`** - Claude-generated search & extraction configs
- **`insights_v2`** - Discovered insights with dynamic schemas
- **`feed_queue`** - Pre-scored insights ready to show
- **`insight_engagement`** - Your likes/bookmarks/dismissals

## How It Works

```
1. You add interests
   ↓
2. Feed generator creates agents
   ↓
3. Agents discover sources (DuckDuckGo)
   ↓
4. Evaluate quality (Groq SLM)
   ↓
5. Extract insights (custom schema per agent)
   ↓
6. Score relevance to your interests
   ↓
7. Add to feed queue
   ↓
8. You swipe through in the app
```

## API Endpoints

### Interests
- `GET /api/interests` - Get user's interests
- `POST /api/interests` - Add new interest
- `DELETE /api/interests/{id}` - Remove interest

### Feed
- `GET /api/feed` - Get personalized insights (20 at a time)
- `POST /api/feed/engage` - Record engagement (like/x/bookmark/share)

### Stats
- `GET /api/stats` - Feed statistics

## Configuration

### Default Topics with Examples

The feed generator includes default example sources for common topics:

- **AI/Tech**: Anthropic blog, Simon Willison, One Useful Thing
- **Startups**: Hacker News, Indie Hackers, SaaStr
- **Investing**: Berkshire letters, Investopedia, Motley Fool

For other topics, agents use general tech/business sources. You can customize this in `api/feed_generator.py`.

### Running Agents Regularly

To keep your feed fresh, run the feed generator daily:

**Option 1: Cron Job (Mac/Linux)**
```bash
# Edit crontab
crontab -e

# Add line to run daily at 9 AM
0 9 * * * cd /path/to/slm-crawl && python api/feed_generator.py
```

**Option 2: Manual**
```bash
python api/feed_generator.py
```

## Cost Estimate

**Per Agent Creation (one-time):**
- Claude Sonnet 4: ~$0.02-0.05 per agent
- Groq (quality evaluation): ~$0.001

**Per Daily Run:**
- Groq for discovery/extraction: ~$0.01-0.05 per agent
- Almost entirely free with Groq's generous limits

**Example:** 5 interests = ~$0.10 one-time + ~$0.05/day ongoing

## Troubleshooting

### "No insights yet" even after running feed generator

**Check:**
1. Did feed generator complete successfully?
2. Are there insights in database?
   ```bash
   sqlite3 insights.db "SELECT COUNT(*) FROM insights_v2;"
   ```
3. Are they in feed queue?
   ```bash
   sqlite3 insights.db "SELECT COUNT(*) FROM feed_queue WHERE shown = 0;"
   ```

### Feed generator fails with Claude API error

**Solutions:**
- Verify `ANTHROPIC_API_KEY` is set in `.env`
- Check you're on a paid Anthropic plan (free tier very limited)
- Reduce number of interests or run one at a time

### Feed generator hangs on discovery

**Solutions:**
- DuckDuckGo might be rate-limiting
- Wait a few minutes between runs
- Reduce `max_to_evaluate` in `agent_runner.py`

### Frontend shows "Failed to load feed"

**Check:**
- Backend is running on port 8000
- CORS is enabled (already configured)
- No console errors in browser DevTools

## Development

### Reset Database
```bash
rm insights.db
python db/init_db.py
```

### View Database
```bash
sqlite3 insights.db
.tables
SELECT * FROM user_interests;
SELECT * FROM feed_queue LIMIT 5;
```

### Test API
```bash
# Check backend health
curl http://localhost:8000/

# Get feed
curl http://localhost:8000/api/feed?limit=5
```

## Documentation

See the [`docs/`](docs/) folder for comprehensive documentation:
- [Documentation Index](docs/README.md) - Complete documentation navigation
- [Architecture](docs/architecture/) - System design and patterns
- [API Reference](docs/architecture/api-endpoints.md) - API documentation
- [Testing Guide](tests/README.md) - How to run tests

## Future Enhancements

- [ ] Better recommendation algorithm (collaborative filtering)
- [ ] Social features (share insights, follow interests)
- [ ] Bookmarks page
- [ ] Daily digest emails
- [ ] Mobile app (React Native)
- [ ] Multiple feed modes (trending, deep, contrarian)

## Tech Stack

- **Backend**: FastAPI (Python)
- **Frontend**: React + TypeScript + Vite
- **Database**: SQLite
- **AI**: Claude Sonnet 4 (config generation), Groq Llama 3.1 (discovery/extraction)
- **Search**: DuckDuckGo
- **Crawling**: Crawl4AI
- **Animations**: Framer Motion

## Credits

Built with:
- **Anthropic Claude** - Smart agent configuration
- **Groq** - Fast, affordable inference
- **Crawl4AI** - Clean web content extraction
- **Framer Motion** - Smooth swipe animations

## License

MIT

---

For comprehensive documentation, see [`docs/`](docs/).
