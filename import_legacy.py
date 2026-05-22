import re
import sys
import os
import asyncio
from database import connect_db, init_db

DEFAULT_FILE_PATH = r"C:\Users\defak\OneDrive\Desktop\vouches_export_50800.txt"

async def run_import():
    file_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_FILE_PATH
    print(f"Starting optimized import from {file_path}...")
    
    if not os.path.exists(file_path):
        print(f"❌ Legacy file not found: {file_path}")
        return

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            
            chunks = content.split("------------------------------")
            print(f"Total chunks found: {len(chunks)}")
            
            unique_verified = {} # id -> name
            
            # Regex for new format
            to_pattern = re.compile(r"TO:.*?\((\d+)\)", re.DOTALL)
            val_pattern = re.compile(r"VAL:\s*([+-]\d+)")
            name_pattern = re.compile(r"TO:\s*(.*?)\s*\(")
            
            # Regex for legacy format
            legacy_id_pattern = re.compile(r"\[Legacy #\d+\] .*? ID:(\d+)")
            legacy_user_pattern = re.compile(r"\[Legacy #\d+\] .*? @(\w+)")

            for chunk in chunks:
                # Check New Format
                to_match = to_pattern.search(chunk)
                val_match = val_pattern.search(chunk)
                if to_match and val_match and int(val_match.group(1)) > 0:
                    uid = int(to_match.group(1))
                    name_match = name_pattern.search(chunk)
                    name = name_match.group(1).strip() if name_match else f"User_{uid}"
                    unique_verified[uid] = name
                
                # Check Legacy Format
                leg_id_match = legacy_id_pattern.search(chunk)
                if leg_id_match:
                    uid = int(leg_id_match.group(1))
                    if uid not in unique_verified:
                        unique_verified[uid] = f"Legacy_{uid}"
                
                leg_user_match = legacy_user_pattern.search(chunk)
                if leg_user_match:
                    text_id_match = re.search(r"\[(\d+)\]", chunk)
                    if text_id_match:
                        uid = int(text_id_match.group(1))
                        unique_verified[uid] = leg_user_match.group(1)

            print(f"Extracted {len(unique_verified)} unique verified records. Committing to database...")
            
            data = [(uid, name, 1, 'active') for uid, name in unique_verified.items()]
            
            # Initialize database migrations/tables first
            print("Ensuring database schema is fully initialized and migrated...")
            await init_db()
            
            async with connect_db() as db:
                await db.executemany(
                    "INSERT OR REPLACE INTO users (user_id, username, is_verified, status) VALUES (?, ?, ?, ?)",
                    data
                )
                await db.commit()

    except Exception as e:
        print(f"Error during legacy import: {e}")
        return

    print(f"✅ Import complete! {len(unique_verified)} users are now verified.")

if __name__ == "__main__":
    asyncio.run(run_import())
