import asyncio
import logging
from aiogram import Bot
from config import BOT_TOKEN
from database import connect_db, update_user_gatekeeper_status, get_all_known_user_ids
from utils.helpers import is_black_channel_member

# Configure clean logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("sync_gatekeeper")

async def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not configured inside config.py or .env!")
        return
        
    bot = Bot(token=BOT_TOKEN)
    logger.info("Fetching all registered user IDs from database...")
    user_ids = await get_all_known_user_ids()
    logger.info(f"Found {len(user_ids)} users to check.")
    
    in_count = 0
    out_count = 0
    
    for idx, uid in enumerate(user_ids, 1):
        try:
            in_black = await is_black_channel_member(bot, uid)
            status = 1 if in_black else 0
            await update_user_gatekeeper_status(uid, status)
            if in_black:
                in_count += 1
                logger.info(f"[{idx}/{len(user_ids)}] User {uid}: IN gatekeeper channel")
            else:
                out_count += 1
        except Exception as e:
            logger.error(f"Error checking user {uid}: {e}")
        
        # Safe sleep to respect Telegram rate limiting bounds
        await asyncio.sleep(0.05)
        
    logger.info("──────────────────────────────────────────────────")
    logger.info(f"🎉 Synchronization Complete!")
    logger.info(f"• IN gatekeeper:  {in_count}")
    logger.info(f"• OUT gatekeeper: {out_count}")
    logger.info("──────────────────────────────────────────────────")
    
    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
