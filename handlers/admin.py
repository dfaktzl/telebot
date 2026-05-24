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
    builder.row(
        types.InlineKeyboardButton(text="⏱️ Delete Timers", callback_data="admin_timers_menu")
    )
    builder.row(types.InlineKeyboardButton(text="⬅️ Back", callback_data="admin_main"))
    
    await callback.message.edit_text(
        "⚙️ **System Configuration**\n"
        f"──────────────────────────\n"
        "Toggle system features instantly. Changes take effect immediately without restart.",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@router.callback_query(F.data == "admin_timers_menu")
async def cb_timers_menu(callback: types.CallbackQuery):
    welcome = await get_setting('welcome_delete_timer', '600')
    kick = await get_setting('kick_delete_timer', '300')
    ban = await get_setting('ban_delete_timer', '600')
    
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text=f"Welcome: {'❌ OFF' if welcome=='0' else f'{int(welcome)//60}m'}", callback_data="admin_edit_timer_welcome"),
        types.InlineKeyboardButton(text=f"Kick: {'❌ OFF' if kick=='0' else f'{int(kick)//60}m'}", callback_data="admin_edit_timer_kick"),
        types.InlineKeyboardButton(text=f"Ban: {'❌ OFF' if ban=='0' else f'{int(ban)//60}m'}", callback_data="admin_edit_timer_ban")
    )
    builder.row(types.InlineKeyboardButton(text="⬅️ Back", callback_data="admin_config"))
    
    await callback.message.edit_text(
        "⏱️ **Message Delete Timers**\n"
        "──────────────────────────\n"
        "Configure how long notifications stay in chat groups before self-destructing. Set to 0 to disable.",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@router.callback_query(F.data.startswith("admin_edit_timer_"))
async def cb_edit_timer(callback: types.CallbackQuery):
    key = callback.data.replace("admin_edit_timer_", "")
    full_key = f"{key}_delete_timer"
    current = await get_setting(full_key, "0")
    
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="⬅️ Back", callback_data="admin_timers_menu"))
    
    await callback.message.edit_text(
        f"⏱️ **Update Delete Timer:** `{full_key}`\n"
        "──────────────────────────\n"
        f"Current: `{current}` seconds\n\n"
        "To update this timer, send:\n"
        f"`/setsetting {full_key} <seconds>`\n\n"
        "Example:\n"
        f"`/setsetting {full_key} 300` (5 minutes)\n"
        f"`/setsetting {full_key} 0` (disable deletion)",
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
    if message.from_user.id != MASTER_ADMIN_ID and not await is_bot_admin(message.bot, message.from_user.id): return
    args = message.text.split()
    if len(args) < 2:
        await message.answer(
            "ℹ️ **Usage:**\n`/setchatlink [type] <url>`\n\n"
            "Example:\n"
            "`/setchatlink market https://t.me/...`\n"
            "`/setchatlink social https://t.me/...`\n"
            "`/setchatlink https://t.me/...` (sets default link)"
        )
        return
        
    if len(args) == 2:
        # Just URL, set the default
        url = args[1]
        await set_setting('invite_link', url)
        await message.answer(f"🔗 **Default Invite Link Updated**\nNew: {url}")
    elif len(args) >= 3:
        # Both type and URL
        link_type = args[1].lower().strip()
        url = args[2]
        
        # Save type to active types list
        configured_types_str = await get_setting('invite_link_types', '')
        configured_types = [t.strip() for t in configured_types_str.split(',') if t.strip()]
        if link_type not in configured_types:
            configured_types.append(link_type)
            await set_setting('invite_link_types', ','.join(configured_types))
        
        await set_setting(f'invite_link_{link_type}', url)
        await message.answer(f"🔗 **Invite Link Updated** for type `{link_type}`\nNew: {url}")


@router.message(Command("delchatlink", prefix="/."))
async def cmd_delchatlink(message: types.Message):
    if message.from_user.id != MASTER_ADMIN_ID and not await is_bot_admin(message.bot, message.from_user.id): return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("ℹ️ **Usage:**\n`/delchatlink <type>`\n\nExample:\n`/delchatlink market`")
        return
        
    link_type = args[1].lower().strip()
    configured_types_str = await get_setting('invite_link_types', '')
    configured_types = [t.strip() for t in configured_types_str.split(',') if t.strip()]
    if link_type in configured_types:
        configured_types.remove(link_type)
        await set_setting('invite_link_types', ','.join(configured_types))
        await set_setting(f'invite_link_{link_type}', '')
        await message.answer(f"❌ **Invite Link Removed** for type `{link_type}`")
    else:
        await message.answer(f"❌ **Link type `{link_type}` not found.**")

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


# ═══════════════════════════════════════════════════════════════════════════════
#  /noweb / /weboff / /webactive
# ═══════════════════════════════════════════════════════════════════════════════

@router.message(Command("noweb", "weboff", prefix="/."))
async def cmd_noweb(message: types.Message):
    if message.from_user.id != MASTER_ADMIN_ID and not await is_bot_admin(message.bot, message.from_user.id): return
    
    import subprocess
    import logging
    from config import LOG_CHANNEL
    logger = logging.getLogger(__name__)
    
    cmd_name = "/weboff" if message.text and "/weboff" in message.text else "/noweb"
    logger.info(f"ADMIN COMMAND: {cmd_name} triggered by admin {message.from_user.id}")
    
    try:
        # Run PM2 command to stop the dashboard
        res = subprocess.run(
            "pm2 stop repbot-dashboard",
            shell=True,
            capture_output=True,
            text=True
        )
        
        if res.returncode == 0:
            msg = (
                "🛑 **WEB FEATURES DISABLED**\n\n"
                "The Live Administrative & Operations Dashboard has been completely shut down "
                "via PM2. The web server is now offline and no longer accessible.\n\n"
                "To turn it back on, an admin can start it using `/webactive` or via SSH: `pm2 start repbot-dashboard`"
            )
            await message.answer(msg, parse_mode="Markdown")
            
            if LOG_CHANNEL:
                try:
                    from html import escape
                    from datetime import datetime, timezone
                    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

                    fn = escape(message.from_user.first_name) if message.from_user.first_name else "Unknown"
                    ln = escape(message.from_user.last_name) if message.from_user.last_name else "None"
                    un = f"@{escape(message.from_user.username)}" if message.from_user.username else "None"

                    log_html = (
                        f"👮 <b>ADMIN MODERATION</b>\n"
                        f"──────────────────────────\n"
                        f"👤 <b>First Name:</b> {fn}\n"
                        f"👤 <b>Last Name:</b> {ln}\n"
                        f"🏷️ <b>Username:</b> {un}\n"
                        f"🆔 <b>User ID:</b> <code>{message.from_user.id}</code>\n"
                        f"⏱️ <b>Time:</b> <code>{now_str}</code>\n"
                        f"──────────────────────────\n"
                        f"📋 <b>Action:</b> Web Dashboard stopped via Telegram command <code>{escape(cmd_name)}</code>"
                    )
                    await message.bot.send_message(
                        chat_id=LOG_CHANNEL,
                        text=log_html,
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
        else:
            error_msg = res.stderr or res.stdout
            logger.error(f"Failed to stop dashboard via PM2: {error_msg}")
            await message.answer(
                f"❌ Failed to disable web features via PM2.\n`Error: {error_msg}`",
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Error executing shutdown command: {e}")
        await message.answer(f"❌ Exception occurred: `{str(e)}`", parse_mode="Markdown")


@router.message(Command("webactive", prefix="/."))
async def cmd_webactive(message: types.Message):
    if message.from_user.id != MASTER_ADMIN_ID and not await is_bot_admin(message.bot, message.from_user.id): return
    
    import subprocess
    import asyncio
    import logging
    from config import LOG_CHANNEL
    logger = logging.getLogger(__name__)
    logger.info(f"ADMIN COMMAND: /webactive triggered by admin {message.from_user.id}")
    
    # Reply immediately that activation is starting
    status_message = await message.answer(
        "⏳ **Activating Web Dashboard...**\n"
        "Initializing server process via PM2. Please wait while the dashboard boots up...",
        parse_mode="Markdown"
    )
    
    try:
        # Run PM2 command to start the dashboard
        res = subprocess.run(
            "pm2 start repbot-dashboard",
            shell=True,
            capture_output=True,
            text=True
        )
        
        if res.returncode == 0:
            # Wait a decent amount of time (5 seconds) for the server to bind port and start
            await asyncio.sleep(5)
            
            # Check if PM2 shows it's online
            status_res = subprocess.run(
                "pm2 show repbot-dashboard",
                shell=True,
                capture_output=True,
                text=True
            )
            
            if "status" in status_res.stdout.lower() and "online" in status_res.stdout.lower():
                msg = (
                    "🚀 **WEB FEATURES ENABLED**\n\n"
                    "The Live Administrative & Operations Dashboard is now online and active.\n"
                    "You can access the dashboard securely using your OCI SSH key pair + password 2FA."
                )
                await status_message.edit_text(msg, parse_mode="Markdown")
                
                if LOG_CHANNEL:
                    try:
                        from html import escape
                        from datetime import datetime, timezone
                        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

                        fn = escape(message.from_user.first_name) if message.from_user.first_name else "Unknown"
                        ln = escape(message.from_user.last_name) if message.from_user.last_name else "None"
                        un = f"@{escape(message.from_user.username)}" if message.from_user.username else "None"

                        log_html = (
                            f"👮 <b>ADMIN MODERATION</b>\n"
                            f"──────────────────────────\n"
                            f"👤 <b>First Name:</b> {fn}\n"
                            f"👤 <b>Last Name:</b> {ln}\n"
                            f"🏷️ <b>Username:</b> {un}\n"
                            f"🆔 <b>User ID:</b> <code>{message.from_user.id}</code>\n"
                            f"⏱️ <b>Time:</b> <code>{now_str}</code>\n"
                            f"──────────────────────────\n"
                            f"📋 <b>Action:</b> Web Dashboard started via Telegram command <code>/webactive</code>"
                        )
                        await message.bot.send_message(
                            chat_id=LOG_CHANNEL,
                            text=log_html,
                            parse_mode="HTML"
                        )
                    except Exception:
                        pass
                return
            else:
                error_msg = "PM2 process started but did not reach online status."
                logger.error(f"Dashboard start check failed: {error_msg}\nStdout: {status_res.stdout}")
                raise Exception(error_msg)
        else:
            error_msg = res.stderr or res.stdout
            logger.error(f"Failed to start dashboard via PM2: {error_msg}")
            raise Exception(error_msg)
            
    except Exception as e:
        logger.error(f"Error starting dashboard, defaulting to shutdown: {e}")
        await status_message.edit_text(
            f"⚠️ **Error starting web features**: `{str(e)}`\n"
            "🚨 Defaulting to **weboff / shutdown** mode to ensure safety...",
            parse_mode="Markdown"
        )
        # Call stop command to ensure it's completely down and safe
        try:
            subprocess.run("pm2 stop repbot-dashboard", shell=True, capture_output=True)
            if LOG_CHANNEL:
                try:
                    from html import escape
                    from datetime import datetime, timezone
                    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

                    fn = escape(message.from_user.first_name) if message.from_user.first_name else "Unknown"
                    ln = escape(message.from_user.last_name) if message.from_user.last_name else "None"
                    un = f"@{escape(message.from_user.username)}" if message.from_user.username else "None"

                    log_html = (
                        f"⚠️ <b>ADMIN WARNING</b>\n"
                        f"──────────────────────────\n"
                        f"👤 <b>First Name:</b> {fn}\n"
                        f"👤 <b>Last Name:</b> {ln}\n"
                        f"🏷️ <b>Username:</b> {un}\n"
                        f"🆔 <b>User ID:</b> <code>{message.from_user.id}</code>\n"
                        f"⏱️ <b>Time:</b> <code>{now_str}</code>\n"
                        f"──────────────────────────\n"
                        f"📋 <b>Action:</b> /webactive failed and defaulted to safety shutdown (weboff).\n"
                        f"❌ <b>Error:</b> <code>{escape(str(e))}</code>"
                    )
                    await message.bot.send_message(
                        chat_id=LOG_CHANNEL,
                        text=log_html,
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
        except Exception as shutdown_err:
            logger.error(f"Failed to perform safety shutdown: {shutdown_err}")
