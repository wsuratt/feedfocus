# Application Architecture

This document provides an overview of the Insight Feed platform's overall architecture, technology stack, and system design.

## Technology Stack

### Backend
- **Framework**: FastAPI (Python)
- **Python Version**: 3.10+
- **Database**: SQLite (application data)
- **Vector Database**: ChromaDB (insight embeddings)
- **AI Models**:
  - Claude Sonnet 4 (extraction)
  - Llama 3.1 8B (quality evaluation via Groq)
- **Web Scraping**: Crawl4AI
- **Search**: DuckDuckGo API
- **Embeddings**: sentence-transformers (all-MiniLM-L6-v2)

### Frontend
- **Framework**: React 18 + TypeScript
- **Build Tool**: Vite
- **UI Library**: Tailwind CSS
- **Animations**: Framer Motion
- **HTTP Client**: Fetch API
- **Icons**: Lucide React

### Infrastructure
- **Development**: Local development with hot reload
- **Environment Management**: python-dotenv
- **Dependency Management**: pip (Python), npm (JavaScript)

## Application Structure

### Project Organization

```
slm-crawl/
├── automation/          # Core insight pipeline
│   ├── topic_handler.py       # Pipeline orchestrator
│   ├── discover_sources.py    # Source discovery (DuckDuckGo)
│   ├── extraction.py          # Insight extraction (Claude)
│   ├── semantic_db.py         # Vector storage + quality filtering
│   └── content_fetcher.py     # Web scraping (Crawl4AI)
├── backend/            # FastAPI server
│   └── main.py               # API endpoints + feed logic
├── frontend/           # React application
│   └── src/
│       ├── components/       # React components
│       └── App.tsx          # Router + main app
├── db/                # Database
│   ├── schema.sql           # SQLite schema
│   └── init_db.py          # Database initialization
├── tests/             # Testing scripts
│   ├── test_quality.py           # End-to-end pipeline test
│   ├── test_manual_extraction.py # Single URL extraction test
│   └── test_extraction.py        # Extraction logic test
├── docs/              # Documentation
│   ├── README.md           # Documentation index
│   ├── architecture.md      # This file
│   └── api.md              # API documentation
└── chroma_db/         # ChromaDB vector storage
```

### Key Architectural Patterns

#### 1. Pipeline Architecture
The insight generation follows a sequential pipeline:

```python
Topic → Query Generation → Source Discovery → Extraction → Quality Filtering → Vector Storage → Feed API
```

**Pipeline Orchestrator** (`automation/topic_handler.py`):
```python
async def process_topic(user_topic: str) -> dict:
    # 1. Generate search queries
    queries = generate_search_queries(user_topic)

    # 2. Discover sources
    sources = await discover_sources_for_topic(user_topic, queries)

    # 3. Extract insights
    extraction_results = []
    for url in sources:
        result = await extract_from_url(url)
        extraction_results.append(result)

    # 4. Filter & store
    added_ids = add_insights_batch(insights, topic=user_topic)

    return result
```

#### 2. Quality Filtering Architecture
Multi-stage filtering ensures high-quality insights:

**Stage 1: Fast Path (Heuristics)**
- Length check (80-500 chars)
- Must have capitals or numbers
- Instant reject obvious spam
- Instant reject self-promotion

**Stage 2: Slow Path (SLM Evaluation)**
```python
def evaluate_insight_quality_slm(insight_text: str, topic: str) -> dict:
    # Scores 0-10 based on:
    # - Topic relevance (0-3)
    # - Specificity (0-3)
    # - Actionability (0-2)
    # - Credibility (0-2)
    # Threshold: >= 7 to pass
```

**Stage 3: Semantic Deduplication**
- Cosine similarity threshold: 0.87
- Removes near-duplicate insights

#### 3. Vector Database Architecture
ChromaDB stores insight embeddings for semantic search:

```python
# Add insight with embedding
collection.add(
    ids=[insight_id],
    embeddings=[embedding],      # sentence-transformers
    documents=[insight_text],
    metadatas=[{
        'category': 'strategic_insights',
        'topic': 'value investing',
        'source_url': url,
        'quality_score': 85
    }]
)

# Query similar insights
results = collection.query(
    query_texts=[user_interest],
    n_results=20
)
```

#### 4. API-First Feed Design
FastAPI backend serves insights with smart aggregation:

```python
# Group insights by source
source_cards = []
for domain, insights in grouped_by_domain:
    card = {
        'source_domain': domain,
        'source_title': generate_source_title(insights),  # AI-generated
        'insights': insights[:4],  # Max 4 per source
        'total_insights': len(insights)
    }
    source_cards.append(card)
```

## Data Architecture

### Application Database (SQLite)

```sql
-- User interests
CREATE TABLE user_interests (
    id INTEGER PRIMARY KEY,
    topic TEXT NOT NULL,
    created_at TIMESTAMP
);

-- Insight engagement tracking
CREATE TABLE insight_engagement (
    id INTEGER PRIMARY KEY,
    insight_id TEXT,
    action TEXT,  -- 'like' | 'x' | 'bookmark' | 'share'
    created_at TIMESTAMP
);
```

### Vector Database (ChromaDB)

```python
# Collection structure
{
    "name": "insights",
    "metadata": {"description": "Insight vectors for personalized feed"},
    "embeddings": [...],  # 384-dim vectors
    "documents": [...],   # Insight text
    "metadatas": [...]    # Category, topic, source, etc.
}
```

### Data Flow Architecture

```
User Interest
    ↓
Query Generation (Claude)
    ↓
Source Discovery (DuckDuckGo)
    ↓
Content Fetching (Crawl4AI)
    ↓
Insight Extraction (Claude)
    ↓
Quality Filtering (Llama 3.1 via Groq)
    ↓
Semantic Deduplication (ChromaDB)
    ↓
Vector Storage (ChromaDB)
    ↓
Feed API (FastAPI)
    ↓
React Frontend
```

## Insight Extraction Architecture

### Extraction Pipeline

**1. Content Fetching**
```python
# Web pages
content = await fetch_content_sample(url)  # Crawl4AI

# PDFs
content = extract_pdf_text(url)  # PyPDF2
```

**2. Claude Extraction**
```python
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    system="Extract ACTIONABLE INSIGHTS...",
    messages=[{"role": "user", "content": prompt}]
)
```

**3. Insight Categories**
- `strategic_insights` - How companies/people approach problems
- `counterintuitive` - Surprising findings with explanations
- `tactical_playbooks` - Specific frameworks and processes
- `emerging_patterns` - Early signals of change
- `case_studies` - Real examples with numbers

**4. Validation**
- Hallucination removal (verify key terms in source)
- JSON structure validation
- Retry logic for failed extractions

### Source Quality Scoring

**Discovery Phase:**
```python
def calculate_source_quality(url: str, title: str, snippet: str) -> int:
    score = 100  # Start at 100

    # Tier 1 domains (research, gov, top tech): +50
    # Tier 2 domains (established media): +25
    # Banned domains: -1000 (reject)

    # Quality indicators in title/snippet: +10 each
    # - "case study", "research", "data", "analysis"

    # Negative indicators: -20 each
    # - "listicle", "top 10", "you won't believe"

    return score
```

**Extraction Phase:**
```python
def is_extraction_valuable(insights: dict) -> bool:
    # Check for "so what?" indicators:
    # - Arrow notation (→)
    # - Implication words (because, therefore, reveals)
    # - Specificity (numbers, company names)

    valuable_count = sum(1 for insight in insights if has_insight_markers(insight))
    return valuable_count >= 3 or (valuable_count / total) >= 0.6
```

## Query Generation Architecture

### Formula-Based Query Generation

Claude generates queries using a structured formula:

```
Query Formula = [Primary Source Type] + [Topic] + [Specificity]

Examples:
- "Warren Buffett Berkshire Hathaway annual shareholder letters"
- "GitLab remote work case study employee productivity"
- "Sequoia Capital memo market analysis"
```

**Query Categories:**
1. **Primary Sources** - Company letters, memos, research papers
2. **Case Studies** - Real company examples with outcomes
3. **Framework Docs** - Playbooks, methodologies, strategies
4. **Strategic Analysis** - Expert commentary, trend analysis
5. **Data Reports** - Original research, surveys, studies

**Anti-Pattern** (what we avoid):
- Generic "trends in [topic]" queries → Returns SEO listicles
- "Best practices for [topic]" → Returns generic advice
- "[topic] statistics 2024" → Returns bare facts without insights

## Performance Architecture

### Caching Strategy

**LRU Cache for SLM Evaluation:**
```python
@lru_cache(maxsize=2000)
def evaluate_insight_quality_slm(insight_text: str, topic: str) -> dict:
    # Cached to avoid repeated API calls for same insight
    # 90%+ cache hit rate during deduplication
```

**ChromaDB Persistence:**
- Persistent client (not in-memory)
- Automatic embedding caching
- Fast similarity search (<50ms for 1000 insights)

### Background Processing

**Async Pipeline:**
```python
# All I/O operations are async
async def extract_from_url(url: str)
async def discover_sources_for_topic(topic: str, queries: list)
async def process_topic(user_topic: str)
```

**Concurrent Source Processing:**
```python
# Process up to 40 sources in parallel
for url in urls:  # 40 URLs
    result = await extract_from_url(url)  # Concurrent execution
```

### Scalability Considerations

**Current Bottlenecks:**
1. **Extraction**: Claude API rate limits (~50 req/min)
2. **Discovery**: DuckDuckGo rate limits
3. **SQLite**: Single-writer limitation

**Scaling Path:**
1. **Horizontal Scaling**: Queue-based architecture (Celery/Redis)
2. **Database**: Migrate to PostgreSQL for multi-user
3. **Caching**: Add Redis for API response caching
4. **CDN**: Static asset delivery for frontend

## Development Architecture

### Code Organization Principles

#### 1. Separation of Concerns
- **automation/**: Pure Python pipeline logic
- **backend/**: API and feed serving
- **frontend/**: UI and user interaction
- **tests/**: Isolated testing scripts

#### 2. Modular Pipeline
Each stage is independent and testable:
```python
# Can test each stage independently
queries = generate_search_queries(topic)
sources = discover_sources_for_topic(topic, queries)
insights = extract_from_url(url)
filtered = add_insights_batch(insights, topic)
```

#### 3. Type Hints and Documentation
```python
async def extract_from_url(url: str) -> Optional[Dict]:
    """
    Main production extraction function

    Args:
        url: Source URL to extract from

    Returns:
        dict with status, insights, quality_score, etc.
        None if extraction fails
    """
```

### Development Workflow

#### Local Development Setup
```bash
# Install dependencies
pip install -r requirements.txt
cd frontend && npm install

# Set up environment
cp .env.example .env  # Add API keys

# Initialize database
python db/init_db.py

# Start development
python backend/main.py       # Terminal 1
cd frontend && npm run dev   # Terminal 2
```

#### Testing Strategy
```bash
# Test extraction on specific URL
python tests/test_manual_extraction.py "https://example.com" "topic"

# Test full pipeline
python tests/test_quality.py

# Test individual components
python tests/test_extraction.py
```

## Configuration Management

### Environment Configuration
```bash
# .env file
ANTHROPIC_API_KEY=sk-ant-...    # Claude API for extraction
GROQ_API_KEY=gsk_...            # Llama 3.1 for quality evaluation
```

### Source Discovery Configuration

**Tier 1 Domains** (highest quality):
```python
TIER_1_DOMAINS = [
    'gov', 'edu', 'nih.gov', 'arxiv.org',  # Research/gov
    'paulgraham.com', 'a16z.com',           # Expert blogs
    'openai.com', 'anthropic.com'           # Primary sources
]
```

**Banned Domains** (filtered out):
```python
BANNED_DOMAINS = [
    'youtube.com', 'facebook.com',          # Social media
    'forbes.com/sites', 'medium.com',       # Content farms
    'softwareadvice.com', 'g2.com'          # Vendor sites
]
```

### Quality Thresholds

```python
# Source selection
TOP_N_SOURCES = 40           # Select top 40 by quality score
MIN_QUALITY_SCORE = 80       # Minimum score to consider

# Insight filtering
MIN_INSIGHT_LENGTH = 80      # Characters
MAX_INSIGHT_LENGTH = 500
SLM_SCORE_THRESHOLD = 7      # Out of 10

# Deduplication
SIMILARITY_THRESHOLD = 0.87  # Cosine similarity
```

## Security Architecture

### API Keys
- Stored in `.env` (gitignored)
- Loaded via python-dotenv
- Never hardcoded in source

### Data Privacy
- No user authentication (single-user app currently)
- All data stored locally (SQLite + ChromaDB)
- No external tracking or analytics

### Input Validation
```python
# URL validation before fetching
if not url.startswith(('http://', 'https://')):
    return {'status': 'failed', 'error': 'Invalid URL'}

# Topic validation before processing
if not topic or len(topic) < 2:
    return {'status': 'failed', 'error': 'Invalid topic'}
```

## Cost Architecture

### API Costs (Per Topic)

**Discovery Phase** (one-time per topic):
- Claude Sonnet 4 (query generation): $0.01-0.02
- Groq Llama 3.1 (source evaluation): $0.001
- **Total**: ~$0.01-0.02

**Extraction Phase** (per run):
- Claude Sonnet 4 (40 sources × extraction): $0.40-0.80
- Groq Llama 3.1 (quality filtering): $0.01
- **Total**: ~$0.41-0.81 per topic

**Monthly Cost Estimate** (5 topics, daily refresh):
- Discovery: $0.05-0.10 (one-time)
- Daily extraction: $2.05-4.05 × 30 = $61.50-121.50/month

**Cost Optimization Strategies:**
1. Cache Claude extractions (don't re-extract same URL)
2. Use Groq for more tasks (much cheaper than Claude)
3. Reduce extraction frequency (weekly vs daily)
4. Implement smart refresh (only new sources)

## Monitoring and Observability

### Logging Strategy

```python
# Detailed pipeline logging
print(f"  1/4 Generating search queries...")
print(f"  2/4 Discovering sources ({len(queries)} queries)...")
print(f"  3/4 Extracting insights from {len(urls)} sources...")
print(f"    ✓ {url[:60]}... ({insight_count} insights)")
print(f"    ✗ {url[:60]}... (extraction failed)")
print(f"  4/4 Importing to vector DB...")
print(f"  ✅ Added {len(inserted_ids)}/{len(insights)} insights to DB")
```

### Debug Output

```python
# Quality filtering debug
print(f"    [DEBUG] Insight {i+1}/{len(insights)}: {text[:100]}...")
print(f"    [DEBUG]   → PASSED quality filter")
print(f"    [DEBUG]   → REJECTED by quality filter")
print(f"  ❌ Filtered (score {result['score']}): {insight_text[:60]}...")
print(f"     Reason: {result['reason']}")
```

### Performance Metrics

```python
# Pipeline timing
duration = (datetime.now() - start_time).total_seconds()
print(f"    Duration: {duration:.1f}s")

# Success rates
success_rate = (successful / len(urls) * 100)
print(f"    [DEBUG] Extraction: {successful} succeeded, {failed} failed ({success_rate:.0f}% success rate)")
```

## Related Documentation

- [API Reference](api.md) - HTTP endpoints and request/response formats
- [Testing Guide](../tests/README.md) - How to run tests and debug issues
- [Project README](../README.md) - Quick start and usage guide

## Key Files Reference

### Core Pipeline
- `automation/topic_handler.py` - Pipeline orchestrator (400 lines)
- `automation/extraction.py` - Claude-based extraction (400 lines)
- `automation/semantic_db.py` - Vector storage + filtering (500 lines)
- `automation/discover_sources.py` - DuckDuckGo search (300 lines)

### API Layer
- `backend/main.py` - FastAPI server + feed logic (400 lines)

### Database
- `db/schema.sql` - SQLite schema definition
- `db/init_db.py` - Database initialization script

### Configuration
- `.env` - API keys and secrets (gitignored)
- `requirements.txt` - Python dependencies
- `frontend/package.json` - JavaScript dependencies

---

**Last Updated**: November 2024
**Version**: 1.0
