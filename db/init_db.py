"""
Initialize the SQLite database with the schema
Run this before starting the backend server
"""

import sqlite3
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # Go up to project root
DB_PATH = os.path.join(PROJECT_ROOT, "insights.db")
SCHEMA_PATH = os.path.join(PROJECT_ROOT, "db", "schema.sql")

def init_database():
    """Initialize database with schema"""
    print(f"Initializing database at: {DB_PATH}")
    
    # Check if schema file exists
    if not os.path.exists(SCHEMA_PATH):
        print(f"❌ Schema file not found at: {SCHEMA_PATH}")
        return
    
    # Read schema
    with open(SCHEMA_PATH, 'r') as f:
        schema = f.read()
    
    # Connect and execute
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.executescript(schema)
        conn.commit()
        print("✅ Database initialized successfully")
        
        # Verify user_interests table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_interests'")
        if cursor.fetchone():
            print("✅ user_interests table created")
        else:
            print("❌ user_interests table NOT found")
        
        # Show all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"\n📋 Tables created: {', '.join(tables)}")
        
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    init_database()
