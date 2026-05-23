import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import BOT_TOKEN, BLACK_CHANNEL_ID, HEALTH_CHECK_INTERVAL, SYNC_INTERVAL
from database import (
    init_db, get_setting, set_setting, get_all_verified_users,
    verify_user, add_or_update_user, get_all_known_user_ids
)
from handlers import common, admin, logger as log_handler, reputation
from handlers import enforcement
from utils.helpers import is_black_channel_member, safe_broadcast

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot & Dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Background Tasks
async def health_check():
    white_id = await get_setting('white_channel_id', '0')
    if white_id == '0':
        return

    try:
        # Ping the channel
        await bot.get_chat(white_id)
    except Exception as e:
        logger.error(f"Health Check Failed for {white_id}: {e}")
        # If Forbidden or ChatNotFound, enter Emergency Mode
        if "chat not found" in str(e).lower() or "forbidden" in str(e).lower():
            current_emergency = await get_setting('emergency_mode', '0')
            if current_emergency == '0':
                logger.warning("Entering Emergency Mode!")
                await set_setting('emergency_mode', '1')
                
                # Notify verified users
                user_ids = await get_all_verified_users()
                alert_text = (
                    "⚠️ **IMPORTANT NOTICE**\n\n"
                    "The current access channel has been taken down. We are in Emergency Mode.\n"
                    "A new link will be provided within 24-48 hours. Please stay tuned."
                )
                await safe_broadcast(bot, user_ids, alert_text)

async def sync_members():
    logger.info("Starting daily sync...")
    # This is a simplified sync. For large groups, use getChatMember in batches if needed.
    # Here we check all verified users.
    verified_ids = await get_all_verified_users()
    for uid in verified_ids:
        in_black = await is_black_channel_member(bot, uid)
        if not in_black:
            logger.info(f"User {uid} left Black Channel. Revoking verification.")
            await verify_user(uid, 0)
    logger.info("Sync complete.")

async def enforcement_sweep():
    """Scheduled sweep: check all known users in social chat against main group."""
    enforcement_on = await get_setting('enforcement_enabled', '1')
    if enforcement_on != '1':
        return

    white_id = await get_setting('white_channel_id', '0')
    if white_id == '0':
        return

    white_id_int = int(white_id)
    logger.info("Starting enforcement sweep...")

    user_ids = await get_all_known_user_ids()
    actions_taken = 0

    for uid in user_ids:
        # Check if user is currently in the social chat
        try:
            member = await bot.get_chat_member(white_id_int, uid)
            if member.status in ["left", "kicked"]:
                continue  # Not in social chat, skip
        except Exception:
            continue  # Can't check, skip

        # They ARE in social chat — enforce main group membership
        from handlers.enforcement import enforce_user
        acted = await enforce_user(bot, uid, white_id_int)
        if acted:
            actions_taken += 1

        # Small delay to respect Telegram rate limits
        import asyncio
        await asyncio.sleep(0.5)

    logger.info(f"Enforcement sweep complete. Actions taken: {actions_taken}")

# Join Request Handler
@dp.chat_join_request()
async def handle_join_request(event: types.ChatJoinRequest):
    black_id = int(await get_setting('black_channel_id', str(BLACK_CHANNEL_ID)))
    if event.chat.id == black_id:
        logger.info(f"Join request from {event.from_user.id} ({event.from_user.username})")
        
        # Check if dangerous from legacy bot
        from database import is_dangerous_user
        is_evil, reason = await is_dangerous_user(event.from_user.id)
        if is_evil:
            logger.warning(f"BLOCKED DANGEROUS JOIN REQUEST: {event.from_user.id} ({reason})")
            await bot.decline_chat_join_request(event.chat.id, event.from_user.id)
            return

        await add_or_update_user(event.from_user.id, event.from_user.username)

# Main
async def main():
    # Init DB
    await init_db()
    
    # Register Handlers (Commands take priority)
    dp.include_router(admin.router)
    dp.include_router(enforcement.router)  # Enforcement before common so join checks fire first
    dp.include_router(common.router)
    dp.include_router(reputation.router)
    dp.include_router(log_handler.router)
    
    # Scheduler
    scheduler = AsyncIOScheduler()
    h_int = int(await get_setting('health_check_interval', '300'))
    s_int = int(await get_setting('sync_interval', '86400'))
    
    scheduler.add_job(health_check, 'interval', seconds=h_int)
    scheduler.add_job(sync_members, 'interval', seconds=s_int)
    scheduler.add_job(enforcement_sweep, 'interval', seconds=21600, misfire_grace_time=3600)  # Every 6 hours (4x daily)
    scheduler.start()
    
    # Start Polling
    logger.info("Bot is starting...")
    await bot.delete_webhook(drop_pending_updates=True)

    # Register commands with Telegram
    try:
        from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat
        from config import ADMIN_IDS
        
        # Public Command (only /letmein is public)
        public_commands = [
            BotCommand(command="letmein", description="Gain entry to an undeletable group if you are known and trusted")
        ]
        await bot.set_my_commands(public_commands, scope=BotCommandScopeDefault())
        
        # Admin Commands (only visible to admins in DMs)
        admin_commands = public_commands + [
            BotCommand(command="admin", description="Admin Control Panel"),
            BotCommand(command="status", description="Check bot system and OCI server status"),
        ]
        for admin_id in ADMIN_IDS:
            try:
                await bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))
            except Exception as e:
                logger.warning(f"Failed to set admin commands for {admin_id}: {e}")
    except Exception as e:
        logger.error(f"Failed to set commands menu: {e}")

    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
