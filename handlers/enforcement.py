import asyncio
import logging
from aiogram import Router, types, F, Bot
from database import (
    get_setting, get_kick_count, increment_kick_count, add_or_update_user,
    update_user_gatekeeper_status
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
    await update_user_gatekeeper_status(user_id, 1 if in_main_group else 0)
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
            # Auto-delete the notification if timer is enabled (> 0)
            kick_timer = int(await get_setting('kick_delete_timer', '300'))
            if kick_timer > 0:
                async def _delete_kick_msg(msg=kick_msg, delay=kick_timer):
                    await asyncio.sleep(delay)
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
            # Auto-delete the notification if timer is enabled (> 0)
            ban_timer = int(await get_setting('ban_delete_timer', '600'))
            if ban_timer > 0:
                async def _delete_ban_msg(msg=ban_msg, delay=ban_timer):
                    await asyncio.sleep(delay)
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
            
            u_mention = member.mention_html()
            u_username = f"@{member.username}" if member.username else "None"
            u_id = member.id
            
            welcome_text = (
                 f"🌟 <b>WELCOME TO THE COMMUNITY</b> 🌟\n"
                 f"──────────────────────────\n"
                 f"👋 Welcome to the social group, {u_mention}!\n\n"
                 f"👤 <b>Profile Details:</b>\n"
                 f"├─ 🏷️ <b>Username:</b> {u_username}\n"
                 f"└─ 🆔 <b>User ID:</b> <code>{u_id}</code>\n\n"
                 f"✨ <i>Enjoy your stay, read the pinned rules, and conduct yourself respectfully!</i>\n"
                 f"──────────────────────────\n"
                 f"⏳ <i>This welcome message self-destructs in {timer} seconds.</i>"
            )
            
            try:
                from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📖 Start Welcome Guide", callback_data="start_welcome_guide")]
                ])
                sent = await message.answer(welcome_text, parse_mode="HTML", reply_markup=kb)
                
                # Auto-delete in background if timer is enabled (> 0)
                if timer > 0:
                    async def _delete_later(msg=sent, delay=timer):
                        await asyncio.sleep(delay)
                        try:
                            await msg.delete()
                        except Exception:
                            pass
                    asyncio.create_task(_delete_later())
            except Exception as e:
                logger.error(f"Failed to send welcome message: {e}")


@router.callback_query(F.data == "start_welcome_guide")
async def cb_start_welcome_guide(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    first_name = callback_query.from_user.first_name
    
    # Premium Onboarding Guide Text for private DM
    guide_text = (
        f"📖 <b>WELCOME GUIDE & TUTORIAL</b>\n"
        f"──────────────────────────\n"
        f"Hello <a href=\"tg://user?id={user_id}\">{first_name}</a>! Welcome to our private community.\n\n"
        f"🛡️ <b>ABOUT THE REPUTATION BOT</b>\n"
        f"We use a highly redundant permanent reputation system to protect members from fraud:\n"
        f"• <b>Unique User IDs:</b> Vouches follow your Telegram User ID (<code>{user_id}</code>) persistently, even if you edit your username!\n"
        f"• <b>Sybil Shield:</b> New accounts have strict cooldowns and must be verified to interact with specific chats.\n\n"
        f"💡 <b>QUICK COMMANDS TUTORIAL</b>\n"
        f"• <code>/check</code> — View your own vouch score and history.\n"
        f"• <code>/check &lt;User ID or @username&gt;</code> — Lookup another member's trust record.\n"
        f"• Reply <code>/check</code> to anyone's message in group chats to audit them.\n\n"
        f"✅ <b>VOUCHING FOR OTHERS (High-Trust Entry)</b>\n"
        f"Vouches represent active successful trades or peer reviews:\n"
        f"• Reply to a trusted peer's message with <code>+vouch Great trader!</code> or <code>+1</code>.\n"
        f"• Or run: <code>/vouch &lt;User ID&gt; [reason]</code> in our DM.\n\n"
        f"⚠️ <b>POLICIES & SECURITY RULES</b>\n"
        f"• 2 vouches max per 24 hours.\n"
        f"• Cooldown per user: 36 hours.\n"
        f"• Cooldown for new accounts to vouch: 48 hours.\n"
        f"• ⛔ <b>ZERO TOLERANCE FOR ILLEGAL/DRUG TERMS:</b> "
        f"<b>You MUST NOT use drug names, illegal terminology, weapons, or fraud terms in your vouches!</b> "
        f"<b>You gain absolutely nothing from adding illegal terms.</b> Just saying _\"stuff was good, on time, would deal with again\"_ is **perfect and preferred**.\n"
        f"<b>Violations will trigger an instant vouch rejection + permanent ban!</b>\n\n"
        f"──────────────────────────\n"
        f"<i>To start checking profiles or link your account, use Vouch Checker: @VouchCheckerBot. Enjoy your stay!</i>"
    )
    
    try:
        await callback_query.bot.send_message(
            chat_id=user_id,
            text=guide_text,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        await callback_query.answer("📨 Guide successfully sent to your private DMs!", show_alert=True)
    except Exception as e:
        logger.warning(f"Failed to DM welcome guide to {user_id}: {e}")
        await callback_query.answer(
            "⚠️ Unable to DM you! Please click @VouchCheckerBot and send /start first, then try again.",
            show_alert=True
        )


@router.chat_member()
async def on_chat_member_join_log(event: types.ChatMemberUpdated, bot: Bot):
    """Listens to all chat member status changes and logs user joins to any group/channel the bot is in to LOG_CHANNEL."""
    from config import LOG_CHANNEL
    if not LOG_CHANNEL:
        return

    old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status

    was_in = old_status in ["member", "administrator", "creator"]
    is_in = new_status in ["member", "administrator", "creator"]

    if is_in and not was_in:
        # User joined! Let's log it.
        user = event.new_chat_member.user
        if user.is_bot:
            return

        from html import escape
        from datetime import datetime, timezone
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        u_fn = escape(user.first_name) if user.first_name else "Unknown"
        u_ln = escape(user.last_name) if user.last_name else "None"
        u_un = f"@{escape(user.username)}" if user.username else "None"
        chat_title = escape(event.chat.title) if event.chat.title else "Group"

        log_html = (
            f"📥 <b>User joined chat {chat_title}</b>\n"
            f"👤 <b>User:</b> {u_fn} {u_ln} ({u_un}) | 🆔 <b>ID:</b> <code>{user.id}</code>\n"
            f"⏱️ <b>Time:</b> <code>{now_str}</code>"
        )
        try:
            await bot.send_message(chat_id=LOG_CHANNEL, text=log_html, parse_mode="HTML")
        except Exception as log_err:
            logger.warning(f"Failed to send join log for user {user.id} to LOG_CHANNEL: {log_err}")


