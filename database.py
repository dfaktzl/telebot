import aiosqlite
from config import DB_PATH, BLACK_CHANNEL_ID
import os

REP_DB_PATH = "reputation.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                is_verified INTEGER DEFAULT 0,
                vouched_by INTEGER DEFAULT NULL,
                vouch_count INTEGER DEFAULT 0,
                join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active',
                kick_count INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS username_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                old_username TEXT,
                new_username TEXT,
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        
        defaults = [
            ('white_channel_id', '-1003769928131'),
            ('black_channel_id', str(BLACK_CHANNEL_ID)),
            ('invite_link', 'None'),
            ('emergency_mode', '0'),
            ('timer_end', '0'),
            ('admin_name', 'Admin Team'),
            ('admin_contact', '@VouchCheckerBot'),
            ('admin_email', 'PerthEntryBot@Protonmail.com'),
            ('vouch_limit', '1'),
            ('broadcast_delay', '0.15'),
            ('auto_vouch_enabled', '1'),
            ('illegal_detection_enabled', '1'),
            ('min_sentiment_score', '2'),
            ('min_sentiment_words', '5'),
            ('positive_keywords', 'vouch,legit,trusted,reliable,recommend,genuine,smooth,safe,fast,quick,delivered,confirmed,verified,excellent,perfect,amazing,solid,consistent,professional,quality,real deal,top notch,on time,came through,no issues,all good,thumbs up,big ups,massive vouch,fat vouch,huge vouch,big vouch,honest'),
            ('negative_keywords', 'scam,scammer,scammed,fraud,fraudster,fake,liar,thief,stole,ripped,ripoff,rip off,ripped off,sketchy,shady,dodgy,ghosted,blocked,never delivered,took my money,didnt deliver,avoid,warning,beware,dont trust,not legit,ran off,disappeared,selective scammer'),
            ('blacklist_terms', 'counterfeit,cashout,carding,fullz,dumps,cvv,fake money,prop money,bank logs,cloned cards,paypal,whatsapp'),
            ('drug_terms', 'cocaine,heroin,meth,methamphetamine,mdma,ecstasy,molly,lsd,acid,ketamine,fentanyl,xanax,alprazolam,oxy,oxycodone,percs,percocet,codeine,morphine,opium,tramadol,hydrocodone,vicodin,adderall,ritalin,shrooms,psilocybin,dmt,pcp,ghb,rohypnol,crack,coke,speed,ice,crystal,weed,marijuana,cannabis,thc,edibles,plug,vendor,wickr'),
            ('health_check_interval', '300'),
            ('sync_interval', '86400'),
            ('msg_start', '🛡️ **Welcome to the Perimeter.**\n\nTo access our high-security community, you must be verified by an existing trusted member.\n\n👤 **Status:** {status}\n\n_Please send the contact details of your referee or have them /vouch for you._'),
            ('msg_verify_instructions', '📝 **Verification Required**\n\nTo enter, a verified member must vouch for you using:\n`/vouch {user_id}`\n\nOnce vouched, use /link to get your invite.'),
            ('msg_access_granted', '🎉 **Access Granted!**\n\nYour reputation has been confirmed. You are now a verified member of the community.'),
            ('msg_access_denied', '🚫 **Access Denied**\n\nYour verification is currently inactive or you have been flagged by the security system.'),
            ('msg_blocked', '⛔ **PERMANENT BAN**\n\nYour ID has been matched against our Dangerous User database. You are permanently barred from this community.'),
            ('msg_vouch_success', '✅ **Vouch Recorded**\n────────────────────\nUser: `{identifier}`\nStatus: **VERIFIED**\nReason: _{comment}_\n\n🔄 _Synced daily to @VouchCheckerBot_'),
            ('msg_vouch_revoked', '🚫 **Negative Vouch**\n────────────────────\nUser: `{identifier}`\nStatus: **FLAGGED / UNVERIFIED**\nReason: _{comment}_'),
            ('msg_vouch_usage', 'ℹ️ **Vouch Usage**\n\nReply to a message with `/vouch` or use:\n`/vouch <ID or @username> [reason]`'),
            ('msg_vouch_error', '❌ **Process Failed**\n\nCould not verify the user. Ensure the ID is correct or the user has interacted with the bot.'),
            ('msg_illegal_warning', '⚠️ **CONTENT WARNING**\n────────────────────\n{user_mention}, please be careful of the words you use in here.\n\n_We are maintaining strict compliance to ensure the longevity of this community._'),
            ('msg_welcome', '👋 **Welcome, {user_mention}!**\n────────────────────\nYou have entered a high-trust community. Please read the rules and conduct yourself accordingly.\n\n_This message will self-destruct in {timer} seconds._'),
            ('welcome_delete_timer', '600'),
            ('enforcement_enabled', '1')
        ]
        for key, value in defaults:
            await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))

        # Migration: Ensure new columns exist in users table
        cursor = await db.execute("PRAGMA table_info(users)")
        cols_found = [row[1] for row in await cursor.fetchall()]
        
        migration_needed = [
            ('vouched_by', 'INTEGER DEFAULT NULL'),
            ('vouch_count', 'INTEGER DEFAULT 0'),
            ('status', "TEXT DEFAULT 'active'"),
            ('kick_count', 'INTEGER DEFAULT 0'),
        ]
        
        for col_name, col_type in migration_needed:
            if col_name not in cols_found:
                await db.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
        
        await db.commit()

async def get_setting(key, default=None):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else default

async def set_setting(key, value):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
        await db.commit()

async def get_user_by_id_or_username(identifier):
    async with aiosqlite.connect(DB_PATH) as db:
        ident_str = str(identifier).strip().lstrip('@')
        if ident_str.isdigit():
            async with db.execute("SELECT * FROM users WHERE user_id = ?", (int(ident_str),)) as cursor:
                return await cursor.fetchone()
        else:
            async with db.execute("SELECT * FROM users WHERE username = ?", (ident_str,)) as cursor:
                return await cursor.fetchone()

async def add_or_update_user(user_id, username):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT username FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
        if row:
            old_username = row[0]
            if old_username != username:
                await db.execute("INSERT INTO username_history (user_id, old_username, new_username) VALUES (?, ?, ?)", (user_id, old_username, username))
                await db.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
        else:
            await db.execute("INSERT INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
        await db.commit()

async def get_username_history(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT old_username, new_username, changed_at FROM username_history WHERE user_id = ? ORDER BY changed_at DESC", (user_id,)) as cursor:
            return await cursor.fetchall()

async def verify_user(identifier, status=1, vouched_by=None):
    ident_str = str(identifier).strip().lstrip('@')
    user = await get_user_by_id_or_username(ident_str)
    target_uid = None
    if user:
        target_uid = user[0]
    elif ident_str.isdigit():
        target_uid = int(ident_str)
        username = f"User_{target_uid}"
        if os.path.exists(REP_DB_PATH):
            async with aiosqlite.connect(REP_DB_PATH) as db:
                async with db.execute("SELECT username FROM users WHERE id = ?", (target_uid,)) as cursor:
                    row = await cursor.fetchone()
                    if row: username = row[0]
        await add_or_update_user(target_uid, username)
    else:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        status_text = 'active' if status == 1 else 'flagged'
        await db.execute("UPDATE users SET is_verified = ?, vouched_by = ?, status = ? WHERE user_id = ?", (status, vouched_by, status_text, target_uid))
        await db.commit()
    return target_uid

async def get_reputation_score(user_id):
    if not os.path.exists(REP_DB_PATH): return 0
    async with aiosqlite.connect(REP_DB_PATH) as db:
        async with db.execute("SELECT vouches FROM users WHERE id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def is_dangerous_user(user_id):
    if not os.path.exists(REP_DB_PATH): return False, None
    async with aiosqlite.connect(REP_DB_PATH) as db:
        async with db.execute("SELECT is_flagged, is_dangerous, flag_reason FROM users WHERE id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row and (row[0] == 1 or row[1] == 1): return True, row[2]
    return False, None

async def get_all_verified_users():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users WHERE is_verified = 1") as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

async def get_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            total_members = (await cursor.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE is_verified = 1") as cursor:
            verified_users = (await cursor.fetchone())[0]
        return total_members, verified_users

async def get_kick_count(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT kick_count FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def increment_kick_count(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        # Ensure user exists first
        async with db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)) as cursor:
            if not await cursor.fetchone():
                await db.execute("INSERT INTO users (user_id, username, kick_count) VALUES (?, ?, 1)", (user_id, f"User_{user_id}"))
            else:
                await db.execute("UPDATE users SET kick_count = kick_count + 1 WHERE user_id = ?", (user_id,))
        await db.commit()

async def get_all_known_user_ids():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users") as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]
