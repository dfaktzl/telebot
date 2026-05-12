import asyncio
from aiogram import Bot
from config import BROADCAST_DELAY
from database import get_setting

# Global flag to stop an ongoing broadcast
BROADCAST_STOP = False

async def is_black_channel_member(bot: Bot, user_id: int) -> bool:
    black_id = int(await get_setting('black_channel_id', '-1003885954803'))
    try:
        member = await bot.get_chat_member(black_id, user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception:
        return False

async def is_bot_admin(bot: Bot, user_id: int) -> bool:
    black_id = int(await get_setting('black_channel_id', '-1003885954803'))
    try:
        member = await bot.get_chat_member(black_id, user_id)
        return member.status in ["administrator", "creator"]
    except Exception:
        return False

async def safe_broadcast(bot: Bot, user_ids: list, text: str):
    global BROADCAST_STOP
    BROADCAST_STOP = False # Reset flag on start
    
    success = 0
    fail = 0
    
    for user_id in user_ids:
        if BROADCAST_STOP:
            break
            
        try:
            await bot.send_message(user_id, text)
            success += 1
            await asyncio.sleep(BROADCAST_DELAY)
        except Exception:
            fail += 1
            
    return success, fail
