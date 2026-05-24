import aiosqlite
from config import DB_PATH, BLACK_CHANNEL_ID
import os
from contextlib import asynccontextmanager

@asynccontextmanager
async def connect_db():
    async with aiosqlite.connect(DB_PATH, timeout=5.0) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA busy_timeout=5000")
        yield db

async def init_db():
    async with connect_db() as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                is_verified INTEGER DEFAULT 0,
                vouched_by INTEGER DEFAULT NULL,
                vouch_count INTEGER DEFAULT 0,
                join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active',
                kick_count INTEGER DEFAULT 0,
                in_gatekeeper INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS username_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                old_username TEXT,
                new_username TEXT,
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS market_verify_tickets (
                user_id INTEGER,
                admin_message_id INTEGER,
                user_message_id INTEGER,
                status TEXT DEFAULT 'pending',
                admin_chat_id INTEGER DEFAULT 834606708,
                channel_message_id INTEGER DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS market_verify_message_map (
                message_id INTEGER PRIMARY KEY,
                user_id INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admin_help_tickets (
                user_id INTEGER,
                admin_message_id INTEGER,
                user_message_id INTEGER,
                status TEXT DEFAULT 'pending',
                admin_chat_id INTEGER DEFAULT 834606708,
                channel_message_id INTEGER DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admin_help_message_map (
                message_id INTEGER PRIMARY KEY,
                user_id INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admin_help_chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                sender_name TEXT,
                sender_role TEXT,
                message_text TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS blacklist_users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                reason TEXT,
                banned_by TEXT,
                banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            ('admin_email', 'TryForgetThis@proton.me'),
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
            ('msg_start', '🚪 <b>THE LOCKED DOOR (Gatekeeper)</b>\n──────────────────────────\nWelcome to the high-security gateway. This bot acts as the automated gatekeeper and reputation synchronization module for our private, high-trust community.\n\n<b>🔒 WHAT DOES THIS BOT DO?</b>\n• 🟢 <b>Automated Whitelisting:</b> Verifies membership in our main channel to grant invite links.\n• 🔴 <b>Sybil & Fraud Prevention:</b> Continuously audits member lists to block dangerous or unverified users.\n• 🔵 <b>Reputation Tracking:</b> Operates an independent, backed-up reputation database linked to unique User IDs, which frequently syncs with <b>@PerthVouchBot</b> (holding 50,000+ OG vouches).\n\n──────────────────────────\n<b>👤 YOUR PROFILE DETAILS:</b>\n• 🆔 <b>User ID:</b> <code>{user_id}</code>\n• 🏷️ <b>Username:</b> {username}\n• 📝 <b>Display Name:</b> <code>{full_name}</code>\n• ⚡ <b>Verified Status:</b> {status}\n• ⏱️ <b>Current Time:</b> <code>{current_time}</code>\n\n──────────────────────────\n<b>🔑 HOW TO ENTER & VERIFY:</b>\nIf your status is currently <b>⏳ UNVERIFIED</b>:\n\n1️⃣ <b>Referrer Chain (Main Entrance):</b>\nIf you are a well-vouched, long-standing member of the community, you can message <b>@TryForgetThis</b> directly to request manual verification. This secure gate is built on a rigorous, high-level <i>operational security (OpSec) referrer chain</i>.\n👉 <i>Please make sure to send any usernames of active members who can vouch for you.</i>\n\n2️⃣ <b>Community Vouching (Alternative):</b>\nAnother way is to have other trusted members of the community <code>/vouch {user_id}</code> for you.'),
            ('msg_verify_instructions', '🔑 <b>VERIFICATION REQUIRED</b>\n──────────────────────────\nTo gain entry to the social/market channel, you must first be verified by a trusted member.\n\n📝 <b>How to get vouched:</b>\nHave an active, verified member run this command in the bot:\n<code>/vouch {user_id}</code>\n\n📌 <i>Once they vouch for you, run /link again to get your invite.</i>'),
            ('msg_access_granted', '🟢 <b>ACCESS GRANTED</b>\n──────────────────────────\n🎉 Congratulations! Your reputation has been confirmed. You are a verified member of our high-trust network.'),
            ('msg_access_denied', '❌ <b>ACCESS DENIED</b>\n──────────────────────────\nOnly verified community members have permission to perform this action.'),
            ('msg_blocked', '🚪 <b>THE LOCKED DOOR (Gatekeeper)</b>\n──────────────────────────\n⛔ <b>PERMANENT BAN ALERT</b>\n\nYour unique Telegram ID has been matched against our Dangerous User database. You are permanently barred from this community.\n\n❌ <i>This security decision is final and non-negotiable.</i>'),
            ('msg_vouch_success', '✅ <b>VOUCH RECORDED</b>\n──────────────────────────\n• 👤 <b>User:</b> <code>{identifier}</code>\n• ⚡ <b>Status:</b> <b>VERIFIED</b>\n• 💬 <b>Reason:</b> <i>{comment}</i>\n\n🔄 <i>Synced automatically to @PerthVouchBot</i>'),
            ('msg_vouch_revoked', '🚫 <b>VOUCH REVOKED / FLAGGED</b>\n──────────────────────────\n• 👤 <b>User:</b> <code>{identifier}</code>\n• ⚡ <b>Status:</b> <b>FLAGGED / UNVERIFIED</b>\n• 💬 <b>Reason:</b> <i>{comment}</i>\n\n⚠️ <i>Security status updated across all channels.</i>'),
            ('msg_vouch_notification', '🎉 <b>CONGRATULATIONS!</b>\n──────────────────────────\nYou have been vouched for by a trusted member and successfully verified.\n\n🔗 Use the <code>/link</code> command here to claim your invitation to the chat!'),
            ('msg_unvouch_notification', '⚠️ <b>SECURITY ALERT</b>\n──────────────────────────\nYour community verification has been revoked by a trusted member.\n\n🚫 You have been flagged as unverified and access has been restricted.'),
            ('msg_vouch_usage', 'ℹ️ <b>VOUCH COMMAND USAGE</b>\n──────────────────────────\nReply to a user\'s message with <code>/vouch</code> or run:\n<code>/vouch &lt;ID or @username&gt; [reason]</code>'),
            ('msg_vouch_error', '❌ <b>VOUCHING FAILED</b>\n──────────────────────────\nCould not process the vouch. Please verify the ID is correct and ensure the user has initiated a conversation with the bot first.'),
            ('msg_illegal_warning', '⚠️ <b>CONTENT &amp; POLICY WARNING</b>\n──────────────────────────\n{user_mention}, please be careful with the terminology you use.\n\n🚫 We maintain absolute compliance to protect the longevity of this high-trust group. Repeated violations will result in an automated ban.'),
            ('msg_welcome', '👋 <b>Welcome, {user_mention}!</b>\n──────────────────────────\nYou have entered a high-trust, whitelisted community. Please conduct yourself respectfully and read the pinned rules.'),
            ('msg_kick_notification', '⚠️ <b>{display_name}</b> has been removed from this channel.\n──────────────────────────\n📋 <b>Reason:</b> Not a verified member of our main group.\nℹ️ Join our main group first to gain access here.\n\n<i>This is their first warning. A second attempt will result in a permanent ban.</i>'),
            ('msg_ban_notification', '🚫 <b>{display_name}</b> has been permanently banned.\n──────────────────────────\n📋 <b>Reason:</b> Repeated entry without main group verification.\n❌ <i>This decision is final.</i>'),
            ('welcome_delete_timer', '600'),
            ('kick_delete_timer', '300'),
            ('ban_delete_timer', '600'),
            ('enforcement_enabled', '1')
        ]
        for key, value in defaults:
            await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))

        # Migration: Ensure all columns from both bots exist in the users table
        cursor = await db.execute("PRAGMA table_info(users)")
        cols_found = [row[1] for row in await cursor.fetchall()]
        
        migration_needed = [
            ('first_name', 'TEXT'),
            ('last_name', 'TEXT'),
            ('vouches', 'INTEGER DEFAULT 0'),
            ('messages_count', 'INTEGER DEFAULT 0'),
            ('is_flagged', 'INTEGER DEFAULT 0'),
            ('flag_reason', 'TEXT'),
            ('is_sex_worker', 'INTEGER DEFAULT 0'),
            ('is_dangerous', 'INTEGER DEFAULT 0'),
            ('first_seen', 'TIMESTAMP'),
            ('last_seen', 'TIMESTAMP'),
            ('is_verified', 'INTEGER DEFAULT 0'),
            ('vouched_by', 'INTEGER DEFAULT NULL'),
            ('vouch_count', 'INTEGER DEFAULT 0'),
            ('status', "TEXT DEFAULT 'active'"),
            ('kick_count', 'INTEGER DEFAULT 0'),
            ('in_gatekeeper', 'INTEGER DEFAULT 0'),
        ]
        
        for col_name, col_type in migration_needed:
            if col_name not in cols_found:
                await db.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")

        # Migration for market_verify_tickets
        cursor = await db.execute("PRAGMA table_info(market_verify_tickets)")
        cols_found = [row[1] for row in await cursor.fetchall()]
        if 'admin_chat_id' not in cols_found:
            await db.execute("ALTER TABLE market_verify_tickets ADD COLUMN admin_chat_id INTEGER DEFAULT 834606708")
        if 'channel_message_id' not in cols_found:
            await db.execute("ALTER TABLE market_verify_tickets ADD COLUMN channel_message_id INTEGER DEFAULT NULL")

        # Migration for admin_help_tickets
        cursor = await db.execute("PRAGMA table_info(admin_help_tickets)")
        cols_found = [row[1] for row in await cursor.fetchall()]
        if 'admin_chat_id' not in cols_found:
            await db.execute("ALTER TABLE admin_help_tickets ADD COLUMN admin_chat_id INTEGER DEFAULT 834606708")
        if 'channel_message_id' not in cols_found:
            await db.execute("ALTER TABLE admin_help_tickets ADD COLUMN channel_message_id INTEGER DEFAULT NULL")
        
        await db.commit()

async def get_setting(key, default=None):
    async with connect_db() as db:
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else default

async def set_setting(key, value):
    async with connect_db() as db:
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
        await db.commit()

async def get_user_by_id_or_username(identifier):
    async with connect_db() as db:
        ident_str = str(identifier).strip().lstrip('@')
        if ident_str.isdigit():
            async with db.execute("SELECT * FROM users WHERE id = ?", (int(ident_str),)) as cursor:
                return await cursor.fetchone()
        else:
            async with db.execute("SELECT * FROM users WHERE username = ?", (ident_str,)) as cursor:
                return await cursor.fetchone()

async def add_or_update_user(user_id, username, first_name=None, last_name=None):
    async with connect_db() as db:
        async with db.execute("SELECT username, first_name, last_name FROM users WHERE id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
        if row:
            old_username = row[0]
            old_first = row[1]
            old_last = row[2]
            
            updates = []
            params = []
            
            if old_username != username:
                await db.execute("INSERT INTO username_history (user_id, old_username, new_username) VALUES (?, ?, ?)", (user_id, old_username, username))
                updates.append("username = ?")
                params.append(username)
            if first_name and old_first != first_name:
                updates.append("first_name = ?")
                params.append(first_name)
            if last_name and old_last != last_name:
                updates.append("last_name = ?")
                params.append(last_name)
                
            if updates:
                params.append(user_id)
                await db.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)
        else:
            await db.execute("INSERT INTO users (id, username, first_name, last_name) VALUES (?, ?, ?, ?)", (user_id, username, first_name, last_name))
        await db.commit()

async def get_username_history(user_id):
    async with connect_db() as db:
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
        async with connect_db() as db:
            async with db.execute("SELECT username FROM users WHERE id = ?", (target_uid,)) as cursor:
                row = await cursor.fetchone()
                if row: username = row[0]
        await add_or_update_user(target_uid, username)
    else:
        return False
    async with connect_db() as db:
        status_text = 'active' if status == 1 else 'flagged'
        await db.execute("UPDATE users SET is_verified = ?, vouched_by = ?, status = ? WHERE id = ?", (status, vouched_by, status_text, target_uid))
        await db.commit()
    return target_uid

async def get_reputation_score(user_id):
    async with connect_db() as db:
        async with db.execute("SELECT vouches FROM users WHERE id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def is_dangerous_user(user_id):
    async with connect_db() as db:
        async with db.execute("SELECT is_flagged, is_dangerous, flag_reason FROM users WHERE id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row and (row[0] == 1 or row[1] == 1): return True, row[2]
    return False, None

async def get_all_verified_users():
    async with connect_db() as db:
        async with db.execute("SELECT id FROM users WHERE is_verified = 1") as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

async def get_stats():
    async with connect_db() as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            total_members = (await cursor.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE is_verified = 1") as cursor:
            verified_users = (await cursor.fetchone())[0]
        return total_members, verified_users

async def get_kick_count(user_id):
    async with connect_db() as db:
        async with db.execute("SELECT kick_count FROM users WHERE id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def increment_kick_count(user_id):
    async with connect_db() as db:
        # Ensure user exists first
        async with db.execute("SELECT id FROM users WHERE id = ?", (user_id,)) as cursor:
            if not await cursor.fetchone():
                await db.execute("INSERT INTO users (id, username, kick_count) VALUES (?, ?, 1)", (user_id, f"User_{user_id}"))
            else:
                await db.execute("UPDATE users SET kick_count = kick_count + 1 WHERE id = ?", (user_id,))
        await db.commit()

async def get_all_known_user_ids():
    async with connect_db() as db:
        async with db.execute("SELECT id FROM users") as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

async def update_user_gatekeeper_status(user_id, in_gatekeeper):
    async with connect_db() as db:
        await db.execute("UPDATE users SET in_gatekeeper = ? WHERE id = ?", (in_gatekeeper, user_id))
        await db.commit()


# ═══════════════════════════════════════════════════════════════════════════════
#  MARKET VERIFICATION TICKETS HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

async def create_market_verify_ticket(user_id: int, admin_message_id: int, user_message_id: int, channel_message_id: int = None):
    async with connect_db() as db:
        # Mark previous pending tickets for this user as superseded
        await db.execute(
            "UPDATE market_verify_tickets SET status = 'superseded' WHERE user_id = ? AND status = 'pending'",
            (user_id,)
        )
        await db.execute(
            "INSERT INTO market_verify_tickets (user_id, admin_message_id, user_message_id, channel_message_id, status) VALUES (?, ?, ?, ?, 'pending')",
            (user_id, admin_message_id, user_message_id, channel_message_id)
        )
        await db.commit()

async def get_pending_ticket_by_user(user_id: int):
    async with connect_db() as db:
        async with db.execute(
            "SELECT * FROM market_verify_tickets WHERE user_id = ? AND status = 'pending' ORDER BY created_at DESC LIMIT 1",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None

async def get_user_id_by_admin_message(admin_message_id: int):
    async with connect_db() as db:
        async with db.execute(
            "SELECT user_id FROM market_verify_message_map WHERE message_id = ?",
            (admin_message_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def add_market_message_mapping(message_id: int, user_id: int):
    async with connect_db() as db:
        await db.execute(
            "INSERT OR REPLACE INTO market_verify_message_map (message_id, user_id) VALUES (?, ?)",
            (message_id, user_id)
        )
        await db.commit()

async def update_ticket_last_messages(user_id: int, admin_chat_id: int = None, admin_message_id: int = None, user_message_id: int = None):
    async with connect_db() as db:
        if admin_chat_id is not None:
            await db.execute(
                "UPDATE market_verify_tickets SET admin_chat_id = ? WHERE user_id = ? AND status = 'pending'",
                (admin_chat_id, user_id)
            )
        if admin_message_id is not None:
            await db.execute(
                "UPDATE market_verify_tickets SET admin_message_id = ? WHERE user_id = ? AND status = 'pending'",
                (admin_message_id, user_id)
            )
        if user_message_id is not None:
            await db.execute(
                "UPDATE market_verify_tickets SET user_message_id = ? WHERE user_id = ? AND status = 'pending'",
                (user_message_id, user_id)
            )
        await db.commit()

async def verify_market_ticket(user_id: int):
    async with connect_db() as db:
        await db.execute(
            "UPDATE market_verify_tickets SET status = 'verified' WHERE user_id = ? AND status = 'pending'",
            (user_id,)
        )
        await db.commit()

async def bind_market_ticket_to_discussion(channel_message_id: int, discussion_chat_id: int, discussion_message_id: int):
    async with connect_db() as db:
        # Find user_id associated with this channel message ID
        async with db.execute(
            "SELECT user_id FROM market_verify_tickets WHERE channel_message_id = ? AND status = 'pending' ORDER BY created_at DESC LIMIT 1",
            (channel_message_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                user_id = row[0]
                # Update ticket's admin_chat_id and admin_message_id
                await db.execute(
                    "UPDATE market_verify_tickets SET admin_chat_id = ?, admin_message_id = ? WHERE user_id = ? AND status = 'pending'",
                    (discussion_chat_id, discussion_message_id, user_id)
                )
                await db.commit()
                return user_id
            return None


# ═══════════════════════════════════════════════════════════════════════════════
#  ADMIN HELP / SUPPORT TICKETS HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

async def create_admin_help_ticket(user_id: int, admin_message_id: int, user_message_id: int, channel_message_id: int = None):
    async with connect_db() as db:
        # Mark previous pending help tickets for this user as superseded
        await db.execute(
            "UPDATE admin_help_tickets SET status = 'superseded' WHERE user_id = ? AND status = 'pending'",
            (user_id,)
        )
        await db.execute(
            "INSERT INTO admin_help_tickets (user_id, admin_message_id, user_message_id, channel_message_id, status) VALUES (?, ?, ?, ?, 'pending')",
            (user_id, admin_message_id, user_message_id, channel_message_id)
        )
        await db.commit()

async def get_pending_help_ticket_by_user(user_id: int):
    async with connect_db() as db:
        async with db.execute(
            "SELECT * FROM admin_help_tickets WHERE user_id = ? AND status = 'pending' ORDER BY created_at DESC LIMIT 1",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None

async def get_user_id_by_help_message(admin_message_id: int):
    async with connect_db() as db:
        async with db.execute(
            "SELECT user_id FROM admin_help_message_map WHERE message_id = ?",
            (admin_message_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def add_help_message_mapping(message_id: int, user_id: int):
    async with connect_db() as db:
        await db.execute(
            "INSERT OR REPLACE INTO admin_help_message_map (message_id, user_id) VALUES (?, ?)",
            (message_id, user_id)
        )
        await db.commit()

async def update_help_ticket_last_messages(user_id: int, admin_chat_id: int = None, admin_message_id: int = None, user_message_id: int = None):
    async with connect_db() as db:
        if admin_chat_id is not None:
            await db.execute(
                "UPDATE admin_help_tickets SET admin_chat_id = ? WHERE user_id = ? AND status = 'pending'",
                (admin_chat_id, user_id)
            )
        if admin_message_id is not None:
            await db.execute(
                "UPDATE admin_help_tickets SET admin_message_id = ? WHERE user_id = ? AND status = 'pending'",
                (admin_message_id, user_id)
            )
        if user_message_id is not None:
            await db.execute(
                "UPDATE admin_help_tickets SET user_message_id = ? WHERE user_id = ? AND status = 'pending'",
                (user_message_id, user_id)
            )
        await db.commit()

async def close_admin_help_ticket(user_id: int):
    async with connect_db() as db:
        await db.execute(
            "UPDATE admin_help_tickets SET status = 'resolved' WHERE user_id = ? AND status = 'pending'",
            (user_id,)
        )
        await db.commit()

async def bind_help_ticket_to_discussion(channel_message_id: int, discussion_chat_id: int, discussion_message_id: int):
    async with connect_db() as db:
        # Find user_id associated with this channel message ID
        async with db.execute(
            "SELECT user_id FROM admin_help_tickets WHERE channel_message_id = ? AND status = 'pending' ORDER BY created_at DESC LIMIT 1",
            (channel_message_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                user_id = row[0]
                # Update ticket's admin_chat_id and admin_message_id
                await db.execute(
                    "UPDATE admin_help_tickets SET admin_chat_id = ?, admin_message_id = ? WHERE user_id = ? AND status = 'pending'",
                    (discussion_chat_id, discussion_message_id, user_id)
                )
                await db.commit()
                return user_id
            return None


# ═══════════════════════════════════════════════════════════════════════════════
#  ADMIN HELP / SUPPORT CHAT HISTORY HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

async def add_help_chat_message(user_id: int, sender_name: str, sender_role: str, message_text: str):
    async with connect_db() as db:
        await db.execute(
            "INSERT INTO admin_help_chat_history (user_id, sender_name, sender_role, message_text) VALUES (?, ?, ?, ?)",
            (user_id, sender_name, sender_role, message_text)
        )
        await db.commit()

async def get_help_chat_history(user_id: int):
    async with connect_db() as db:
        async with db.execute(
            "SELECT sender_name, sender_role, message_text, timestamp FROM admin_help_chat_history WHERE user_id = ? ORDER BY timestamp ASC",
            (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def delete_help_chat_history(user_id: int):
    async with connect_db() as db:
        await db.execute("DELETE FROM admin_help_chat_history WHERE user_id = ?", (user_id,))
        await db.commit()
