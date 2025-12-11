# API Reference

This document provides detailed reference for all API endpoints exposed by the Insight Feed backend.

## Base URL

```
http://localhost:8000
```

All endpoints are prefixed with `/api/` except for health check.

## Authentication

**Current Version**: No authentication required (single-user app)

**Future**: Will add JWT-based authentication for multi-user support.

---

## Endpoints

### Health Check

#### `GET /`

Check if the backend server is running.

**Response**
```json
{
  "status": "ok",
  "message": "Insight Feed API"
}
```

**Example**
```bash
curl http://localhost:8000/
```

---

## Interests Management

### Get All Interests

#### `GET /api/interests`

Retrieve all user interests.

**Response**
```json
[
  {
    "id": 1,
    "topic": "value investing",
    "created_at": "2024-11-20T13:45:00"
  },
  {
    "id": 2,
    "topic": "AI agents",
    "created_at": "2024-11-20T14:30:00"
  }
]
```

**Example**
```bash
curl http://localhost:8000/api/interests
```

---

### Add Interest

#### `POST /api/interests`

Add a new user interest.

**Request Body**
```json
{
  "topic": "startup fundraising"
}
```

**Response**
```json
{
  "id": 3,
  "status": "added"
}
```

**Validation**
- `topic` must be a non-empty string
- Duplicate topics are allowed (no uniqueness constraint)

**Example**
```bash
curl -X POST http://localhost:8000/api/interests \
  -H "Content-Type: application/json" \
  -d '{"topic": "startup fundraising"}'
```

---

### Delete Interest

#### `DELETE /api/interests/{id}`

Remove a user interest.

**Path Parameters**
- `id` (integer) - Interest ID to delete

**Response**
```json
{
  "status": "deleted"
}
```

**Example**
```bash
curl -X DELETE http://localhost:8000/api/interests/3
```

---

## Feed

### Get Feed

#### `GET /api/feed`

Get personalized insights grouped by source.

**Query Parameters**
- `limit` (integer, optional) - Number of insights to return (default: 20)

**Response**
```json
[
  {
    "source_domain": "berkshirehathaway.com",
    "source_title": "Berkshire Hathaway: Warren Buffett's Investment Philosophy",
    "insights": [
      {
        "id": "abc123...",
        "text": "Buffett's Japanese trading house strategy involves buying stable businesses at 8-10x earnings while US equivalents trade at 20x - exploiting systematic undervaluation where these companies generate 15%+ ROE but trade below book value",
        "category": "📋 Tactical Playbook",
        "topic": "value investing",
        "source_url": "https://berkshirehathaway.com/letters/2023ltr.pdf",
        "quality_score": 95,
        "created_at": "2024-11-20T10:30:00"
      },
      {
        "id": "def456...",
        "text": "Berkshire maintains $150B+ cash reserves not as caution but because finding businesses that meet their quality bar at reasonable prices has become increasingly difficult as markets have become more efficient",
        "category": "💡 Strategic Insight",
        "topic": "value investing",
        "source_url": "https://berkshirehathaway.com/letters/2023ltr.pdf",
        "quality_score": 92,
        "created_at": "2024-11-20T10:30:00"
      }
    ],
    "total_insights": 6
  },
  {
    "source_domain": "valuewalk.com",
    "source_title": "Joel Greenblatt's Magic Formula Performance",
    "insights": [
      {
        "id": "ghi789...",
        "text": "Greenblatt's Magic Formula (low P/E + high ROIC) generated 30.8% annual returns vs 12.4% S&P 500 over 17 years, but required holding positions for 12+ months despite underperforming in 5 of those years - most investors abandoned it during drawdowns",
        "category": "📊 Case Study",
        "topic": "value investing",
        "source_url": "https://valuewalk.com/magic-formula-returns/",
        "quality_score": 88,
        "created_at": "2024-11-20T11:15:00"
      }
    ],
    "total_insights": 3
  }
]
```

**Response Fields**

**SourceCard:**
- `source_domain` (string) - Domain name of the source
- `source_title` (string) - AI-generated descriptive title
- `insights` (array) - Array of insight objects (max 4 per source)
- `total_insights` (integer) - Total insights available from this source

**Insight:**
- `id` (string) - Unique insight ID (hash of content)
- `text` (string) - The insight content (80-500 characters)
- `category` (string) - Insight category with emoji
  - `💡 Strategic Insight`
  - `🔄 Counterintuitive`
  - `📋 Tactical Playbook`
  - `⚡ Emerging Pattern`
  - `📊 Case Study`
- `topic` (string) - Associated user interest
- `source_url` (string) - Original source URL
- `quality_score` (integer) - Quality score 0-100
- `created_at` (string) - ISO 8601 timestamp

**Notes**
- Insights are grouped by source domain
- Max 4 insights shown per source
- Sources sorted by avg quality score
- Post-collection filtering applied (removes promotional/vague insights)

**Example**
```bash
# Get default feed (20 insights)
curl http://localhost:8000/api/feed

# Get more insights
curl "http://localhost:8000/api/feed?limit=50"
```

---

### Record Engagement

#### `POST /api/feed/engage`

Record user engagement with an insight (like, bookmark, x).

**Request Body**
```json
{
  "insight_id": "abc123...",
  "action": "like"
}
```

**Request Fields**
- `insight_id` (string, required) - Insight ID from feed
- `action` (string, required) - One of: `"like"`, `"x"`, `"bookmark"`, `"share"`

**Response**
```json
{
  "status": "recorded"
}
```

**Notes**
- Used for future recommendation improvements
- Currently only tracked, not used for filtering

**Example**
```bash
curl -X POST http://localhost:8000/api/feed/engage \
  -H "Content-Type: application/json" \
  -d '{
    "insight_id": "abc123...",
    "action": "like"
  }'
```

---

## Statistics

### Get Stats

#### `GET /api/stats`

Get database and feed statistics.

**Response**
```json
{
  "total_insights": 156,
  "total_interests": 3,
  "insights_by_topic": {
    "value investing": 68,
    "AI agents": 52,
    "startup fundraising": 36
  }
}
```

**Response Fields**
- `total_insights` (integer) - Total insights in database
- `total_interests` (integer) - Number of user interests
- `insights_by_topic` (object) - Breakdown by topic

**Example**
```bash
curl http://localhost:8000/api/stats
```

---

## Error Responses

All endpoints may return error responses in this format:

### 400 Bad Request
```json
{
  "detail": "Invalid request: topic is required"
}
```

### 404 Not Found
```json
{
  "detail": "Interest not found"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Database error: ..."
}
```

---

## Data Models

### Pydantic Models

#### Interest
```python
class Interest(BaseModel):
    topic: str  # User interest topic
```

#### EngagementAction
```python
class EngagementAction(BaseModel):
    insight_id: str     # Unique insight ID
    action: str         # 'like' | 'x' | 'bookmark' | 'share'
```

#### SourceCard
```python
class SourceCard(BaseModel):
    source_domain: str           # e.g., "berkshirehathaway.com"
    source_title: str            # AI-generated title
    insights: List[Dict]         # Array of insight objects
    total_insights: int          # Total from this source
```

---

## CORS Configuration

CORS is enabled for local development:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Allowed Origins:**
- `http://localhost:3000` - React dev server (Create React App)
- `http://localhost:5173` - Vite dev server

---

## Rate Limiting

**Current**: No rate limiting

**Future**: Will add rate limiting for API abuse prevention
- 100 requests per minute per IP
- 1000 requests per hour per IP

---

## Caching

**Current**: No HTTP caching headers

**Future**: Will add caching for feed endpoint
- `Cache-Control: max-age=300` (5 minutes)
- `ETag` support for conditional requests

---

## Content Negotiation

All endpoints return `application/json` responses.

**Request Headers:**
- `Content-Type: application/json` (for POST requests)
- `Accept: application/json` (optional)

---

## Database Schema

### Tables Used by API

#### `user_interests`
```sql
CREATE TABLE user_interests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### `insight_engagement`
```sql
CREATE TABLE insight_engagement (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    insight_id TEXT NOT NULL,
    action TEXT NOT NULL,  -- 'like' | 'x' | 'bookmark' | 'share'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Note**: Insights are stored in ChromaDB (vector database), not SQLite.

---

## API Client Examples

### JavaScript (Fetch)

```javascript
// Get feed
const feed = await fetch('http://localhost:8000/api/feed?limit=20')
  .then(res => res.json());

// Add interest
await fetch('http://localhost:8000/api/interests', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ topic: 'value investing' })
});

// Record engagement
await fetch('http://localhost:8000/api/feed/engage', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    insight_id: 'abc123',
    action: 'like'
  })
});
```

### Python (requests)

```python
import requests

BASE_URL = "http://localhost:8000"

# Get feed
response = requests.get(f"{BASE_URL}/api/feed", params={"limit": 20})
feed = response.json()

# Add interest
response = requests.post(
    f"{BASE_URL}/api/interests",
    json={"topic": "value investing"}
)
result = response.json()

# Record engagement
response = requests.post(
    f"{BASE_URL}/api/feed/engage",
    json={
        "insight_id": "abc123",
        "action": "like"
    }
)
```

### cURL

```bash
# Get feed
curl http://localhost:8000/api/feed?limit=20

# Add interest
curl -X POST http://localhost:8000/api/interests \
  -H "Content-Type: application/json" \
  -d '{"topic": "value investing"}'

# Record engagement
curl -X POST http://localhost:8000/api/feed/engage \
  -H "Content-Type: application/json" \
  -d '{"insight_id": "abc123", "action": "like"}'

# Get stats
curl http://localhost:8000/api/stats
```

---

## Testing

### Manual API Testing

1. **Start backend**
```bash
cd backend
python main.py
```

2. **Test health check**
```bash
curl http://localhost:8000/
```

3. **Add test interest**
```bash
curl -X POST http://localhost:8000/api/interests \
  -H "Content-Type: application/json" \
  -d '{"topic": "test topic"}'
```

4. **Check feed** (will be empty until insights are generated)
```bash
curl http://localhost:8000/api/feed
```

### Automated Testing

See [Testing Guide](../tests/README.md) for automated test scripts.

---

## Future API Enhancements

### Planned v2 Endpoints

#### User Authentication
```
POST /api/auth/register
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/me
```

#### Bookmarks
```
GET    /api/bookmarks
POST   /api/bookmarks
DELETE /api/bookmarks/{id}
```

#### Feed Personalization
```
GET  /api/feed/trending      # Most-liked insights
GET  /api/feed/recent        # Newest insights
GET  /api/feed/deep          # Long-form insights
POST /api/feed/refresh       # Trigger new insight generation
```

#### Analytics
```
GET /api/analytics/engagement  # User engagement metrics
GET /api/analytics/topics      # Topic popularity
GET /api/analytics/sources     # Source quality stats
```

---

## Related Documentation

- [Architecture](architecture.md) - System design and data flow
- [Testing Guide](../tests/README.md) - How to test the API
- [Project README](../README.md) - Setup and usage

---

**Last Updated**: November 2024
**API Version**: 1.0
