from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from database import (
    get_user_by_id_or_username, verify_user, add_or_update_user, 
    get_setting, is_dangerous_user, get_reputation_score
)
from utils.helpers import is_black_channel_member
import re

router = Router()

async def is_fully_verified(bot: Bot, user_id: int):
    # 1. Check Master Admin
    if user_id == 834606708: return True
    
    # 2. Check Database Verification
    user = await get_user_by_id_or_username(user_id)
    if user and user[2]: return True
    
    # 3. Check Black Channel Membership (Auto-Verification)
    in_black = await is_black_channel_member(bot, user_id)
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
        msg_text = await get_setting('msg_blocked', '⛔ You are permanently banned.')
        await message.answer(msg_text)
        return

    is_verified = await is_fully_verified(message.bot, user_id)
    status_text = "✅ **VERIFIED**" if is_verified else "⏳ **UNVERIFIED**"
    
    msg_tpl = await get_setting('msg_start', 'Welcome. Status: {status}')
    resp = msg_tpl.format(status=status_text, user_id=user_id)
    await message.answer(resp)

@router.message(Command("vouch", "+vouch", "+1"))
async def cmd_vouch(message: types.Message):
    sender_id = message.from_user.id
    
    # Check if sender is verified (Using the new bypass)
    if not await is_fully_verified(message.bot, sender_id):
        await message.answer("❌ **Access Denied**\nOnly verified members can vouch for others.")
        return
        
    args = message.text.split()
    if len(args) < 2 and not message.reply_to_message:
        msg_usage = await get_setting('msg_vouch_usage', 'Usage: /vouch <id>')
        await message.answer(msg_usage)
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
        await message.answer(msg_success.format(identifier=identifier, comment=comment))
        try:
            await message.bot.send_message(success_id, "🎉 **Congratulations!**\nYou have been vouched for and verified. Use /link to join.")
        except: pass
    else:
        msg_err = await get_setting('msg_vouch_error', 'Process Failed.')
        await message.answer(msg_err)

@router.message(Command("unvouch", "-vouch", "-1"))
async def cmd_unvouch(message: types.Message):
    sender_id = message.from_user.id
    if not await is_fully_verified(message.bot, sender_id): return
        
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
        await message.answer(msg_revoked.format(identifier=identifier, comment=comment))
        try:
            await message.bot.send_message(user_id, "⚠️ **Security Alert**\nYour verification has been revoked by a trusted member.")
        except: pass

@router.message(Command("link"))
async def cmd_link(message: types.Message):
    user_id = message.from_user.id
    is_verified = await is_fully_verified(message.bot, user_id)
    
    if not is_verified:
        msg_text = await get_setting('msg_verify_instructions', 'You need a vouch.')
        await message.answer(msg_text.format(user_id=user_id))
        return

    invite_link = await get_setting('invite_link', 'Contact Admin for link.')
    msg_granted = await get_setting('msg_access_granted', 'Access Granted!')
    await message.answer(f"{msg_granted}\n\n🔗 **Your Entry Link:**\n{invite_link}")
