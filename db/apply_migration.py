"""Apply database migrations"""
import sqlite3
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "insights.db")

def apply_migration(migration_file: str):
    """Apply a SQL migration file"""
    migration_path = os.path.join(PROJECT_ROOT, "db", "migrations", migration_file)

    if not os.path.exists(migration_path):
        print(f"Migration file not found: {migration_path}")
        return False

    print(f"Applying migration: {migration_file}")

    with open(migration_path, 'r') as f:
        sql = f.read()

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.executescript(sql)
        conn.commit()
        conn.close()
        print(f"Successfully applied {migration_file}")
        return True
    except Exception as e:
        print(f"Error applying migration: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        migration_file = sys.argv[1]
    else:
        migration_file = "003_performance_indexes.sql"

    apply_migration(migration_file)
