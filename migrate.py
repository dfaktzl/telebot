import sqlite3

def migrate():
    conn = sqlite3.connect('gatekeeper.db')
    cursor = conn.cursor()
    
    columns = [
        ('vouched_by', 'INTEGER DEFAULT NULL'),
        ('vouch_count', 'INTEGER DEFAULT 0'),
        ('status', "TEXT DEFAULT 'active'")
    ]
    
    for col_name, col_type in columns:
        try:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
            print(f"✅ Added column: {col_name}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print(f"ℹ️ Column already exists: {col_name}")
            else:
                print(f"❌ Error adding {col_name}: {e}")
                
    conn.commit()
    conn.close()
    print("🚀 Migration complete.")

if __name__ == "__main__":
    migrate()
