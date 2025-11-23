import sqlite3
import json
from datetime import datetime
from typing import List, Optional
import os
import sys
import re

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Compute project root and ensure it's on sys.path BEFORE local imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from automation.semantic_db import search_insights
from automation.training_logger import log_feedback

# Load environment variables
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

# Feature flags
ENABLE_POST_COLLECTION_FILTER = os.getenv('ENABLE_POST_COLLECTION_FILTER', 'true').lower() == 'true'
print(f"🔧 Post-collection filtering: {'ENABLED' if ENABLE_POST_COLLECTION_FILTER else 'DISABLED'}")

app = FastAPI(title="Insight Feed API", version="3.0.0")

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

class EngagementAction(BaseModel):
    insight_id: str
    action: str  # 'like', 'x' (dismiss), 'bookmark', 'share'

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
    """Generate a specific title from insight content"""
    
    # Extract capitalized proper nouns (companies, people, products)
    import re
    proper_nouns = re.findall(r'(?<!^)(?<=[\s,])([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})?)', insights_text)
    
    # Deduplicate and take first 2
    unique_nouns = []
    seen = set()
    for noun in proper_nouns:
        if noun.lower() not in seen and len(unique_nouns) < 2:
            unique_nouns.append(noun)
            seen.add(noun.lower())
    
    if unique_nouns:
        return f"{', '.join(unique_nouns)} Insights"
    
    # Extract domain name as fallback
    domain_parts = domain.replace('www.', '').split('.')
    domain_name = domain_parts[0].title()
    
    return f"{domain_name} Insights"


# API Endpoints

@app.get("/")
async def root():
    return {
        "message": "Insight Feed API", 
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
    
    print(f"[DEBUG] Interests: {interest_list}")
    print(f"[DEBUG] Query: {query}")

    # Fetch more results since we'll group them
    raw_results = search_insights(query=query, top_k=limit * 5)
    print(f"[DEBUG] Raw results from vector DB: {len(raw_results)}")

    # 4. Filter out dismissed insights + optional post-collection quality filter
    if ENABLE_POST_COLLECTION_FILTER:
        filtered = [
            r for r in raw_results 
            if r["id"] not in dismissed_ids 
            and should_display_in_feed(r["metadata"].get("text", ""), r["metadata"])
        ]
        print(f"[DEBUG] After quality filter: {len(filtered)} insights (filtering enabled)")
    else:
        filtered = [
            r for r in raw_results 
            if r["id"] not in dismissed_ids
        ]
        print(f"[DEBUG] Skipped quality filter: {len(filtered)} insights (filtering disabled)")

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
    
    print(f"[DEBUG] Grouped into {len(source_cards)} source cards")
    
    return source_cards[:limit]

@app.post("/api/feed/engage")
async def engage_with_insight(engagement: EngagementAction):
    """
    Record user engagement with insight
    Updates recommendation algorithm
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Record engagement as a log against the vector insight ID
    cursor.execute(
        """
        INSERT INTO insight_engagement (insight_id, action, created_at, user_id)
        VALUES (?, ?, ?, ?)
        """,
        (engagement.insight_id, engagement.action, datetime.now().isoformat(), 1),
    )

    conn.commit()
    conn.close()
    
    # Log feedback for training data (non-blocking)
    try:
        log_feedback(
            insight_id=engagement.insight_id,
            action=engagement.action,
            metadata={"user_id": 1}
        )
    except Exception:
        # Don't fail engagement if logging fails
        pass
    
    return {"status": "recorded"}

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
        print(f"Feed generation error: {e}")

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
