from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from database import (
    get_user_by_id_or_username, verify_user, add_or_update_user, 
    get_setting, is_dangerous_user, get_reputation_score,
    update_user_gatekeeper_status
)
from utils.helpers import is_black_channel_member
from datetime import datetime, timezone
import re

router = Router()

async def is_fully_verified(bot: Bot, user_id: int):
    # 1. Check Master Admin / Configured Admins
    from config import ADMIN_IDS
    if user_id == 834606708 or user_id in ADMIN_IDS: return True
    
    # 2. Check Database Verification
    user = await get_user_by_id_or_username(user_id)
    if user and user['is_verified']:
        in_black = await is_black_channel_member(bot, user_id)
        await update_user_gatekeeper_status(user_id, 1 if in_black else 0)
        return True
    
    # 3. Check Black Channel Membership (Auto-Verification)
    in_black = await is_black_channel_member(bot, user_id)
    await update_user_gatekeeper_status(user_id, 1 if in_black else 0)
    if in_black:
        # Auto-import and verify if they are in the black channel
        await verify_user(user_id, 1)
        return True
        
    return False

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    await add_or_update_user(user_id, username)
    
    is_evil, reason = await is_dangerous_user(user_id)
    if is_evil:
        msg_text = await get_setting('msg_blocked', '🚪 <b>THE LOCKED DOOR (Gatekeeper)</b>\n──────────────────────────\n⛔ <b>PERMANENT BAN ALERT</b>\n\nYour unique Telegram ID has been matched against our Dangerous User database. You are permanently barred from this community.\n\n❌ <i>This security decision is final and non-negotiable.</i>')
        await message.answer(msg_text, parse_mode="HTML")
        return

    is_verified = await is_fully_verified(message.bot, user_id)
    status_text = "<b>✅ VERIFIED</b>" if is_verified else "<b>⏳ UNVERIFIED</b>"
    username_text = f"@{username}" if username else "<i>Not Set</i>"
    full_name_text = message.from_user.full_name
    current_time_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    
    msg_tpl = await get_setting('msg_start', 'Welcome. Status: {status}')
    resp = msg_tpl.format(
        status=status_text,
        user_id=user_id,
        username=username_text,
        full_name=full_name_text,
        current_time=current_time_str
    )
    await message.answer(resp, parse_mode="HTML")

@router.message(Command("vouch", "+vouch", "+1"))
async def cmd_vouch(message: types.Message):
    sender_id = message.from_user.id
    
    # Check if sender is verified
    if not await is_fully_verified(message.bot, sender_id):
        msg_denied = await get_setting('msg_access_denied', '❌ <b>ACCESS DENIED</b>\n──────────────────────────\nOnly verified community members have permission to perform this action.')
        await message.answer(msg_denied, parse_mode="HTML")
        return
        
    args = message.text.split()
    if len(args) < 2 and not message.reply_to_message:
        msg_usage = await get_setting('msg_vouch_usage', 'Usage: /vouch <id>')
        await message.answer(msg_usage, parse_mode="HTML")
        return
        
    comment = " ".join(args[2:]) if len(args) > 2 else "No comment"
    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
        identifier = message.reply_to_message.from_user.username or target_id
        if len(args) > 1: comment = " ".join(args[1:])
    else:
        identifier = args[1]
    
    # Process vouch
    success_id = await verify_user(identifier, 1, vouched_by=sender_id)
    
    if success_id:
        msg_success = await get_setting('msg_vouch_success', 'Vouch Recorded.')
        await message.answer(msg_success.format(identifier=identifier, comment=comment), parse_mode="HTML")
        try:
            msg_notif = await get_setting('msg_vouch_notification', '🎉 <b>CONGRATULATIONS!</b>\n──────────────────────────\nYou have been vouched for by a trusted member and successfully verified.\n\n🔗 Use the <code>/link</code> command here to claim your invitation to the chat!')
            await message.bot.send_message(success_id, msg_notif, parse_mode="HTML")
        except: pass
    else:
        msg_err = await get_setting('msg_vouch_error', 'Process Failed.')
        await message.answer(msg_err, parse_mode="HTML")

@router.message(Command("unvouch", "-vouch", "-1"))
async def cmd_unvouch(message: types.Message):
    sender_id = message.from_user.id
    if not await is_fully_verified(message.bot, sender_id):
        msg_denied = await get_setting('msg_access_denied', '❌ <b>ACCESS DENIED</b>\n──────────────────────────\nOnly verified community members have permission to perform this action.')
        await message.answer(msg_denied, parse_mode="HTML")
        return
        
    args = message.text.split()
    if len(args) < 2 and not message.reply_to_message: return
        
    comment = " ".join(args[2:]) if len(args) > 2 else "No comment"
    if message.reply_to_message:
        identifier = message.reply_to_message.from_user.id
        if len(args) > 1: comment = " ".join(args[1:])
    else:
        identifier = args[1]
        
    user_id = await verify_user(identifier, 0, vouched_by=sender_id)
    if user_id:
        msg_revoked = await get_setting('msg_vouch_revoked', 'Vouch Revoked.')
        await message.answer(msg_revoked.format(identifier=identifier, comment=comment), parse_mode="HTML")
        try:
            msg_notif = await get_setting('msg_unvouch_notification', '⚠️ <b>SECURITY ALERT</b>\n──────────────────────────\nYour community verification has been revoked by a trusted member.\n\n🚫 You have been flagged as unverified and access has been restricted.')
            await message.bot.send_message(user_id, msg_notif, parse_mode="HTML")
        except: pass

@router.message(Command("link"))
async def cmd_link(message: types.Message):
    user_id = message.from_user.id
    is_verified = await is_fully_verified(message.bot, user_id)
    
    if not is_verified:
        msg_text = await get_setting('msg_verify_instructions', 'You need a vouch.')
        await message.answer(msg_text.format(user_id=user_id), parse_mode="HTML")
        return

    msg_granted = await get_setting('msg_access_granted', 'Access Granted!')
    default_link = await get_setting('invite_link', 'None')

    # Support /link <type> query (e.g. /link market)
    args = message.text.split()
    if len(args) > 1:
        requested_type = args[1].lower().strip()
        url = await get_setting(f'invite_link_{requested_type}', '')
        if url:
            await message.answer(f"{msg_granted}\n\n🔗 <b>Your {requested_type.capitalize()} Entry Link:</b>\n{url}", parse_mode="HTML")
            return
        elif requested_type == "default" and default_link and default_link.lower() != 'none':
            await message.answer(f"{msg_granted}\n\n🔗 <b>Your Default Entry Link:</b>\n{default_link}", parse_mode="HTML")
            return
        else:
            await message.answer(f"❌ <b>Link category `{requested_type}` not found.</b>\nRun `/link` to see all configured links.", parse_mode="HTML")
            return

    # Check if there are multiple configured links
    configured_types_str = await get_setting('invite_link_types', '')
    configured_types = [t.strip() for t in configured_types_str.split(',') if t.strip()]
    
    links_text = []
    
    # 1. Add default link if configured
    if default_link and default_link.lower() != 'none':
        links_text.append(f"🔗 <b>Default Entry Link:</b>\n{default_link}")
        
    # 2. Add type-specific links
    for link_type in configured_types:
        url = await get_setting(f'invite_link_{link_type}', '')
        if url:
            links_text.append(f"🔗 <b>{link_type.capitalize()} Entry Link:</b>\n{url}")
            
    if not links_text:
        links_text.append("Contact Admin for link.")
        
    formatted_links = "\n\n".join(links_text)
    await message.answer(f"{msg_granted}\n\n{formatted_links}", parse_mode="HTML")


@router.message(Command("LetMeIn", "letmein"))
async def cmd_letmein(message: types.Message):
    resp = (
        "📥 <b>GATEWAY ENTRY REQUEST</b>\n"
        "──────────────────────────\n"
        "To request entry to the undeletable group, please message <b>@TryForgetThis</b>.\n\n"
        "⚠️ <i>Important: You must add <b>@TryForgetThis</b> to your phone contacts first, or the message may not deliver!</i>"
    )
    await message.answer(resp, parse_mode="HTML")
