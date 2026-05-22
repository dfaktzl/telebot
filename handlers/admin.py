from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database import (
    get_stats, set_setting, get_setting, verify_user, 
    get_all_verified_users, get_user_by_id_or_username, get_username_history
)
from utils.helpers import is_bot_admin, safe_broadcast, BROADCAST_STOP
import aiosqlite
import os
import psutil
import time

START_TIME = time.time()
MASTER_ADMIN_ID = 834606708

router = Router()

def get_admin_main_kb():
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="📊 Stats & Health", callback_data="admin_stats"))
    builder.row(types.InlineKeyboardButton(text="⚙️ System Config", callback_data="admin_config"))
    builder.row(types.InlineKeyboardButton(text="🧠 Brain (Keywords)", callback_data="admin_keywords"))
    builder.row(types.InlineKeyboardButton(text="📝 Edit Messages", callback_data="admin_messages"))
    builder.row(types.InlineKeyboardButton(text="📢 Mass Broadcast", callback_data="admin_broadcast_start"))
    return builder.as_markup()

@router.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id != MASTER_ADMIN_ID and not await is_bot_admin(message.bot, message.from_user.id): return
    await message.answer(
        "⚙️ **MASTER CONTROL PANEL**\n"
        "──────────────────────────\n"
        "Welcome to the high-security management interface. Choose a module to manage:",
        reply_markup=get_admin_main_kb()
    )

@router.callback_query(F.data == "admin_main")
async def cb_main(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "⚙️ **MASTER CONTROL PANEL**\n"
        "──────────────────────────\n"
        "Welcome to the high-security management interface. Choose a module to manage:",
        reply_markup=get_admin_main_kb()
    )
    await callback.answer()

# --- 📊 STATS PAGE ---
@router.callback_query(F.data == "admin_stats")
async def cb_stats(callback: types.CallbackQuery):
    total, verified = await get_stats()
    emergency = await get_setting('emergency_mode', '0')
    status = "🚨 EMERGENCY" if emergency == '1' else "🟢 NORMAL"
    
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="🔄 Update Channel IDs", callback_data="admin_update_id"))
    builder.row(types.InlineKeyboardButton(text="⬅️ Back", callback_data="admin_main"))
    
    await callback.message.edit_text(
        f"📊 **System Stats & Health**\n"
        f"──────────────────────────\n"
        f"Users: `{total}` total (`{verified}` verified)\n"
        f"Status: **{status}**\n\n"
        f"Vouches are synced daily to @VouchCheckerBot.\n"
        f"Health Check: **OPERATIONAL**",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

# --- ⚙️ CONFIG PAGE ---
@router.callback_query(F.data == "admin_config")
async def cb_config(callback: types.CallbackQuery):
    emergency = await get_setting('emergency_mode', '0')
    auto_vouch = await get_setting('auto_vouch_enabled', '1')
    illegal_det = await get_setting('illegal_detection_enabled', '1')
    
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text=f"{'🔴' if emergency == '1' else '🟢'} Emergency Mode", callback_data="toggle_emergency"),
        types.InlineKeyboardButton(text=f"{'🟢' if auto_vouch == '1' else '🔴'} Auto-Vouch", callback_data="toggle_auto")
    )
    builder.row(
        types.InlineKeyboardButton(text=f"{'🟢' if illegal_det == '1' else '🔴'} Illegal Check", callback_data="toggle_illegal"),
        types.InlineKeyboardButton(text="🔗 Set Link", callback_data="admin_update_link")
    )
    builder.row(types.InlineKeyboardButton(text="⬅️ Back", callback_data="admin_main"))
    
    await callback.message.edit_text(
        "⚙️ **System Configuration**\n"
        f"──────────────────────────\n"
        "Toggle system features instantly. Changes take effect immediately without restart.",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@router.callback_query(F.data.startswith("toggle_"))
async def cb_toggle(callback: types.CallbackQuery):
    feature = callback.data.split("_")[1]
    key = {
        "emergency": "emergency_mode",
        "auto": "auto_vouch_enabled",
        "illegal": "illegal_detection_enabled"
    }.get(feature)
    
    current = await get_setting(key, '0')
    new_val = '1' if current == '0' else '0'
    await set_setting(key, new_val)
    await cb_config(callback)

# --- 🧠 BRAIN PAGE ---
@router.callback_query(F.data == "admin_keywords")
async def cb_keywords(callback: types.CallbackQuery):
    score = await get_setting('min_sentiment_score', '2')
    words = await get_setting('min_sentiment_words', '5')
    
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="⬅️ Back", callback_data="admin_main"))
    
    await callback.message.edit_text(
        "🧠 **Reputation Intelligence**\n"
        f"──────────────────────────\n"
        f"📊 Threshold: {words} words / {score}+ sentiment score\n\n"
        "Automatically extracts vouches from natural conversations based on structured sentiment scoring.",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

# --- 📝 MESSAGES PAGE ---
@router.callback_query(F.data == "admin_messages")
async def cb_messages(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="Start Msg", callback_data="edit_msg_start"),
        types.InlineKeyboardButton(text="Welcome Msg", callback_data="edit_msg_welcome")
    )
    builder.row(
        types.InlineKeyboardButton(text="Vouch Success", callback_data="edit_msg_vouch_success"),
        types.InlineKeyboardButton(text="Vouch Revoked", callback_data="edit_msg_vouch_revoked")
    )
    builder.row(
        types.InlineKeyboardButton(text="Vouch Notif", callback_data="edit_msg_vouch_notification"),
        types.InlineKeyboardButton(text="Unvouch Notif", callback_data="edit_msg_unvouch_notification")
    )
    builder.row(
        types.InlineKeyboardButton(text="Access Granted", callback_data="edit_msg_access_granted"),
        types.InlineKeyboardButton(text="Access Denied", callback_data="edit_msg_access_denied")
    )
    builder.row(
        types.InlineKeyboardButton(text="Verify Instr", callback_data="edit_msg_verify_instructions"),
        types.InlineKeyboardButton(text="Blocked Msg", callback_data="edit_msg_blocked")
    )
    builder.row(
        types.InlineKeyboardButton(text="Kick Notif", callback_data="edit_msg_kick_notification"),
        types.InlineKeyboardButton(text="Ban Notif", callback_data="edit_msg_ban_notification")
    )
    builder.row(
        types.InlineKeyboardButton(text="ToS Warning", callback_data="edit_msg_illegal_warning")
    )
    builder.row(types.InlineKeyboardButton(text="⬅️ Back", callback_data="admin_main"))
    
    await callback.message.edit_text(
        "📝 **Dynamic Message Editor**\n"
        f"──────────────────────────\n"
        "Choose a message to edit. You will receive the current text and edit instructions.",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@router.callback_query(F.data.startswith("edit_msg_"))
async def cb_edit_msg(callback: types.CallbackQuery):
    key = callback.data.replace("edit_", "")
    current = await get_setting(key, "Not Set")
    
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="⬅️ Back", callback_data="admin_messages"))
    
    # Custom note based on the setting key
    variables_note = "No specific variables."
    if key == "msg_start":
        variables_note = "Use {user_id}, {username}, {full_name}, {status}, and {current_time}."
    elif key == "msg_welcome":
        variables_note = "Use {user_mention} and {timer}."
    elif key in ["msg_vouch_success", "msg_vouch_revoked"]:
        variables_note = "Use {identifier} and {comment}."
    elif key in ["msg_kick_notification", "msg_ban_notification"]:
        variables_note = "Use {display_name}."
    elif key == "msg_verify_instructions":
        variables_note = "Use {user_id}."
    elif key == "msg_illegal_warning":
        variables_note = "Use {user_mention}."

    await callback.message.edit_text(
        f"📝 **Editing:** `{key}`\n"
        f"──────────────────────────\n"
        f"**Current Text:**\n`{current}`\n\n"
        f"**To update, use:**\n`/setsetting {key} Your new message text here`\n\n"
        f"_Note: {variables_note}_",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

# --- 🔗 HELPERS (The missing handlers) ---
@router.callback_query(F.data == "admin_update_link")
async def cb_update_link(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="⬅️ Back", callback_data="admin_config"))
    await callback.message.edit_text(
        "🔗 **Update Invite Link**\n"
        "──────────────────────────\n"
        "To set a new invite link for verified users, please send:\n\n"
        "`/setchatlink <your_url_here>`",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@router.callback_query(F.data == "admin_update_id")
async def cb_update_id(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="⬅️ Back", callback_data="admin_stats"))
    await callback.message.edit_text(
        "🔄 **Update Channel ID**\n"
        "──────────────────────────\n"
        "To update the main group ID (Black Channel), send:\n\n"
        "`/blackchannel <channel_id>`",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@router.callback_query(F.data == "admin_broadcast_start")
async def cb_broadcast_start(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="⬅️ Back", callback_data="admin_main"))
    await callback.message.edit_text(
        "📢 **Mass Broadcast**\n"
        "──────────────────────────\n"
        "To send a message to all verified users, send:\n\n"
        "`/broadcast <your message here>`\n\n"
        "⚠️ _Use /stopbroadcast to kill an ongoing process._",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

# --- COMMAND HANDLERS ---
@router.message(Command("setchatlink", prefix="/."))
async def cmd_setchatlink(message: types.Message):
    if not await is_bot_admin(message.bot, message.from_user.id): return
    args = message.text.split(maxsplit=1)
    if len(args) < 2: return
    await set_setting('invite_link', args[1])
    await message.answer(f"🔗 **Invite Link Updated**\nNew: {args[1]}")

@router.message(Command("blackchannel", prefix="/."))
async def cmd_blackchannel(message: types.Message):
    if not await is_bot_admin(message.bot, message.from_user.id): return
    args = message.text.split(maxsplit=1)
    if len(args) < 2: return
    await set_setting('black_channel_id', args[1])
    await message.answer(f"🔄 **Black Channel Updated**\nID: `{args[1]}`")

@router.message(Command("broadcast", prefix="/."))
async def cmd_broadcast(message: types.Message):
    if not await is_bot_admin(message.bot, message.from_user.id): return
    args = message.text.split(maxsplit=1)
    if len(args) < 2: return
    users = await get_all_verified_users()
    await message.answer(f"📢 **Broadcast Initialized**\nTargeting {len(users)} verified members...")
    success, fail = await safe_broadcast(message.bot, users, args[1])
    await message.answer(f"📢 **Broadcast Finished**\nSent: `{success}` | Failed: `{fail}`")

@router.message(Command("setsetting"))
async def cmd_setsetting(message: types.Message):
    if message.from_user.id != MASTER_ADMIN_ID and not await is_bot_admin(message.bot, message.from_user.id): return
    args = message.text.split(maxsplit=2)
    if len(args) < 3: return
    await set_setting(args[1], args[2])
    await message.answer(f"⚙️ **Setting `{args[1]}` Updated**")

@router.message(Command("stopbroadcast"))
async def cmd_stopbroadcast(message: types.Message):
    if message.from_user.id != MASTER_ADMIN_ID and not await is_bot_admin(message.bot, message.from_user.id): return
    from utils.helpers import BROADCAST_STOP
    import utils.helpers as helpers
    helpers.BROADCAST_STOP = True
    await message.answer("⚠️ **Broadcast Killed**\nAll pending messages have been cancelled.")

@router.message(Command("status"))
async def cmd_status(message: types.Message):
    if message.from_user.id != MASTER_ADMIN_ID and not await is_bot_admin(message.bot, message.from_user.id): return
    try:
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        uptime_secs = int(time.time() - START_TIME)
        uptime_str = f"{uptime_secs // 3600}h {(uptime_secs % 3600) // 60}m {uptime_secs % 60}s"
        total, verified = await get_stats()
        await message.answer(
            f"🖥️ **OCI Server Status**\n"
            f"──────────────────────────\n"
            f"⚙️ CPU: `{cpu}%`\n"
            f"🧠 RAM: `{ram.percent}%` used (`{ram.used // 1024 // 1024}MB` / `{ram.total // 1024 // 1024}MB`)\n"
            f"💾 Disk: `{disk.percent}%` used\n"
            f"⏱️ Uptime: `{uptime_str}`\n\n"
            f"👥 Users: `{total}` total | `{verified}` verified"
        )
    except Exception as e:
        await message.answer(f"❌ Status check failed: `{e}`")
