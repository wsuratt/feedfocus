# ChromaDB → SQLite Migration Guide

## Overview

Your 1830 insights are currently in ChromaDB. We're migrating them to SQLite for the unified feed while **keeping ChromaDB for deduplication**.

## Strategy

```
┌─────────────────────────────────────────────────────┐
│  OLD: ChromaDB only                                 │
│  • All insights in vector DB                        │
│  • Semantic search for feed                         │
│  • Slow filtering/ranking                           │
└─────────────────────────────────────────────────────┘
                      ↓ MIGRATE
┌─────────────────────────────────────────────────────┐
│  NEW: Hybrid approach                               │
│  • ChromaDB: Dedup during extraction only           │
│  • SQLite: Feed queries, filtering, ranking         │
│  • Fast, structured queries                         │
└─────────────────────────────────────────────────────┘
```

## Why This Works Better

**ChromaDB (Vector DB):**
- ✅ Great for: Semantic similarity, deduplication
- ❌ Bad for: Complex filtering, user-specific queries, ranking

**SQLite (Relational DB):**
- ✅ Great for: Structured queries, filtering, user data, fast lookups
- ❌ Bad for: Semantic similarity

**Solution: Use both!**
- ChromaDB: Check if insight already exists (dedup)
- SQLite: Store insights for feed queries

---

## Deployment Steps

### 1. Commit and Push Changes

```bash
# LOCAL
cd /Users/williamsuratt/Documents/feedfocus-dev/feedfocus

git add .
git commit -m "feat: Add ChromaDB → SQLite migration for unified feed"
git push origin main
```

### 2. Pull on Server

```bash
# SERVER
ssh ubuntu@3.17.64.149
cd /home/ubuntu/feedfocus
git pull origin main
```

### 3. Run Schema Migration

```bash
# Still on server
python3 db/migrations/migrate_to_unified_feed.py
```

This creates the new tables (insights, user_topics, user_engagement, etc.)

### 4. Run ChromaDB Migration

```bash
# Still on server
python3 db/migrations/migrate_chromadb_to_unified.py
```

This will:
- Export all 1830 insights from ChromaDB
- Import them into SQLite `insights` table
- Create topic metadata
- Migrate user topic follows
- Keep ChromaDB intact for future dedup

**Expected output:**
```
🚀 Starting ChromaDB → SQLite migration...
📁 ChromaDB: /home/ubuntu/feedfocus/chroma_db
📁 SQLite: /home/ubuntu/feedfocus/insights.db

🔗 Connecting to ChromaDB...
✅ Found 1830 insights in ChromaDB

📥 Fetching insights from ChromaDB...
✅ Fetched 1830 insights

📦 Migrating insights...
  Progress: 100/1830 (5.5%)
  Progress: 200/1830 (10.9%)
  ...
✅ Migrated 1830 insights (0 skipped)

📚 Creating topic metadata...
✅ Created metadata for X topics

============================================================
MIGRATION SUMMARY
============================================================
📦 Insights migrated: 1830
📚 Topics found: X
```

### 5. Restart Backend

```bash
# Still on server
sudo systemctl restart feedfocus-backend
sudo systemctl status feedfocus-backend
```

### 6. Test New Endpoints

```bash
# From your local machine
curl https://api.feed-focus.com/api/feed/following?user_id=default&limit=5

# Should return insights with new structure
```

---

## Database Schema After Migration

### SQLite Tables

```sql
-- Global insights pool (1830 rows after migration)
insights (
    id,              -- UUID
    topic,           -- e.g., "AI agents"
    category,        -- CASE STUDY, PLAYBOOK, etc.
    text,            -- Insight text
    source_url,
    source_domain,
    quality_score,
    engagement_score,
    created_at,
    chroma_id        -- Reference to ChromaDB for dedup
)

-- User follows (from old user_interests)
user_topics (
    user_id,         -- "default"
    topic,           -- "AI agents"
    followed_at
)

-- Engagement tracking
user_engagement (
    user_id,
    insight_id,
    action,          -- view, like, save, dismiss
    created_at
)
```

### ChromaDB Collection

```python
# STILL USED - Don't delete!
collection: "insights"
- 1830 documents
- Used ONLY for dedup check
```

---

## Future Extraction Flow

When new insights are extracted:

```python
# 1. Check ChromaDB for dedup (existing flow)
if insight already in ChromaDB:
    skip

# 2. Add to ChromaDB (existing flow)
chroma_collection.add(insight)
chroma_id = insight.id

# 3. NEW: Also add to SQLite
db.execute("""
    INSERT INTO insights (
        id, topic, category, text, source_url, source_domain,
        quality_score, engagement_score, created_at, chroma_id
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (uuid4(), topic, category, text, url, domain, 0.5, 0.0, now(), chroma_id))
```

---

## Verification Checklist

After migration, verify:

### SQLite
```bash
ssh ubuntu@3.17.64.149
sqlite3 /home/ubuntu/feedfocus/insights.db

-- Check insights
SELECT COUNT(*) FROM insights;
-- Should return: 1830

-- Check topics
SELECT topic, COUNT(*) as count 
FROM insights 
GROUP BY topic 
ORDER BY count DESC 
LIMIT 10;

-- Check user topics
SELECT * FROM user_topics;
```

### ChromaDB (Still Intact)
```bash
python3 << 'EOF'
import chromadb
client = chromadb.PersistentClient(path="/home/ubuntu/feedfocus/chroma_db")
collection = client.get_collection("insights")
print(f"ChromaDB count: {collection.count()}")  # Should still be 1830
EOF
```

### API Endpoints
```bash
# Following feed
curl https://api.feed-focus.com/api/feed/following?user_id=default&limit=5

# For You feed
curl https://api.feed-focus.com/api/feed/for-you?user_id=default&limit=5
```

---

## Rollback Plan

If something goes wrong:

```bash
# 1. Restore database backup
ssh ubuntu@3.17.64.149
cd /home/ubuntu/feedfocus
cp insights.db.backup-YYYYMMDD-HHMMSS insights.db

# 2. Restart backend
sudo systemctl restart feedfocus-backend

# ChromaDB is unchanged - no rollback needed
```

---

## What Stays the Same

- ✅ ChromaDB still has all 1830 insights
- ✅ Old `/api/feed` endpoint still works
- ✅ Extraction pipeline works (just needs small update)
- ✅ No data loss

## What's New

- ✅ SQLite has copy of all insights
- ✅ New `/api/feed/following` endpoint
- ✅ New `/api/feed/for-you` endpoint
- ✅ Faster filtering and ranking
- ✅ Better user-specific queries

---

## Timeline

1. **Migration**: 5-10 minutes (1830 insights)
2. **Testing**: 5 minutes
3. **Restart backend**: 30 seconds
4. **Total downtime**: ~1 minute (during restart)

---

## Next Steps After Migration

1. ✅ Verify all 1830 insights migrated
2. ✅ Test new unified feed endpoints
3. ✅ Update extraction pipeline to write to both DBs
4. ✅ Deploy web and mobile frontends
5. ✅ Monitor performance

---

**Status:** Ready to deploy  
**Risk:** Low (ChromaDB backup exists, old endpoints still work)  
**Reversible:** Yes (database backup)
