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


async def delete_message_after_delay(bot: Bot, chat_id: int, message_id: int, delay: int):
    """Safely delete a message after a specified delay (in seconds)."""
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        logger.warning(f"Failed to auto-delete message {message_id} in chat {chat_id}: {e}")


async def enforce_user(bot: Bot, user_id: int, chat_id: int, username: str = None, **kwargs):
    """Core enforcement logic: check if user belongs to main group.
    If not, give 5 warnings before a kick, and then another 3 warnings before a permanent ban.
    Returns True if action was taken (user was kicked or banned), False if user was just warned."""
    from config import LOG_CHANNEL

    # Check if user is in the main group (black channel)
    in_main_group = await is_black_channel_member(bot, user_id)
    await update_user_gatekeeper_status(user_id, 1 if in_main_group else 0)
    if in_main_group:
        return False  # User is legit, no action needed

    kick_count = await get_kick_count(user_id)
    display_name = f"@{username}" if username else f"User {user_id}"

    if kick_count < 5:
        # Case A: Warn (Warning 1/5 to 5/5)
        warn_num = kick_count + 1
        await increment_kick_count(user_id)

        try:
            warn_msg = await bot.send_message(
                chat_id,
                f"⚠️ <b>{display_name}</b> has received a warning (Warning <b>{warn_num}/5</b>).\n"
                f"──────────────────────────\n"
                f"📋 <b>Reason:</b> Not a verified member of our main group.\n"
                f"ℹ️ Please join our main group first to gain access here.\n\n"
                f"<i>You will be kicked from this chat on the 6th attempt.</i>",
                parse_mode="HTML"
            )
            # Auto-delete warning notification
            warn_timer = int(await get_setting('kick_delete_timer', '300'))
            if warn_timer > 0:
                asyncio.create_task(delete_message_after_delay(bot, chat_id, warn_msg.message_id, warn_timer))
        except Exception as e:
            logger.error(f"Failed to send join warning notification for {user_id}: {e}")

        if LOG_CHANNEL:
            try:
                log_text = (
                    f"🚪 <b>GATEKEEPER WARNING (Pre-Kick)</b>\n"
                    f"──────────────────────────\n"
                    f"👤 <b>User:</b> {display_name} (<code>{user_id}</code>)\n"
                    f"📋 <b>Action:</b> Warned (Warning {warn_num}/5)\n"
                    f"ℹ️ <b>Reason:</b> Not a verified member of the main group."
                )
                await bot.send_message(
                    chat_id=LOG_CHANNEL,
                    text=log_text,
                    parse_mode="HTML"
                )
            except Exception as log_err:
                logger.warning(f"Failed to send gatekeeper log: {log_err}")

        logger.info(f"ENFORCEMENT: Warned {display_name} ({user_id}) (Warning {warn_num}/5)")
        return False  # Not kicked/banned

    elif kick_count == 5:
        # Case B: KICK (On the 6th attempt, after 5 warnings)
        try:
            await bot.ban_chat_member(chat_id, user_id)
            # Immediately unban so they CAN rejoin
            await bot.unban_chat_member(chat_id, user_id, only_if_banned=True)
        except Exception as e:
            logger.error(f"Failed to kick {user_id} from {chat_id}: {e}")
            return False

        await increment_kick_count(user_id)

        try:
            kick_msg = await bot.send_message(
                chat_id,
                f"⚠️ <b>{display_name}</b> has been kicked from the channel.\n"
                f"──────────────────────────\n"
                f"📋 <b>Reason:</b> Exceeded 5 warnings without main group verification.\n"
                f"ℹ️ Join our main group first to gain access here.\n\n"
                f"<i>Another 3 warnings will result in a permanent ban.</i>",
                parse_mode="HTML"
            )
            kick_timer = int(await get_setting('kick_delete_timer', '300'))
            if kick_timer > 0:
                asyncio.create_task(delete_message_after_delay(bot, chat_id, kick_msg.message_id, kick_timer))
        except Exception as e:
            logger.error(f"Failed to send kick notification for {user_id}: {e}")

        if LOG_CHANNEL:
            try:
                log_text = (
                    f"🚪 <b>GATEKEEPER EVICTION (Kick)</b>\n"
                    f"──────────────────────────\n"
                    f"👤 <b>User:</b> {display_name} (<code>{user_id}</code>)\n"
                    f"📋 <b>Action:</b> Kicked from Social Chat (5 warnings exceeded)\n"
                    f"ℹ️ <b>Reason:</b> Not a verified member of the main group."
                )
                await bot.send_message(
                    chat_id=LOG_CHANNEL,
                    text=log_text,
                    parse_mode="HTML"
                )
            except Exception as log_err:
                logger.warning(f"Failed to send gatekeeper log: {log_err}")

        logger.info(f"ENFORCEMENT: Kicked {display_name} ({user_id})")
        return True  # Kicked

    elif kick_count >= 6 and kick_count <= 8:
        # Case C: Warning before Ban (another 3 warnings: warnings 1/3, 2/3, 3/3 after kick)
        post_warn_num = kick_count - 5
        await increment_kick_count(user_id)

        try:
            warn_msg = await bot.send_message(
                chat_id,
                f"⚠️ <b>{display_name}</b> has received a warning (Warning <b>{post_warn_num}/3</b> after kick).\n"
                f"──────────────────────────\n"
                f"📋 <b>Reason:</b> Re-entering without main group verification.\n"
                f"ℹ️ Please join our main group first to gain access here.\n\n"
                f"<i>You will be permanently banned on the 4th attempt.</i>",
                parse_mode="HTML"
            )
            warn_timer = int(await get_setting('ban_delete_timer', '600'))
            if warn_timer > 0:
                asyncio.create_task(delete_message_after_delay(bot, chat_id, warn_msg.message_id, warn_timer))
        except Exception as e:
            logger.error(f"Failed to send post-kick warning notification for {user_id}: {e}")

        if LOG_CHANNEL:
            try:
                log_text = (
                    f"🚪 <b>GATEKEEPER WARNING (Post-Kick)</b>\n"
                    f"──────────────────────────\n"
                    f"👤 <b>User:</b> {display_name} (<code>{user_id}</code>)\n"
                    f"📋 <b>Action:</b> Warned (Post-Kick Warning {post_warn_num}/3)\n"
                    f"ℹ️ <b>Reason:</b> Not a verified member of the main group."
                )
                await bot.send_message(
                    chat_id=LOG_CHANNEL,
                    text=log_text,
                    parse_mode="HTML"
                )
            except Exception as log_err:
                logger.warning(f"Failed to send gatekeeper log: {log_err}")

        logger.info(f"ENFORCEMENT: Warned {display_name} ({user_id}) (Post-Kick Warning {post_warn_num}/3)")
        return False  # Not kicked/banned

    else:
        # Case D: Permanent BAN (On the 4th attempt after kick)
        try:
            await bot.ban_chat_member(chat_id, user_id)
        except Exception as e:
            logger.error(f"Failed to ban {user_id} from {chat_id}: {e}")
            return False

        await increment_kick_count(user_id)

        try:
            ban_msg = await bot.send_message(
                chat_id,
                f"🚫 <b>{display_name}</b> has been permanently banned.\n"
                f"──────────────────────────\n"
                f"📋 <b>Reason:</b> Repeated entry without main group verification.\n"
                f"❌ <i>This decision is final.</i>",
                parse_mode="HTML"
            )
            ban_timer = int(await get_setting('ban_delete_timer', '600'))
            if ban_timer > 0:
                asyncio.create_task(delete_message_after_delay(bot, chat_id, ban_msg.message_id, ban_timer))
        except Exception as e:
            logger.error(f"Failed to send ban notification for {user_id}: {e}")

        if LOG_CHANNEL:
            try:
                log_text = (
                    f"🚫 <b>GATEKEEPER BAN (Permanent)</b>\n"
                    f"──────────────────────────\n"
                    f"👤 <b>User:</b> {display_name} (<code>{user_id}</code>)\n"
                    f"📋 <b>Action:</b> Permanently Banned from Social Chat\n"
                    f"ℹ️ <b>Reason:</b> Exceeded post-kick warnings (Attempt #{kick_count + 1}) without main group verification."
                )
                await bot.send_message(
                    chat_id=LOG_CHANNEL,
                    text=log_text,
                    parse_mode="HTML"
                )
            except Exception as log_err:
                logger.warning(f"Failed to send gatekeeper ban log: {log_err}")

        logger.info(f"ENFORCEMENT: Banned {display_name} ({user_id}) from social chat (attempt #{kick_count + 1})")
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
                 f"✨ <i>Enjoy your stay, read the pinned rules, and conduct yourself respectfully!</i>"
            )
            
            try:
                from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📖 Start Welcome Guide", callback_data="start_welcome_guide")]
                ])
                sent = await message.answer(welcome_text, parse_mode="HTML", reply_markup=kb)
                
                # Auto-delete in background if timer is enabled (> 0)
                if timer > 0:
                    asyncio.create_task(delete_message_after_delay(message.bot, message.chat.id, sent.message_id, timer))
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
        f"<b>Violations will trigger an instant vouch rejection + policy warning. Repeated violations will be reviewed by the mod team.</b>\n\n"
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
            f"──────────────────────────\n"
            f"👤 <b>User:</b> {u_fn} {u_ln} ({u_un})\n"
            f"🆔 <b>User ID:</b> <code>{user.id}</code>\n"
            f"⏱️ <b>Time:</b> <code>{now_str}</code>"
        )
        try:
            await bot.send_message(chat_id=LOG_CHANNEL, text=log_html, parse_mode="HTML")
        except Exception as log_err:
            logger.warning(f"Failed to send join log for user {user.id} to LOG_CHANNEL: {log_err}")


