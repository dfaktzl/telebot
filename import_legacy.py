import re
import asyncio
import aiosqlite

FILE_PATH = r"C:\Users\defak\OneDrive\Desktop\vouches_export_50800.txt"
DB_PATH = "gatekeeper.db"

async def run_import():
    print(f"Starting optimized import from {FILE_PATH}...")
    
    try:
        with open(FILE_PATH, 'r', encoding='utf-8', errors='ignore') as f:
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
            
            async with aiosqlite.connect(DB_PATH) as db:
                await db.executemany(
                    "INSERT OR REPLACE INTO users (user_id, username, is_verified, status) VALUES (?, ?, ?, ?)",
                    data
                )
                await db.commit()

    except Exception as e:
        print(f"Error: {e}")
        return

    print(f"✅ Import complete! {len(unique_verified)} users are now verified.")

if __name__ == "__main__":
    asyncio.run(run_import())
