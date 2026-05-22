import asyncio
import logging
from aiogram import Router, types, F, Bot
from database import (
    get_setting, get_kick_count, increment_kick_count, add_or_update_user
)
from utils.helpers import is_black_channel_member

router = Router()
logger = logging.getLogger(__name__)


async def enforce_user(bot: Bot, user_id: int, chat_id: int, username: str = None):
    """Core enforcement logic: check if user belongs to main group.
    If not, kick (1st offense) or ban (2nd+ offense) from the social chat.
    Returns True if action was taken, False if user is legitimate."""
    from config import LOG_CHANNEL

    # Check if user is in the main group (black channel)
    in_main_group = await is_black_channel_member(bot, user_id)
    if in_main_group:
        return False  # User is legit, no action needed

    kick_count = await get_kick_count(user_id)
    display_name = f"@{username}" if username else f"User {user_id}"

    if kick_count == 0:
        # ── First offense: KICK ──
        try:
            await bot.ban_chat_member(chat_id, user_id)
            # Immediately unban so they CAN rejoin (kick, not permaban)
            await bot.unban_chat_member(chat_id, user_id, only_if_banned=True)
        except Exception as e:
            logger.error(f"Failed to kick {user_id} from {chat_id}: {e}")
            return False

        await increment_kick_count(user_id)

        try:
            kick_tpl = await get_setting(
                'msg_kick_notification',
                '⚠️ <b>{display_name}</b> has been removed from this channel.\n──────────────────────────\n📋 <b>Reason:</b> Not a verified member of our main group.\nℹ️ Join our main group first to gain access here.\n\n<i>This is their first warning. A second attempt will result in a permanent ban.</i>'
            )
            kick_msg = await bot.send_message(
                chat_id,
                kick_tpl.format(display_name=display_name),
                parse_mode="HTML"
            )
            # Auto-delete the notification after 5 minutes
            async def _delete_kick_msg(msg=kick_msg):
                await asyncio.sleep(300)
                try:
                    await msg.delete()
                except Exception:
                    pass
            asyncio.create_task(_delete_kick_msg())
        except Exception as e:
            logger.error(f"Failed to send kick notification for {user_id}: {e}")

        # Send Log Channel update
        if LOG_CHANNEL:
            try:
                log_text = (
                    f"🚪 <b>GATEKEEPER EVICTION (Kick)</b>\n"
                    f"──────────────────────────\n"
                    f"👤 <b>User:</b> {display_name} (<code>{user_id}</code>)\n"
                    f"📋 <b>Action:</b> Kicked from Social Chat (1st offense)\n"
                    f"ℹ️ <b>Reason:</b> Not a verified member of the main group."
                )
                await bot.send_message(
                    chat_id=LOG_CHANNEL,
                    text=log_text,
                    parse_mode="HTML"
                )
            except Exception as log_err:
                logger.warning(f"Failed to send gatekeeper kick log: {log_err}")

        logger.info(f"ENFORCEMENT: Kicked {display_name} ({user_id}) from social chat (1st offense)")
        return True

    else:
        # ── Second+ offense: PERMANENT BAN ──
        try:
            await bot.ban_chat_member(chat_id, user_id)
            # Do NOT unban — this is permanent
        except Exception as e:
            logger.error(f"Failed to ban {user_id} from {chat_id}: {e}")
            return False

        await increment_kick_count(user_id)

        try:
            ban_tpl = await get_setting(
                'msg_ban_notification',
                '🚫 <b>{display_name}</b> has been permanently banned.\n──────────────────────────\n📋 <b>Reason:</b> Repeated entry without main group verification.\n❌ <i>This decision is final.</i>'
            )
            ban_msg = await bot.send_message(
                chat_id,
                ban_tpl.format(display_name=display_name),
                parse_mode="HTML"
            )
            # Auto-delete the notification after 10 minutes
            async def _delete_ban_msg(msg=ban_msg):
                await asyncio.sleep(600)
                try:
                    await msg.delete()
                except Exception:
                    pass
            asyncio.create_task(_delete_ban_msg())
        except Exception as e:
            logger.error(f"Failed to send ban notification for {user_id}: {e}")

        # Send Log Channel update
        if LOG_CHANNEL:
            try:
                log_text = (
                    f"🚫 <b>GATEKEEPER BAN (Permanent)</b>\n"
                    f"──────────────────────────\n"
                    f"👤 <b>User:</b> {display_name} (<code>{user_id}</code>)\n"
                    f"📋 <b>Action:</b> Permanently Banned from Social Chat\n"
                    f"ℹ️ <b>Reason:</b> Repeated entry attempt (Offense #{kick_count + 1}) without main group verification."
                )
                await bot.send_message(
                    chat_id=LOG_CHANNEL,
                    text=log_text,
                    parse_mode="HTML"
                )
            except Exception as log_err:
                logger.warning(f"Failed to send gatekeeper ban log: {log_err}")

        logger.info(f"ENFORCEMENT: Banned {display_name} ({user_id}) from social chat (offense #{kick_count + 1})")
        return True


@router.message(F.new_chat_members)
async def on_social_chat_join(message: types.Message):
    """When someone joins the social/market chat, check if they belong to the main group and welcome them if allowed."""
    white_id = await get_setting('white_channel_id', '0')
    if str(message.chat.id) != white_id:
        return  # Not the social chat, ignore

    enforcement_on = await get_setting('enforcement_enabled', '1')

    for member in message.new_chat_members:
        if member.is_bot:
            continue

        # Record the user in DB
        await add_or_update_user(member.id, member.username)

        # Enforce if enabled
        acted = False
        if enforcement_on == '1':
            acted = await enforce_user(
                message.bot,
                member.id,
                message.chat.id,
                username=member.username
            )

        # Welcome the user if they were allowed to stay (not kicked/banned)
        if not acted:
            timer = int(await get_setting('welcome_delete_timer', '600'))  # Default to 10 minutes
            msg_tpl = await get_setting('msg_welcome', 'Welcome, {user_mention}!')
            mention = member.mention_html()
            text = msg_tpl.format(user_mention=mention, timer=timer)
            try:
                sent = await message.answer(text, parse_mode="HTML")
                
                # Auto-delete in background
                async def _delete_later(msg=sent, delay=timer):
                    await asyncio.sleep(delay)
                    try:
                        await msg.delete()
                    except Exception:
                        pass
                asyncio.create_task(_delete_later())
            except Exception as e:
                logger.error(f"Failed to send welcome message: {e}")

