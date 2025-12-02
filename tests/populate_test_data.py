"""
Populate test data for unified feed testing

Creates sample insights, topics, and user follows for testing
"""

import sqlite3
import json
import uuid
from datetime import datetime, timedelta
import random
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)

DB_PATH = os.path.join(PROJECT_ROOT, "insights.db")


# Sample insights by topic
SAMPLE_INSIGHTS = {
    "AI agents": [
        {
            "category": "CASE STUDY",
            "text": "Duolingo grew from 40M to 100M users by making their mascot 'unhinged' on TikTok. The owl character became internet famous through aggressive, meme-worthy content that went viral.",
            "source_url": "https://www.anthropic.com/research/constitutional-ai",
            "source_domain": "anthropic.com",
            "quality_score": 8.5
        },
        {
            "category": "PLAYBOOK",
            "text": "OpenAI's GPT-4 uses 'Constitutional AI' - the model is trained to critique and revise its own responses according to a set of principles. This reduces harmful outputs by 40% compared to GPT-3.5.",
            "source_url": "https://openai.com/research/gpt-4",
            "source_domain": "openai.com",
            "quality_score": 9.0
        },
        {
            "category": "TREND",
            "text": "AI coding assistants now generate 46% of code at companies using GitHub Copilot. Developers report 55% faster task completion for repetitive coding work.",
            "source_url": "https://github.blog/2023-06-27-the-economic-impact-of-the-ai-powered-developer-lifecycle-and-lessons-from-github-copilot/",
            "source_domain": "github.com",
            "quality_score": 8.0
        },
    ],
    "Value Investing": [
        {
            "category": "PLAYBOOK",
            "text": "Buffett's Bank of America investment structure: $5B preferred shares at 6% annual dividend + warrants to buy 700M common shares at $7.14. This 'heads I win, tails I don't lose much' approach protects downside while capturing upside.",
            "source_url": "https://www.berkshirehathaway.com/letters/2021ltr.pdf",
            "source_domain": "berkshirehathaway.com",
            "quality_score": 9.2
        },
        {
            "category": "COUNTERINTUITIVE",
            "text": "Companies with 'boring' businesses (waste management, storage units) outperformed tech stocks by 2.3x from 2000-2020. Low glamour = less competition = sustained high returns.",
            "source_url": "https://www.aqr.com/Insights/Research/Journal-Article/Value-Glamour-and-the-Great-Divide",
            "source_domain": "aqr.com",
            "quality_score": 8.7
        },
        {
            "category": "CASE STUDY",
            "text": "Mohnish Pabrai's 'Heads I win, Tails I don't lose much' framework: Only invest when downside is <10% and upside is >300%. He's achieved 28% annual returns over 20 years using this asymmetric risk approach.",
            "source_url": "https://www.moiinvestments.com/framework",
            "source_domain": "moiinvestments.com",
            "quality_score": 8.9
        },
    ],
    "Gen Z Consumer": [
        {
            "category": "CASE STUDY",
            "text": "Fashion Nova generates $941M in revenue with only 5 physical stores. Their secret: 600-1000 new styles per week, priced 70% lower than competitors, all marketed through Instagram influencers (not traditional ads).",
            "source_url": "https://www.businessinsider.com/fashion-nova-ceo-richard-saghian-interview-2019-5",
            "source_domain": "businessinsider.com",
            "quality_score": 8.8
        },
        {
            "category": "TREND",
            "text": "73% of Gen Z prefers discovering brands through social media over search engines. TikTok has become the new Google for product discovery, with #TikTokMadeMeBuyIt videos generating 4.6B views.",
            "source_url": "https://www.forbes.com/sites/forbesagencycouncil/2023/01/24/how-gen-z-is-changing-marketing-forever/",
            "source_domain": "forbes.com",
            "quality_score": 7.5
        },
        {
            "category": "COUNTERINTUITIVE",
            "text": "Gen Z spends more on 'experiences' than physical products, yet buys clothes more frequently than Millennials. The key: Fast fashion enables constant 'micro-experiences' of newness at low cost.",
            "source_url": "https://www.mckinsey.com/industries/retail/our-insights/the-state-of-fashion-2023",
            "source_domain": "mckinsey.com",
            "quality_score": 8.2
        },
    ],
}


def populate_insights():
    """Populate insights table with sample data"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("📦 Populating insights...")
    
    inserted = 0
    for topic, insights_list in SAMPLE_INSIGHTS.items():
        for insight_data in insights_list:
            insight_id = str(uuid.uuid4())
            
            # Randomize creation date (last 30 days)
            days_ago = random.randint(0, 30)
            created_at = (datetime.now() - timedelta(days=days_ago)).isoformat()
            
            cursor.execute("""
                INSERT INTO insights (
                    id, topic, category, text, source_url, source_domain,
                    quality_score, engagement_score, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                insight_id,
                topic,
                insight_data['category'],
                insight_data['text'],
                insight_data['source_url'],
                insight_data['source_domain'],
                insight_data['quality_score'],
                0.0,  # No engagement yet
                created_at
            ))
            inserted += 1
    
    conn.commit()
    conn.close()
    
    print(f"✅ Inserted {inserted} insights")


def populate_topics():
    """Create topic metadata"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("📚 Creating topic metadata...")
    
    for topic in SAMPLE_INSIGHTS.keys():
        # Count insights for this topic
        cursor.execute("""
            SELECT COUNT(*) FROM insights WHERE topic = ?
        """, (topic,))
        insight_count = cursor.fetchone()[0]
        
        cursor.execute("""
            INSERT OR REPLACE INTO topics (topic, insight_count, follower_count)
            VALUES (?, ?, 0)
        """, (topic, insight_count))
    
    conn.commit()
    conn.close()
    
    print(f"✅ Created {len(SAMPLE_INSIGHTS)} topics")


def add_test_user_follows():
    """Add test user follows"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("👤 Adding user follows...")
    
    # User follows AI agents and Value Investing
    test_user_id = "default"
    follow_topics = ["AI agents", "Value Investing"]
    
    for topic in follow_topics:
        cursor.execute("""
            INSERT OR IGNORE INTO user_topics (user_id, topic, followed_at)
            VALUES (?, ?, ?)
        """, (test_user_id, topic, datetime.now().isoformat()))
        
        # Increment follower count
        cursor.execute("""
            UPDATE topics SET follower_count = follower_count + 1
            WHERE topic = ?
        """, (topic,))
    
    conn.commit()
    conn.close()
    
    print(f"✅ User following {len(follow_topics)} topics")


def simulate_engagement():
    """Simulate some user engagement"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("💚 Simulating engagement...")
    
    # Get some random insights
    cursor.execute("""
        SELECT id FROM insights ORDER BY RANDOM() LIMIT 5
    """)
    
    insight_ids = [row[0] for row in cursor.fetchall()]
    
    test_user_id = "default"
    actions = ['like', 'save', 'view']
    
    for insight_id in insight_ids:
        # Random actions
        for action in random.sample(actions, random.randint(1, 3)):
            engagement_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT OR IGNORE INTO user_engagement (id, user_id, insight_id, action, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (engagement_id, test_user_id, insight_id, action, datetime.now().isoformat()))
    
    conn.commit()
    
    # Update engagement scores
    for insight_id in insight_ids:
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT CASE WHEN action = 'view' THEN user_id END) as views,
                COUNT(DISTINCT CASE WHEN action = 'like' THEN user_id END) as likes,
                COUNT(DISTINCT CASE WHEN action = 'save' THEN user_id END) as saves
            FROM user_engagement
            WHERE insight_id = ?
        """, (insight_id,))
        
        row = cursor.fetchone()
        views, likes, saves = row
        
        if views > 0:
            engagement_score = min((likes + saves) / views, 1.0)
            cursor.execute("""
                UPDATE insights SET engagement_score = ? WHERE id = ?
            """, (engagement_score, insight_id))
    
    conn.commit()
    conn.close()
    
    print(f"✅ Simulated engagement for {len(insight_ids)} insights")


def print_summary():
    """Print summary of data"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("\n" + "="*60)
    print("TEST DATA SUMMARY")
    print("="*60)
    
    # Count insights
    cursor.execute("SELECT COUNT(*) FROM insights")
    insight_count = cursor.fetchone()[0]
    print(f"📦 Total insights: {insight_count}")
    
    # Count by topic
    cursor.execute("""
        SELECT topic, COUNT(*) as count
        FROM insights
        GROUP BY topic
        ORDER BY count DESC
    """)
    print("\n📊 Insights by topic:")
    for row in cursor.fetchall():
        print(f"  • {row[0]}: {row[1]}")
    
    # User follows
    cursor.execute("""
        SELECT topic FROM user_topics WHERE user_id = 'default'
    """)
    follows = [row[0] for row in cursor.fetchall()]
    print(f"\n👤 User following: {', '.join(follows)}")
    
    # Engagement
    cursor.execute("""
        SELECT COUNT(*) FROM user_engagement
    """)
    engagement_count = cursor.fetchone()[0]
    print(f"\n💚 Engagement records: {engagement_count}")
    
    print("\n✅ Test data ready!")
    print("="*60)
    print("\nTest the API:")
    print("  GET http://localhost:8000/api/feed/following")
    print("  GET http://localhost:8000/api/feed/for-you")
    print("="*60)
    
    conn.close()


def main():
    """Run all population steps"""
    print("🚀 Populating test data for unified feed...\n")
    
    if not os.path.exists(DB_PATH):
        print("❌ Database not found! Run migration first.")
        return
    
    try:
        populate_insights()
        populate_topics()
        add_test_user_follows()
        simulate_engagement()
        print_summary()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
