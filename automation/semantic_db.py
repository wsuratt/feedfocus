# semantic_db.py
import json
import hashlib
from datetime import datetime
from typing import Dict, List, Optional
import sqlite3
import uuid

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import os
from groq import Groq
from functools import lru_cache
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Ensure consistent ChromaDB path regardless of where script is run from
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROMA_PATH = os.path.join(PROJECT_ROOT, "chroma_db")
DB_PATH = os.path.join(PROJECT_ROOT, "insights.db")

# Initialize ChromaDB persistent client
chroma_client = chromadb.PersistentClient(
    path=CHROMA_PATH,
    settings=Settings(
        anonymized_telemetry=False,
        allow_reset=True,
    ),
)

# Initialize embedding model (small and fast, good quality)
_model_name = "all-MiniLM-L6-v2"
model = SentenceTransformer(_model_name)

# Get or create collection
collection = chroma_client.get_or_create_collection(
    name="insights",
    metadata={"description": "Insight vectors for personalized feed"},
)

# Initialize Groq client for SLM evaluation
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))


def _make_insight_id(insight: Dict) -> str:
    """Create a deterministic ID from core insight fields.

    This lets us avoid duplicates when the same insight is imported again.
    """
    key_payload = json.dumps(
        {
            "text": insight.get("text", ""),
            "category": insight.get("category", ""),
            "topic": insight.get("topic", ""),
            "source_url": insight.get("source_url", ""),
        },
        sort_keys=True,
    )
    return hashlib.md5(key_payload.encode("utf-8")).hexdigest()


def _make_document_text(insight: Dict) -> str:
    """Create a single text string to embed from insight fields."""
    parts: List[str] = []

    topic = insight.get("topic")
    if topic:
        parts.append(f"Topic: {topic}")

    category = insight.get("category")
    if category:
        parts.append(f"Category: {category.replace('_', ' ')}")

    text = insight.get("text")
    if text:
        parts.append(text)

    domain = insight.get("source_domain")
    if domain:
        parts.append(f"Source: {domain}")

    return " | ".join(parts)


def add_insight(insight: Dict) -> str:
    """Add a single insight to the vector DB.

    Expected keys in `insight`:
      - text (str)
      - category (str)
      - topic (str)
      - source_url (str)
      - source_domain (str)
      - quality_score (float, optional)
      - extracted_at (str ISO, optional)
      - detected_year (int, optional)
    """
    insight_id = _make_insight_id(insight)

    # Check if already present
    try:
        existing = collection.get(ids=[insight_id])
        if existing.get("ids") and existing["ids"]:
            # Already exists
            return insight_id
    except Exception:
        # If collection.get fails for some reason, continue and attempt add
        pass

    doc = _make_document_text(insight)
    embedding = model.encode(doc).tolist()

    metadata: Dict = {
        "category": insight.get("category", ""),
        "topic": insight.get("topic", ""),
        "source_url": insight.get("source_url", ""),
        "source_domain": insight.get("source_domain", ""),
        "extracted_at": insight.get("extracted_at", ""),
        "quality_score": float(insight.get("quality_score", 0.0)),
    }
    if insight.get("detected_year") is not None:
        metadata["detected_year"] = int(insight["detected_year"])

    # Add clean text to metadata for display (not just for embedding)
    metadata["text"] = insight.get("text", "")

    collection.add(
        ids=[insight_id],
        embeddings=[embedding],
        documents=[doc],
        metadatas=[metadata],
    )

    # Also add to SQLite insights table for feed
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        sql_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO insights (
                id, topic, category, text, source_url, source_domain,
                quality_score, engagement_score, created_at, updated_at,
                is_archived, chroma_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sql_id,
            insight.get("topic", ""),
            insight.get("category", ""),
            insight.get("text", ""),
            insight.get("source_url", ""),
            insight.get("source_domain", ""),
            float(insight.get("quality_score", 0)),
            0.0,  # engagement_score starts at 0
            insight.get("extracted_at", datetime.now().isoformat()),
            datetime.now().isoformat(),
            0,  # not archived
            insight_id  # chroma_id for reference
        ))

        conn.commit()
        conn.close()
    except sqlite3.IntegrityError:
        # Already exists in SQLite, that's fine
        pass
    except Exception as e:
        # Log error but don't fail the whole operation
        print(f"Warning: Failed to add insight to SQLite: {e}")

    return insight_id


@lru_cache(maxsize=2000)
def evaluate_insight_quality_slm(insight_text: str, topic: str) -> dict:
    """
    Use Groq's Llama 3.2 (3B) for fast, free quality evaluation

    Returns: {
        "should_include": bool,
        "score": int (0-10),
        "reason": str
    }
    """

    prompt = f"""Evaluate this insight for a feed about "{topic}".

Insight: {insight_text}

Score 0-10 based on:
1. TOPIC RELEVANCE (0-3): Is it about "{topic}"?
2. SPECIFICITY (0-3): Has company names or concrete numbers?
3. ACTIONABLE (0-2): Can someone use this info?
4. CREDIBLE (0-2): Factual, not promotional/spam?

RED FLAGS (score 0):
- "Our platform/solution" = self-promo
- "Click here/Sign up" = spam
- Generic advice with no proof
- Off-topic

Respond ONLY with JSON (no markdown):
{{"score": <0-10>, "include": <true if >= 7>, "reason": "<brief>"}}"""

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",  # Fast, reliable
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,  # Low temp for consistent classification
            max_tokens=150,
        )

        result_text = response.choices[0].message.content.strip()

        # Parse JSON (Llama sometimes adds markdown)
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
            result_text = result_text.strip()

        result = json.loads(result_text)

        # Ensure boolean
        if 'include' not in result:
            result['include'] = result.get('score', 0) >= 7

        return {
            "should_include": result.get('include', True),
            "score": result.get('score', 7),
            "reason": result.get('reason', '')
        }

    except Exception as e:
        print(f"  ⚠️  SLM evaluation error: {e}")
        # Fail open - use fast heuristics
        return {
            "should_include": True,
            "score": 7,
            "reason": "Evaluation failed, using heuristics"
        }




def should_include_insight(insight_text: str, topic: str = "") -> bool:
    """
    Two-stage filtering: Fast path (cheap checks) + SLM evaluation (smart checks)
    """

    # FAST PATH: Cheap checks (no API calls)
    # 1. Length check
    if len(insight_text) < 80 or len(insight_text) > 500:
        return False

    # 2. Must have some capitalization or numbers (basic quality signal)
    import re
    has_capitals = bool(re.search(r'[A-Z][a-z]{2,}', insight_text))
    has_numbers = bool(re.search(r'\d+', insight_text))

    if not (has_capitals or has_numbers):
        return False

    # 3. Obvious spam (instant reject)
    spam_terms = [
        'click here', 'sign up now', 'free trial', 'limited time offer',
        'schedule a demo', 'request a demo', 'visit our website',
        'contact us today', 'get started today', 'privacy policy',
        'cookie policy', 'terms of service'
    ]
    text_lower = insight_text.lower()
    if any(term in text_lower for term in spam_terms):
        return False

    # 4. Obvious self-promotion (instant reject)
    self_promo = ['our platform', 'our solution', 'our product', 'our software', 'our service']
    if any(term in text_lower for term in self_promo):
        return False

    # SLOW PATH: SLM evaluation (nuanced quality checks)
    # Uses caching to avoid repeated API calls for same insight
    result = evaluate_insight_quality_slm(insight_text, topic or "general insights")

    # Log rejections for debugging
    if not result['should_include']:
        print(f"  ❌ Filtered (score {result['score']}): {insight_text[:60]}...")
        print(f"     Reason: {result['reason']}")

    return result['should_include']


def is_semantically_similar(text1: str, text2: str, threshold: float = 0.85) -> bool:
    """Check if two texts are semantically similar using embeddings"""
    try:
        emb1 = model.encode(text1)
        emb2 = model.encode(text2)

        # Cosine similarity
        similarity = sum(a * b for a, b in zip(emb1, emb2)) / (
            (sum(a * a for a in emb1) ** 0.5) * (sum(b * b for b in emb2) ** 0.5)
        )

        return similarity > threshold
    except:
        return False


def add_insights_batch(insights: List[Dict], topic: str = "") -> List[str]:
    """Add multiple insights with semantic deduplication and quality filtering.
    Returns list of inserted IDs.
    """

    print(f"    [DEBUG] add_insights_batch: Processing {len(insights)} insights for topic '{topic}'")

    # Deduplicate with semantic similarity check
    unique_insights = []
    duplicates_removed = 0
    quality_filtered = 0
    seen_texts: list[str] = []  # List of texts we've accepted

    for i, insight in enumerate(insights):
        text = insight.get('text', '')

        print(f"    [DEBUG] Insight {i+1}/{len(insights)}: {text[:100]}...")

        # Check quality first (with topic filtering)
        if not should_include_insight(text, topic):
            quality_filtered += 1
            print(f"    [DEBUG]   → REJECTED by quality filter")
            continue
        else:
            print(f"    [DEBUG]   → PASSED quality filter")

        # Check for semantic duplicates (tightened to catch similar angles)
        is_duplicate = False
        for seen_text in seen_texts:
            if is_semantically_similar(text, seen_text, threshold=0.87):
                is_duplicate = True
                duplicates_removed += 1
                print(f"    [DEBUG]   → DUPLICATE (similar to existing insight)")
                break

        if not is_duplicate:
            seen_texts.append(text)
            unique_insights.append(insight)
            print(f"    [DEBUG]   → ACCEPTED (unique)")

    print(f"    [DEBUG] Filtering summary:")
    print(f"    [DEBUG]   - Started with: {len(insights)} insights")
    print(f"    [DEBUG]   - Quality filtered: {quality_filtered}")
    print(f"    [DEBUG]   - Duplicates removed: {duplicates_removed}")
    print(f"    [DEBUG]   - Unique insights: {len(unique_insights)}")

    if duplicates_removed > 0:
        print(f"  ⏭️  Removed {duplicates_removed} duplicate insights (semantic)")
    if quality_filtered > 0:
        print(f"  🗑️  Filtered {quality_filtered} low-quality insights")

    print(f"  ✅ Adding {len(unique_insights)}/{len(insights)} insights to DB")

    # Add unique, high-quality insights
    added_ids = []
    for insight in unique_insights:
        insight_id = add_insight(insight)
        added_ids.append(insight_id)

    return added_ids


def search_insights(
    query: str,
    top_k: int = 20,
    filter_metadata: Optional[Dict] = None,
) -> List[Dict]:
    """Semantic search for insights.

    Returns list of dicts with keys: id, text, metadata, similarity_score.
    """
    try:
        if not query.strip():
            return []

        query_embedding = model.encode(query).tolist()

        # Build query args - only include 'where' if we have actual filters
        query_args = {
            "query_embeddings": [query_embedding],
            "n_results": top_k,
        }
        if filter_metadata:
            query_args["where"] = filter_metadata

        results = collection.query(**query_args)

        if not results.get("ids") or not results["ids"] or not results["ids"][0]:
            return []

        out: List[Dict] = []
        ids = results["ids"][0]
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]

        for i in range(len(ids)):
            similarity = 1.0 - float(dists[i]) if dists else 0.0
            out.append(
                {
                    "id": ids[i],
                    "text": docs[i],
                    "metadata": metas[i] if metas else {},
                    "similarity_score": similarity,
                }
            )

        return out
    except Exception as e:
        print(f"Search error: {e}")
        return []


def get_stats() -> Dict:
    """Return basic collection statistics."""
    count = 0
    try:
        count = collection.count()
    except Exception as e:
        print(f"Stats error: {e}")
    return {
        "total_insights": count,
        "collection_name": collection.name,
        "model": _model_name,
    }


def reset_database() -> None:
    """Delete and recreate the insights collection (destructive)."""
    print("\nWARNING: This will delete all vectors in the 'insights' collection.")
    confirm = input("Type 'DELETE' to confirm: ")
    if confirm != "DELETE":
        print("Cancelled.")
        return

    chroma_client.delete_collection("insights")
    global collection
    collection = chroma_client.get_or_create_collection(
        name="insights",
        metadata={"description": "Insight vectors for personalized feed"},
    )
    print("Vector DB reset complete.")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "stats":
        print(json.dumps(get_stats(), indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "reset":
        reset_database()
    else:
        print("Usage:")
        print("  python semantic_db.py stats   # Show collection stats")
        print("  python semantic_db.py reset   # Clear collection")
