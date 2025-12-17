"""Compute topic embeddings and build similarity matrix"""
import sqlite3
import os
import numpy as np
from typing import List, Tuple, Dict
import chromadb
from chromadb.config import Settings

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "insights.db")
CHROMA_PATH = os.path.join(PROJECT_ROOT, "chroma_db")

# Use existing ChromaDB collection (embeddings already computed)
chroma_client = chromadb.PersistentClient(
    path=CHROMA_PATH,
    settings=Settings(
        anonymized_telemetry=False,
        allow_reset=True,
    ),
)
collection = chroma_client.get_or_create_collection(
    name="insights",
    metadata={"description": "Insight vectors for personalized feed"},
)


def compute_topic_embedding(topic: str, db_path: str = DB_PATH) -> np.ndarray:
    """
    Compute topic embedding by averaging embeddings of top 20 insights for this topic.
    Uses existing embeddings from ChromaDB.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get top 20 insights for this topic by quality score
    cursor.execute("""
        SELECT chroma_id FROM insights
        WHERE topic = ? AND chroma_id IS NOT NULL
        ORDER BY quality_score DESC
        LIMIT 20
    """, (topic,))

    chroma_ids = [row[0] for row in cursor.fetchall()]
    conn.close()

    if not chroma_ids:
        # No insights with embeddings for this topic
        print(f"  ⚠️  No embeddings found for topic: {topic}")
        # Return None to skip this topic
        return None

    # Get embeddings from ChromaDB
    try:
        result = collection.get(
            ids=chroma_ids,
            include=['embeddings']
        )

        if not result['embeddings'] or len(result['embeddings']) == 0:
            print(f"  ⚠️  No embeddings returned for topic: {topic}")
            return np.zeros(384)

        # Convert to numpy array and compute mean
        embeddings = np.array(result['embeddings'])
        return np.mean(embeddings, axis=0)

    except Exception as e:
        print(f"  ❌ Error getting embeddings for {topic}: {e}")
        return np.zeros(384)


def build_topic_similarity_index(
    min_similarity: float = 0.7,
    db_path: str = DB_PATH
):
    """
    Pre-compute similarity matrix for all topics.
    Only stores similarities above threshold to save space.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all unique topics that have insights
    cursor.execute("""
        SELECT DISTINCT topic FROM insights
        WHERE is_archived = 0
        ORDER BY topic
    """)
    topics = [row[0] for row in cursor.fetchall()]

    print(f"Computing embeddings for {len(topics)} topics...")

    # Compute embeddings for all topics
    topic_embeddings = {}
    for topic in topics:
        embedding = compute_topic_embedding(topic, db_path)
        topic_embeddings[topic] = embedding
        print(f"  ✓ {topic}")

    print(f"\nBuilding similarity matrix (threshold: {min_similarity})...")

    # Compute pairwise similarities
    similarities_added = 0

    # Clear existing similarities
    cursor.execute("DELETE FROM topic_similarities")

    for i, topic_a in enumerate(topics):
        for topic_b in topics[i+1:]:  # Only compute upper triangle
            # Cosine similarity
            embedding_a = topic_embeddings[topic_a]
            embedding_b = topic_embeddings[topic_b]

            similarity = cosine_similarity(embedding_a, embedding_b)

            # Only store if above threshold
            if similarity >= min_similarity:
                # Store both directions for easy lookup
                cursor.execute("""
                    INSERT INTO topic_similarities (topic_a, topic_b, similarity_score)
                    VALUES (?, ?, ?)
                """, (topic_a, topic_b, similarity))

                cursor.execute("""
                    INSERT INTO topic_similarities (topic_a, topic_b, similarity_score)
                    VALUES (?, ?, ?)
                """, (topic_b, topic_a, similarity))

                similarities_added += 2
                print(f"  {topic_a} ↔ {topic_b}: {similarity:.3f}")

    conn.commit()
    conn.close()

    print(f"\n✅ Similarity index built!")
    print(f"  Total topic pairs stored: {similarities_added // 2}")
    print(f"  Total similarity records: {similarities_added}")


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Calculate cosine similarity between two vectors"""
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def get_similar_topics(
    topic: str,
    min_similarity: float = 0.7,
    db_path: str = DB_PATH
) -> List[Tuple[str, float]]:
    """
    Get topics similar to given topic.
    Returns list of (topic, similarity_score) tuples, sorted by similarity desc.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT topic_b, similarity_score
        FROM topic_similarities
        WHERE topic_a = ? AND similarity_score >= ?
        ORDER BY similarity_score DESC
    """, (topic, min_similarity))

    similar = cursor.fetchall()
    conn.close()

    return similar


def load_all_topic_similarities(db_path: str = DB_PATH) -> Dict[str, List[Tuple[str, float]]]:
    """
    Load entire topic similarity matrix into memory for fast lookup.
    Returns dict mapping topic -> list of (similar_topic, similarity_score).
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT topic_a, topic_b, similarity_score
        FROM topic_similarities
        ORDER BY topic_a, similarity_score DESC
    """)

    similarities = {}
    for topic_a, topic_b, score in cursor.fetchall():
        if topic_a not in similarities:
            similarities[topic_a] = []
        similarities[topic_a].append((topic_b, score))

    conn.close()
    return similarities


if __name__ == "__main__":
    # Build similarity index
    build_topic_similarity_index(min_similarity=0.7)

    # Test queries
    print("\n--- Testing similar topic queries ---")

    test_topics = ["artificial intelligence", "machine learning", "startup funding trends"]

    for topic in test_topics:
        similar = get_similar_topics(topic, min_similarity=0.7)
        print(f"\n{topic}:")
        for sim_topic, score in similar[:5]:  # Top 5
            print(f"  {sim_topic}: {score:.3f}")
