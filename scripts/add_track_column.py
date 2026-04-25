import sqlite3
import os
import sys

DB_PATH = os.path.expanduser('~/aircraft-logger/logs/aircraft.db')

def migrate_db():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(flights)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'track' not in columns:
            print("Adding 'track' column to 'flights' table...")
            cursor.execute("ALTER TABLE flights ADD COLUMN track TEXT")
            conn.commit()
            print("Migration successful! Column 'track' added.")
        else:
            print("Migration not needed: 'track' column already exists.")
            
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == '__main__':
    migrate_db()
