import json
import os
import re
import sqlite3
import sys
from datetime import datetime
from typing import List

from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from automation.semantic_db import search_insights
from backend.extraction_queue import ExtractionQueue
from backend.semantic_search import find_similar_topic, get_topic_insight_count
from backend.topic_validation import validate_topic
from backend.utils.logger import setup_logger
import asyncio

# Compute project root and ensure it's on sys.path BEFORE local imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

logger = setup_logger(__name__)

# Global extraction queue (initialized on startup)
extraction_queue = None

# Minimum insights threshold for topic readiness
MIN_INSIGHTS_THRESHOLD = 30

# Import unified feed service
try:
    from backend.services.feed_service import FeedService
    UNIFIED_FEED_ENABLED = True
except ImportError:
    UNIFIED_FEED_ENABLED = False
    logger.warning("Unified feed service not available")

# Import auth middleware
try:
    from backend.middleware.auth import verify_token
    AUTH_ENABLED = True
except ImportError:
    AUTH_ENABLED = False
    logger.warning("Auth middleware not available")

# Load environment variables
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

# Feature flags
ENABLE_POST_COLLECTION_FILTER = os.getenv('ENABLE_POST_COLLECTION_FILTER', 'true').lower() == 'true'
logger.info(f"Post-collection filtering: {'ENABLED' if ENABLE_POST_COLLECTION_FILTER else 'DISABLED'}")

app = FastAPI(title="Feed Focus API", version="3.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database path - use absolute path relative to PROJECT_ROOT
DB_PATH = os.path.join(PROJECT_ROOT, "insights.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Initialize database tables if they don't exist"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create user_engagement table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_engagement (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            insight_id TEXT NOT NULL,
            action TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # Create user_topics table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_topics (
            user_id TEXT NOT NULL,
            topic TEXT NOT NULL,
            followed_at TEXT NOT NULL,
            PRIMARY KEY (user_id, topic)
        )
    """)

    # Create indexes for performance
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_user_engagement_user
        ON user_engagement(user_id, action)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_user_engagement_insight
        ON user_engagement(insight_id)
    """)

    conn.commit()
    conn.close()

def run_extraction(topic: str, user_id: str) -> dict:
    """
    Wrapper function to run async extraction pipeline synchronously.

    Args:
        topic: Topic to extract insights for
        user_id: User who requested the extraction

    Returns:
        Dict with extraction results
    """
    try:
        # Lazy import - only load when actually running extraction
        from automation.topic_handler import process_topic

        # Run async process_topic in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(process_topic(topic))

            # Adapt result format to what queue expects
            if result.get("status") == "success":
                return {
                    "insight_count": result.get("insights_count", 0),
                    "sources_processed": result.get("sources_count", 0)
                }
            else:
                # Extraction failed
                error_msg = result.get("error", "Unknown error")
                raise Exception(f"Extraction failed: {error_msg}")

        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Extraction error for topic '{topic}': {e}")
        raise

@app.on_event("startup")
async def startup_event():
    """Initialize database, enable WAL mode, and recover stale extraction jobs."""
    global extraction_queue

    logger.info("Starting up application...")

    # Enable WAL mode for better concurrency
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("PRAGMA journal_mode=WAL")
    journal_mode = cursor.fetchone()[0]
    logger.info(f"Database journal mode: {journal_mode}")

    if journal_mode.upper() == "WAL":
        logger.info("WAL mode enabled - multiple workers can write concurrently")

    conn.close()

    # Initialize database tables
    init_database()
    logger.info("Database initialized")

    # Initialize extraction queue with 2 workers
    logger.info("Initializing extraction queue...")
    extraction_queue = ExtractionQueue(num_workers=2, extraction_fn=run_extraction)

    # Recover any stale jobs from previous session
    logger.info("Checking for stale extraction jobs...")
    extraction_queue.recover_stale_jobs()

    logger.info("Application startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    """Gracefully shutdown extraction queue and cleanup resources."""
    global extraction_queue

    logger.info("Shutting down application...")

    if extraction_queue:
        logger.info("Stopping extraction queue...")
        extraction_queue.stop()
        logger.info("Extraction queue stopped - all workers finished")

    logger.info("Application shutdown complete")


# Pydantic models
class Interest(BaseModel):
    topic: str

class InsightSummary(BaseModel):
    id: str
    text: str
    category: str
    similarity_score: float

class SourceCard(BaseModel):
    id: str  # source_url
    source_url: str
    source_domain: str
    title: str
    insights: List[InsightSummary]
    insight_count: int
    created_at: str
    relevance_score: float
    topics: List[str]

# Helper functions
def generate_title(extracted_data: dict) -> str:
    """Generate short title from first sentence or ~60 chars"""
    for field_name, values in extracted_data.items():
        if isinstance(values, list) and len(values) > 0:
            text = values[0] if values[0] else "Interesting insight"
            # Try to extract first sentence or first part before arrow
            if '→' in text:
                title = text.split('→')[0].strip()
            elif '.' in text[:100]:
                title = text.split('.')[0].strip() + '.'
            else:
                title = text[:60] + '...' if len(text) > 60 else text
            return title
    return "Interesting insight"

def generate_summary(extracted_data: dict) -> str:
    """Return full insight text without truncation"""
    for field_name, values in extracted_data.items():
        if isinstance(values, list) and len(values) > 0:
            # Return full text, not truncated
            return values[0] if isinstance(values[0], str) else str(values[0])
    return "New insight discovered"

def categorize_insight(extracted_data: dict) -> str:
    """Categorize insight for UI"""
    data_str = json.dumps(extracted_data).lower()

    if any(word in data_str for word in ['data', 'study', 'research', 'analysis']):
        return "data-driven"
    if any(word in data_str for word in ['trend', 'growing', 'emerging', 'rising']):
        return "trending"
    if any(word in data_str for word in ['contrarian', 'opposite', 'different', 'unique']):
        return "contrarian"
    return "insight"

def format_category_display(category: str) -> str:
    """Format category with emoji for inline display"""
    category_map = {
        "strategic_insights": "💡 CASE STUDY",
        "counterintuitive": "🔥 COUNTERINTUITIVE",
        "tactical_playbooks": "📊 PLAYBOOK",
        "emerging_patterns": "⚡ EARLY SIGNAL",
        "case_studies": "💡 CASE STUDY",
        # Legacy categories
        "key_insights": "💡 KEY INSIGHT",
        "surprising_findings": "🔥 SURPRISING",
        "timing_windows": "⚡ TIMING",
        "implications": "💡 INSIGHT"
    }
    return category_map.get(category, "💡 INSIGHT")

def should_display_in_feed(insight_text: str, metadata: dict) -> bool:
    """
    Universal quality gate - works for any topic
    Filters based on structural patterns, not specific content
    """

    text_lower = insight_text.lower()

    # === 1. STRUCTURAL RED FLAGS ===

    # Self-promotional language (any industry)
    if re.search(r'\b(our|my) (platform|solution|approach|product|tool|system|service|software|company)\b', text_lower):
        return False

    # Call-to-action language (any industry)
    if re.search(r'\b(sign up|subscribe|learn more|contact us|visit our|click here|get started|try free)\b', text_lower):
        return False

    # Marketing language (any industry)
    if re.search(r'\b(leading|industry-leading|award-winning|recognized as|top-rated) (provider|solution|platform|company)\b', text_lower):
        return False

    # === 2. VAGUE LANGUAGE (must have numbers to pass) ===

    vague_patterns = [
        r'\b(increasingly|becoming|growing|rising) (important|popular|common|widespread)\b',
        r'\b(plays a|is) (crucial|essential|critical|vital|important) role\b',
        r'\b(companies|organizations|leaders|businesses) (should|must|need to|are) (adapt|recognize|embrace)\b',
        r'\bin (today\'s|the modern|this|the current) (world|era|landscape|environment)\b',
    ]

    has_vague = any(re.search(pattern, text_lower) for pattern in vague_patterns)
    has_numbers = bool(re.search(r'\d+%|\d+x|\d+\.\d+|\d{3,}', insight_text))

    if has_vague and not has_numbers:
        return False

    # === 3. REQUIRE SUBSTANCE (at least 2 of 4 signals) ===

    substance_signals = 0

    # Signal 1: Proper nouns (companies, people, products)
    # Pattern: Capital letter followed by lowercase, not at sentence start
    proper_nouns = re.findall(r'(?<!^)(?<!\.)\s+([A-Z][a-z]{2,})', insight_text)
    # Also catch acronyms
    acronyms = re.findall(r'\b[A-Z]{2,5}\b', insight_text)

    if len(proper_nouns) + len(acronyms) >= 2:
        substance_signals += 1

    # Signal 2: Concrete numbers (any format)
    number_patterns = [
        r'\d+\.?\d*%',           # 15%, 3.5%
        r'\d+x',                 # 10x, 3x
        r'\$\d+',                # $100M, $5B
        r'[<>]=?\s*\d+',         # >20, <15
        r'\d{3,}',               # 1000, 500
    ]

    if sum(1 for p in number_patterns if re.search(p, insight_text)) >= 2:
        substance_signals += 1

    # Signal 3: Tactical/actionable language
    tactical_indicators = [
        'framework', 'playbook', 'strategy', 'approach', 'formula',
        'criteria', 'threshold', 'trigger', 'rule', 'process',
        'step', 'method', 'system', 'structure', 'model',
    ]

    if sum(1 for word in tactical_indicators if word in text_lower) >= 2:
        substance_signals += 1

    # Signal 4: Specific results/outcomes
    outcome_patterns = [
        r'(increased|decreased|grew|declined|rose|fell) (by )?\d+',
        r'(achieved|delivered|generated|returned) \d+',
        r'from \$?\d+.* to \$?\d+',
        r'(over|in) \d+ (years|months)',
    ]

    if any(re.search(p, text_lower) for p in outcome_patterns):
        substance_signals += 1

    # Need at least 2 substance signals
    if substance_signals < 2:
        return False

    # === 4. LENGTH CHECKS ===

    # Too short (likely incomplete or just a headline)
    if len(insight_text) < 80:
        return False

    # Too long (likely rambling or not edited)
    if len(insight_text) > 500:
        return False

    # Very short insights (80-120 chars) must be extremely specific
    if len(insight_text) < 120:
        # Must have proper nouns AND numbers
        if not (len(proper_nouns) + len(acronyms) >= 1 and has_numbers):
            return False

    # === 5. TOPIC RELEVANCE (generic check) ===

    # If insight is just defining the topic itself, likely generic
    topic = metadata.get('topic', '').lower()

    if topic:
        # Get significant words from topic (exclude common words)
        topic_words = [w for w in topic.split() if len(w) > 3]

        # Check if first 60 chars look like a definition
        first_60 = insight_text[:60].lower()

        # Pattern: "[Topic words] is/are/refers to..."
        if len(topic_words) > 0:
            if all(word in first_60 for word in topic_words):
                # Likely a definition like "Value investing is an approach that..."
                if re.search(r'\b(is|are|refers to|means|involves|focuses on)\b', first_60):
                    return False

    return True


def generate_source_title(insights_text: str, domain: str) -> str:
    """Fast, reliable title generation for Render deployment"""
    import re

    # Remove labels
    text = insights_text
    for label in ['💡 CASE STUDY', '🔉 COUNTERINTUITIVE', '📊 PLAYBOOK', '⚡ EARLY SIGNAL',
                  '💡 KEY INSIGHT', '🔥 SURPRISING', '⚡ TIMING', '💡 INSIGHT']:
        text = text.replace(label, '').strip()

    # Get first complete sentence
    sentences = re.split(r'(?<=[.!?])\s+', text)
    first_sentence = sentences[0] if sentences else text

    # Remove common prefixes that don't add value
    first_sentence = re.sub(r'^(According to|Based on|In a|The study shows|Research finds)\s+',
                           '', first_sentence, flags=re.IGNORECASE)

    # Smart truncation at natural break points
    if len(first_sentence) > 80:
        # Try to break at: comma, dash, "that", "which", "because"
        for pattern in [r'^(.{30,80}),\s', r'^(.{30,80})\s-\s', r'^(.{30,80})\s(?:that|which|because)\s']:
            match = re.search(pattern, first_sentence)
            if match:
                first_sentence = match.group(1)
                break
        else:
            # Just truncate at last complete word
            first_sentence = first_sentence[:77].rsplit(' ', 1)[0] + '...'

    # Capitalize first letter if needed
    if first_sentence and first_sentence[0].islower():
        first_sentence = first_sentence[0].upper() + first_sentence[1:]

    return first_sentence.strip()


# API Endpoints

@app.get("/")
async def root():
    return {
        "message": "Feed Focus API",
        "version": "3.0.0",
        "post_collection_filter_enabled": ENABLE_POST_COLLECTION_FILTER
    }

@app.get("/api/interests")
async def get_interests():
    """Get user's interests"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_interests ORDER BY created_at DESC")
    interests = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return interests

@app.post("/api/interests")
async def add_interest(interest: Interest):
    """Add a new interest"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO user_interests (topic, created_at) VALUES (?, ?)",
        (interest.topic, datetime.now().isoformat())
    )
    conn.commit()
    interest_id = cursor.lastrowid
    conn.close()
    return {"id": interest_id, "status": "added"}

@app.delete("/api/interests/{interest_id}")
async def delete_interest(interest_id: int):
    """Delete an interest"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_interests WHERE id = ?", (interest_id,))
    conn.commit()
    conn.close()
    return {"status": "deleted"}

@app.get("/api/feed", response_model=List[SourceCard])
async def get_feed(limit: int = 20, interests: str = ""):
    """Get personalized feed from vector DB, grouped by source

    Args:
        limit: Max number of source cards to return
        interests: Comma-separated list of interest topics (from client localStorage)
    """
    from collections import defaultdict

    # Parse interests from query parameter (sent by frontend)
    interest_list = [i.strip() for i in interests.split(",") if i.strip()] if interests else []

    # Get dismissed insight IDs (only 'x' action removes from feed)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT DISTINCT insight_id
        FROM insight_engagement
        WHERE user_id = 1 AND action = 'x'
        """
    )
    dismissed_ids = {row["insight_id"] for row in cursor.fetchall()}
    conn.close()

    # Build semantic query from interests
    query = " ".join(interest_list) if interest_list else "insights"

    logger.debug(f"Interests: {interest_list}")
    logger.debug(f"Query: {query}")

    # Fetch more results since we'll group them
    raw_results = search_insights(query=query, top_k=limit * 5)
    logger.debug(f"Raw results from vector DB: {len(raw_results)}")

    # 4. Filter out dismissed insights + optional post-collection quality filter
    if ENABLE_POST_COLLECTION_FILTER:
        filtered = [
            r for r in raw_results
            if r["id"] not in dismissed_ids
            and should_display_in_feed(r["metadata"].get("text", ""), r["metadata"])
        ]
        logger.debug(f"After quality filter: {len(filtered)} insights (filtering enabled)")
    else:
        filtered = [
            r for r in raw_results
            if r["id"] not in dismissed_ids
        ]
        logger.debug(f"Skipped quality filter: {len(filtered)} insights (filtering disabled)")

    # GROUP BY SOURCE
    sources = defaultdict(list)
    for result in filtered:
        meta = result["metadata"]
        source_key = meta.get("source_url", "unknown")

        sources[source_key].append({
            "id": result["id"],
            "text": meta.get("text", ""),
            "category": meta.get("category", "key_insights"),
            "similarity_score": float(result.get("similarity_score", 0.0)),
            "metadata": meta
        })

    # Create source cards
    source_cards: List[SourceCard] = []
    for source_url, insights in sources.items():
        # Get metadata from first insight
        first_meta = insights[0]["metadata"]

        # Calculate average relevance
        avg_relevance = sum(i["similarity_score"] for i in insights) / len(insights)

        # Generate title from insights
        all_text = " ".join([i["text"] for i in insights[:3]])
        title = generate_source_title(all_text, first_meta.get("source_domain", "Unknown"))

        # Create InsightSummary objects with formatted category display
        insight_summaries = []
        for i in insights[:4]:  # Limit to 4 insights per source (relaxed from 3 for more depth)
            # Map category to display format
            category_display = format_category_display(i["category"])

            insight_summaries.append(
                InsightSummary(
                    id=i["id"],
                    text=f"{category_display}\n{i['text']}",  # Inline category
                    category=i["category"],
                    similarity_score=i["similarity_score"]
                )
            )

        card = SourceCard(
            id=source_url,
            source_url=source_url,
            source_domain=first_meta.get("source_domain", "Unknown"),
            title=title,
            insights=insight_summaries,
            insight_count=len(insights),
            created_at=first_meta.get("extracted_at", datetime.now().isoformat()),
            relevance_score=avg_relevance,
            topics=[first_meta.get("topic", "")]
        )

        source_cards.append(card)

    # Sort by relevance
    source_cards.sort(key=lambda x: x.relevance_score, reverse=True)

    logger.debug(f"Grouped into {len(source_cards)} source cards")

    return source_cards[:limit]

# Global variable to track feed generation status
feed_generation_status = {
    "is_running": False,
    "progress": "",
    "completed": False,
    "error": None
}

async def run_feed_generation():
    """Run feed generator in background"""
    global feed_generation_status

    try:
        feed_generation_status["is_running"] = True
        feed_generation_status["progress"] = "Starting feed generation..."
        feed_generation_status["completed"] = False
        feed_generation_status["error"] = None

        # Import here to avoid circular imports
        from api.feed_generator import generate_feed

        feed_generation_status["progress"] = "Generating feed..."
        await generate_feed()

        feed_generation_status["is_running"] = False
        feed_generation_status["completed"] = True
        feed_generation_status["progress"] = "Feed generation complete!"

    except Exception as e:
        feed_generation_status["is_running"] = False
        feed_generation_status["error"] = str(e)
        feed_generation_status["progress"] = f"Error: {str(e)}"
        logger.error(f"Feed generation error: {e}")

@app.post("/api/generate-feed")
async def trigger_feed_generation(background_tasks: BackgroundTasks):
    """
    Legacy endpoint - now a no-op since feed uses vector DB.
    Returns immediately as if generation completed.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM user_interests")
    interests_count = cursor.fetchone()['count']
    conn.close()

    if interests_count == 0:
        raise HTTPException(status_code=400, detail="Please add at least one interest first")

    # No-op: vector DB feed doesn't need generation
    global feed_generation_status
    feed_generation_status["is_running"] = False
    feed_generation_status["completed"] = True
    feed_generation_status["progress"] = "Feed ready (using vector search)"

    return {
        "status": "completed",
        "message": "Feed is ready. Using semantic search over imported insights."
    }

@app.get("/api/generate-feed/status")
async def get_generation_status():
    """Get current feed generation status"""
    return feed_generation_status

@app.get("/api/stats")
async def get_stats():
    """Get feed statistics"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Total insights
    cursor.execute("SELECT COUNT(*) as count FROM insights_v2")
    total_insights = cursor.fetchone()['count']

    # Interests count
    cursor.execute("SELECT COUNT(*) as count FROM user_interests")
    interests_count = cursor.fetchone()['count']

    # Feed queue size
    cursor.execute("SELECT COUNT(*) as count FROM feed_queue WHERE shown = 0")
    queue_size = cursor.fetchone()['count']

    # Engagement stats
    cursor.execute("""
        SELECT action, COUNT(*) as count
        FROM insight_engagement
        GROUP BY action
    """)
    engagement = {row['action']: row['count'] for row in cursor.fetchall()}

    conn.close()

    return {
        "total_insights": total_insights,
        "interests_count": interests_count,
        "queue_size": queue_size,
        "engagement": engagement
    }


# ============================================================================
# UNIFIED FEED ENDPOINTS (New Architecture)
# ============================================================================

@app.get("/api/feed/following")
async def get_following_feed(
    limit: int = 30,
    offset: int = 0,
    user_id: str = Depends(verify_token) if AUTH_ENABLED else "default"
):
    """
    Get Following feed - unified stream of insights from user's followed topics

    Requires authentication. User ID is extracted from JWT token.

    Returns insights from all topics the user follows, ranked by personalization
    """
    if not UNIFIED_FEED_ENABLED:
        raise HTTPException(status_code=501, detail="Unified feed not available")

    try:
        feed_service = FeedService()
        insights = feed_service.generate_following_feed(user_id, limit, offset)

        return {
            "feed_type": "following",
            "insights": insights,
            "count": len(insights),
            "has_more": len(insights) == limit
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate feed: {str(e)}")


@app.get("/api/feed/for-you")
async def get_for_you_feed(
    limit: int = 30,
    offset: int = 0,
    user_id: str = Depends(verify_token) if AUTH_ENABLED else "default"
):
    """
    Get For You feed - algorithmic recommendations from ALL topics

    Requires authentication. User ID is extracted from JWT token.

    Returns insights from any topic, ranked by predicted engagement
    """
    if not UNIFIED_FEED_ENABLED:
        raise HTTPException(status_code=501, detail="Unified feed not available")

    try:
        feed_service = FeedService()
        insights = feed_service.generate_for_you_feed(user_id, limit, offset)

        return {
            "feed_type": "for_you",
            "insights": insights,
            "count": len(insights),
            "has_more": len(insights) == limit
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate feed: {str(e)}")


class FeedEngagement(BaseModel):
    insight_id: str
    action: str  # 'view', 'like', 'save', 'dismiss'


@app.post("/api/feed/engage")
async def record_feed_engagement(
    engagement: FeedEngagement,
    user_id: str = Depends(verify_token) if AUTH_ENABLED else "default"
):
    """
    Record user engagement with an insight

    Requires authentication. User ID is extracted from JWT token.

    Actions: view, like, save, dismiss
    """
    if not UNIFIED_FEED_ENABLED:
        raise HTTPException(status_code=501, detail="Unified feed not available")

    # Validate action
    valid_actions = ['view', 'like', 'save', 'dismiss']
    if engagement.action not in valid_actions:
        raise HTTPException(status_code=400, detail=f"Invalid action. Must be one of: {valid_actions}")

    try:
        feed_service = FeedService()
        feed_service.record_engagement(
            user_id,
            engagement.insight_id,
            engagement.action
        )

        return {
            "status": "recorded",
            "user_id": user_id,
            "insight_id": engagement.insight_id,
            "action": engagement.action
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to record engagement: {str(e)}")


class TopicFollow(BaseModel):
    topic: str


@app.post("/api/topics/follow")
async def follow_topic(
    follow: TopicFollow,
    user_id: str = Depends(verify_token) if AUTH_ENABLED else "default"
):
    """
    Follow a topic with validation, similarity checking, and extraction queueing.

    Flow:
    1. Validate topic (rule-based + SLM)
    2. Check for similar existing topics (semantic similarity)
    3. Add user to user_topics immediately
    4. Check if >= 30 insights exist
    5. If not, queue extraction job

    Requires authentication. User ID is extracted from JWT token.
    """
    topic = follow.topic.strip()

    try:
        # Step 1: Validate topic
        is_valid, error_message, suggestion = validate_topic(topic)

        if not is_valid:
            return {
                "status": "invalid",
                "error": error_message,
                "suggestion": suggestion if suggestion else None
            }

        # Step 2: Check for similar existing topics (threshold 0.85)
        similar_result = find_similar_topic(topic, threshold=0.85)

        if similar_result:
            existing_topic, similarity = similar_result
            insight_count = get_topic_insight_count(existing_topic)

            logger.info(
                f"Found similar topic '{existing_topic}' (similarity: {similarity:.2f}) "
                f"for '{topic}', reusing with {insight_count} insights"
            )

            # Add user to user_topics with the existing topic
            conn = get_db_connection()
            cursor = conn.cursor()

            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO user_topics (user_id, topic, followed_at)
                    VALUES (?, ?, ?)
                """, (user_id, existing_topic, datetime.now().isoformat()))
                conn.commit()
            finally:
                conn.close()

            return {
                "status": "ready",
                "topic": existing_topic,
                "original_topic": topic,
                "insight_count": insight_count,
                "similarity": similarity
            }

        # Step 3: Add user to user_topics immediately (with exact topic)
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT OR IGNORE INTO user_topics (user_id, topic, followed_at)
                VALUES (?, ?, ?)
            """, (user_id, topic, datetime.now().isoformat()))
            conn.commit()
        finally:
            conn.close()

        # Step 4: Check insight count
        insight_count = get_topic_insight_count(topic)

        # Step 5: Queue extraction if needed
        if insight_count < MIN_INSIGHTS_THRESHOLD:
            logger.info(
                f"Topic '{topic}' has {insight_count} insights (< {MIN_INSIGHTS_THRESHOLD}), "
                f"queueing extraction"
            )

            if extraction_queue is None:
                raise HTTPException(
                    status_code=503,
                    detail="Extraction queue not initialized"
                )

            try:
                # Add job with low priority (1) for user-triggered extractions
                # Daily refresh (priority 10) benefits all users and goes first
                result = extraction_queue.add_job(
                    topic=topic,
                    user_id=user_id,
                    priority=1
                )

                return {
                    "status": "extracting",
                    "topic": topic,
                    "message": "Extraction queued - insights will be available shortly",
                    "existing_count": insight_count,
                    "job_id": result["job_id"]
                }

            except ValueError as e:
                # Job already exists (duplicate)
                if "already" in str(e).lower():
                    return {
                        "status": "extracting",
                        "topic": topic,
                        "message": "Extraction already in progress",
                        "existing_count": insight_count
                    }
                raise

        # Topic has enough insights already
        logger.info(f"Topic '{topic}' ready with {insight_count} insights")

        return {
            "status": "ready",
            "topic": topic,
            "insight_count": insight_count
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to follow topic '{topic}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to follow topic: {str(e)}")


@app.get("/api/topics/{topic}/status")
async def get_topic_status(
    topic: str,
    user_id: str = Depends(verify_token) if AUTH_ENABLED else "default"
):
    """
    Get comprehensive status for a topic including extraction job status.

    Returns:
    - is_following: Whether user follows this topic
    - insight_count: Number of insights available
    - extraction_job: Current extraction job details (if any)

    Requires authentication. User ID is extracted from JWT token.
    """
    try:
        topic = topic.strip()

        # Check if user is following
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT COUNT(*) FROM user_topics
                WHERE user_id = ? AND topic = ?
            """, (user_id, topic))
            is_following = cursor.fetchone()[0] > 0

            # Get insight count
            insight_count = get_topic_insight_count(topic)

            # Get extraction job status (most recent)
            cursor.execute("""
                SELECT
                    id,
                    status,
                    insight_count,
                    error,
                    sources_processed,
                    estimated_completion_at,
                    retry_count,
                    created_at,
                    updated_at
                FROM extraction_jobs
                WHERE topic = ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (topic,))

            job_row = cursor.fetchone()

            extraction_job = None
            if job_row:
                job_id, status, job_insight_count, error, sources_processed, \
                estimated_completion_at, retry_count, created_at, updated_at = job_row

                # Parse error JSON if exists
                error_obj = None
                if error:
                    try:
                        error_obj = json.loads(error)
                    except Exception:
                        error_obj = {"type": "unknown", "message": error, "retry_eligible": False}

                extraction_job = {
                    "status": status,
                    "insight_count": job_insight_count or 0,
                    "error": error_obj,
                    "sources_processed": sources_processed or 0,
                    "estimated_completion_at": estimated_completion_at,
                    "retry_count": retry_count or 0,
                    "created_at": created_at,
                    "updated_at": updated_at
                }

            return {
                "topic": topic,
                "is_following": is_following,
                "insight_count": insight_count,
                "extraction_job": extraction_job
            }

        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Failed to get topic status for '{topic}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get topic status: {str(e)}")


@app.get("/api/topics/{topic}/insights")
async def get_topic_insights(
    topic: str,
    limit: int = 30,
    offset: int = 0,
    user_id: str = Depends(verify_token) if AUTH_ENABLED else "default"
):
    """
    Get insights for a specific topic with pagination.

    Returns insights ordered by quality score, with engagement tracking.
    """
    try:
        topic = topic.strip()

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # Get insights for this topic
            cursor.execute("""
                SELECT
                    id,
                    topic,
                    category,
                    text,
                    source_url,
                    source_domain,
                    quality_score,
                    engagement_score,
                    created_at
                FROM insights
                WHERE topic = ?
                ORDER BY quality_score DESC, created_at DESC
                LIMIT ? OFFSET ?
            """, (topic, limit, offset))

            insights = []
            for row in cursor.fetchall():
                insight_id, topic, category, text, source_url, source_domain, \
                quality_score, engagement_score, created_at = row

                insights.append({
                    "id": insight_id,
                    "topic": topic,
                    "category": category,
                    "text": text,
                    "source_url": source_url,
                    "source_domain": source_domain,
                    "quality_score": quality_score,
                    "engagement_score": engagement_score,
                    "created_at": created_at
                })

            # Check if there are more results
            cursor.execute("""
                SELECT COUNT(*) FROM insights WHERE topic = ?
            """, (topic,))
            total_count = cursor.fetchone()[0]
            has_more = (offset + len(insights)) < total_count

            return {
                "topic": topic,
                "insights": insights,
                "count": len(insights),
                "total": total_count,
                "has_more": has_more
            }

        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Failed to get insights for topic '{topic}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get insights: {str(e)}")


@app.post("/api/topics/{topic}/retry")
async def retry_extraction(
    topic: str,
    user_id: str = Depends(verify_token) if AUTH_ENABLED else "default"
):
    """
    Manually retry a failed extraction job.

    Checks for failed job, verifies retry limit not exceeded,
    increments retry count, and re-queues with high priority.

    Requires authentication. User ID is extracted from JWT token.
    """
    try:
        topic = topic.strip()

        if extraction_queue is None:
            raise HTTPException(
                status_code=503,
                detail="Extraction queue not initialized"
            )

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # Find most recent failed job for this topic
            cursor.execute("""
                SELECT id, user_id, priority, retry_count
                FROM extraction_jobs
                WHERE topic = ? AND status = 'failed'
                ORDER BY created_at DESC
                LIMIT 1
            """, (topic,))

            job_row = cursor.fetchone()

            if not job_row:
                return {
                    "status": "not_found",
                    "error": "No failed extraction found for this topic"
                }

            job_id, job_user_id, priority, retry_count = job_row

            # Check retry limit
            if retry_count >= 3:
                return {
                    "status": "max_retries",
                    "error": "Max retries reached (3)",
                    "retry_count": retry_count
                }

            # Increment retry count and update timestamps
            new_retry_count = retry_count + 1
            now = datetime.now().isoformat()

            cursor.execute("""
                UPDATE extraction_jobs
                SET status = 'queued',
                    retry_count = ?,
                    last_retry_at = ?,
                    updated_at = ?,
                    error = NULL
                WHERE id = ?
            """, (new_retry_count, now, now, job_id))

            conn.commit()

            # Re-queue with high priority (10)
            extraction_queue.job_queue.put((10, job_id, topic, job_user_id))

            # Track in active jobs
            with extraction_queue.active_jobs_lock:
                extraction_queue.active_jobs[topic] = job_id

            logger.info(
                f"Manually retrying extraction for '{topic}' "
                f"(attempt {new_retry_count}/{3})"
            )

            return {
                "status": "retrying",
                "attempt": new_retry_count,
                "message": f"Extraction requeued (attempt {new_retry_count}/3)",
                "job_id": job_id
            }

        finally:
            conn.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retry extraction for '{topic}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retry extraction: {str(e)}")


@app.get("/api/queue/health")
async def get_queue_health():
    """
    Get extraction queue health and statistics.

    Returns metrics about queue status, recent failures,
    and completion statistics for monitoring.

    No authentication required - monitoring endpoint.
    """
    try:
        if extraction_queue is None:
            raise HTTPException(
                status_code=503,
                detail="Extraction queue not initialized"
            )

        # Get queue metrics
        health_metrics = extraction_queue.get_health_metrics()

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # Get recent failures (last 5)
            cursor.execute("""
                SELECT topic, error, retry_count, updated_at
                FROM extraction_jobs
                WHERE status = 'failed'
                ORDER BY updated_at DESC
                LIMIT 5
            """)

            failures = []
            for row in cursor.fetchall():
                topic, error, retry_count, updated_at = row

                # Parse error JSON
                error_msg = "Unknown error"
                if error:
                    try:
                        error_obj = json.loads(error)
                        error_msg = error_obj.get("message", error)
                    except Exception:
                        error_msg = error

                failures.append({
                    "topic": topic,
                    "error": error_msg,
                    "retry_count": retry_count,
                    "failed_at": updated_at
                })

            # Get average completion time (in minutes)
            cursor.execute("""
                SELECT AVG(extraction_duration_seconds) / 60.0
                FROM extraction_jobs
                WHERE status = 'complete'
                AND extraction_duration_seconds IS NOT NULL
            """)

            avg_time_row = cursor.fetchone()
            avg_completion_time = round(avg_time_row[0], 2) if avg_time_row[0] else 0

            # Get jobs completed today
            cursor.execute("""
                SELECT COUNT(*)
                FROM extraction_jobs
                WHERE status = 'complete'
                AND DATE(updated_at) = DATE('now')
            """)

            completed_today = cursor.fetchone()[0]

            return {
                "workers_active": health_metrics["workers_active"],
                "queue_size": health_metrics["queue_size"],
                "jobs_processing": health_metrics["jobs_processing"],
                "recent_failures": failures,
                "avg_completion_time": avg_completion_time,
                "total_completed_today": completed_today
            }

        finally:
            conn.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get queue health: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get queue health: {str(e)}")


@app.delete("/api/topics/follow")
async def unfollow_topic(
    follow: TopicFollow,
    user_id: str = Depends(verify_token) if AUTH_ENABLED else "default"
):
    """
    Remove topic from user's following list

    Requires authentication. User ID is extracted from JWT token.
    """
    if not UNIFIED_FEED_ENABLED:
        raise HTTPException(status_code=501, detail="Unified feed not available")

    try:
        feed_service = FeedService()
        feed_service.unfollow_topic(user_id, follow.topic)

        return {
            "status": "unfollowed",
            "user_id": user_id,
            "topic": follow.topic
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to unfollow topic: {str(e)}")


@app.get("/api/topics/following")
async def get_following_topics(
    user_id: str = Depends(verify_token) if AUTH_ENABLED else "default"
):
    """
    Get list of topics user is following

    Requires authentication. User ID is extracted from JWT token.
    """
    if not UNIFIED_FEED_ENABLED:
        raise HTTPException(status_code=501, detail="Unified feed not available")

    try:
        feed_service = FeedService()
        topics = feed_service.get_user_topics(user_id)

        return {
            "user_id": user_id,
            "topics": topics,
            "count": len(topics)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get topics: {str(e)}")


@app.get("/api/insights/liked")
async def get_liked_insights(
    limit: int = 50,
    offset: int = 0,
    user_id: str = Depends(verify_token) if AUTH_ENABLED else "default"
):
    """
    Get user's liked insights

    Requires authentication. User ID is extracted from JWT token.
    """
    if not UNIFIED_FEED_ENABLED:
        raise HTTPException(status_code=501, detail="Unified feed not available")

    try:
        feed_service = FeedService()
        insights = feed_service.get_user_liked_insights(user_id, limit, offset)

        return {
            "user_id": user_id,
            "insights": insights,
            "count": len(insights),
            "has_more": len(insights) == limit
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get liked insights: {str(e)}")


@app.get("/api/insights/bookmarked")
async def get_bookmarked_insights(
    limit: int = 50,
    offset: int = 0,
    user_id: str = Depends(verify_token) if AUTH_ENABLED else "default"
):
    """
    Get user's bookmarked (saved) insights

    Requires authentication. User ID is extracted from JWT token.
    """
    if not UNIFIED_FEED_ENABLED:
        raise HTTPException(status_code=501, detail="Unified feed not available")

    try:
        feed_service = FeedService()
        insights = feed_service.get_user_bookmarked_insights(user_id, limit, offset)

        return {
            "user_id": user_id,
            "insights": insights,
            "count": len(insights),
            "has_more": len(insights) == limit
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get bookmarked insights: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
