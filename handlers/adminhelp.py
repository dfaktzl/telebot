import logging
from datetime import datetime, timezone
from html import escape

from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile

from database import (
    get_user_by_id_or_username,
    add_or_update_user,
    create_admin_help_ticket,
    get_pending_help_ticket_by_user,
    get_user_id_by_help_message,
    add_help_message_mapping,
    update_help_ticket_last_messages,
    close_admin_help_ticket,
    bind_help_ticket_to_discussion,
    add_help_chat_message,
    get_help_chat_history,
    delete_help_chat_history
)
from config import LOG_CHANNEL

logger = logging.getLogger(__name__)
router = Router()

MASTER_ADMIN_ID = 834606708  # @TryForgetThis account default

class AdminHelpStates(StatesGroup):
    waiting_for_help_msg = State()


# ==============================================================================
#  DISCUSSION GROUP FORWARD LISTENER
# ==============================================================================

@router.message(
    F.chat.type.in_({"group", "supergroup"}),
    (F.forward_from_chat.id == LOG_CHANNEL) | (F.sender_chat.id == LOG_CHANNEL)
)
async def handle_help_discussion_forward(message: types.Message):
    """Listens for support logs forwarded from the Channel to the linked Discussion Group.
    Resolves the associated pending support ticket, binds it to this discussion thread,
    and copies the user's original inquiry as an inline reply."""
    channel_msg_id = message.forward_from_message_id
    if not channel_msg_id and message.reply_to_message:
        channel_msg_id = message.reply_to_message.forward_from_message_id

    if channel_msg_id:
        user_id = await bind_help_ticket_to_discussion(channel_msg_id, message.chat.id, message.message_id)
        if user_id:
            await add_help_message_mapping(message.message_id, user_id)
            logger.info(f"SUPPORT: Bound ticket for user {user_id} to discussion thread {message.message_id} in group {message.chat.id}")

            # Fetch the ticket details to get the user's original inquiry message ID
            ticket = await get_pending_help_ticket_by_user(user_id)
            if ticket and ticket.get('user_message_id'):
                try:
                    # Copy the user's actual inquiry message to the discussion group thread
                    inquiry_copy = await message.bot.copy_message(
                        chat_id=message.chat.id,
                        from_chat_id=user_id,
                        message_id=ticket['user_message_id'],
                        reply_to_message_id=message.message_id
                    )
                    # Add message mapping for the copied inquiry message
                    await add_help_message_mapping(inquiry_copy.message_id, user_id)
                    # Update ticket's admin_message_id to this copied inquiry message ID
                    # so that subsequent user replies thread nicely under it!
                    await update_help_ticket_last_messages(user_id, admin_message_id=inquiry_copy.message_id)
                    logger.info(f"SUPPORT: Copied original inquiry to discussion thread for user {user_id}")
                except Exception as copy_err:
                    logger.warning(f"Failed to copy original inquiry to discussion group: {copy_err}")


# ==============================================================================
#  USER PRIVATE COMMANDS: /help & /support
# ==============================================================================

@router.message(Command("help", "support"), F.chat.type == "private")
async def cmd_help(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username
    await add_or_update_user(user_id, username, message.from_user.first_name, message.from_user.last_name)

    # 1. Check if already has an open help ticket
    active_ticket = await get_pending_help_ticket_by_user(user_id)
    if active_ticket:
        await message.answer(
            "\u23F3 <b>PENDING SUPPORT SESSION OPEN</b>\n"
            "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
            "You already have an active support ticket open. "
            "You can type message replies directly in this chat, and they will be forwarded to the admin team.",
            parse_mode="HTML"
        )
        return

    # 2. Enter FSM state
    await state.set_state(AdminHelpStates.waiting_for_help_msg)
    await message.answer(
        "\u2753 <b>ADMIN HELP & SUPPORT</b>\n"
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
        "Need to speak with an administrator? Please explain your issue, question, or inquiry in detail.\n\n"
        "\u26A0 <b>INSTRUCTION:</b>\n"
        "Please write your inquiry and attach any evidence in a <b>SINGLE MESSAGE</b> now.\n\n"
        "<i>An administrator will review your ticket and reply directly to you through this chat.</i>",
        parse_mode="HTML"
    )


# ==============================================================================
#  SUPPORT INQUIRY PROMPT RESPONSE HANDLER
# ==============================================================================

@router.message(AdminHelpStates.waiting_for_help_msg, F.chat.type == "private")
async def process_help_request(message: types.Message, state: FSMContext, bot: Bot):
    # Abort if they run another command
    if message.text and message.text.startswith("/"):
        await state.clear()
        return

    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name or ""
    
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Record user's initial inquiry in the chat history DB
    user_display_name = f"@{username}" if username else f"{first_name} {last_name}".strip() or "User"
    inquiry_text = message.text or message.caption or "(Media/Attachment)"
    await add_help_chat_message(user_id, user_display_name, "user", inquiry_text)

    # Format header for Admin Ticket
    fn = escape(first_name) if first_name else "Unknown"
    ln = escape(last_name) if last_name else "None"
    un = f"@{escape(username)}" if username else "None"

    admin_header_text = (
        f"\U0001F3AB <b>NEW SUPPORT TICKET</b>\n"
        f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
        f"\U0001F464 <b>First Name:</b> {fn}\n"
        f"\U0001F464 <b>Last Name:</b> {ln}\n"
        f"\U0001F3F7\ufe0f <b>Username:</b> {un}\n"
        f"\U0001F194 <b>User ID:</b> <code>{user_id}</code>\n"
        f"\u23F1\ufe0f <b>Time:</b> <code>{now_str}</code>\n"
        f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
        f"\U0001F447 <i>Below is the support inquiry submitted by the user. You can reply directly to any message in this thread to converse, or send <code>/close</code> to resolve the ticket.</i>"
    )

    try:
        header_msg = await bot.send_message(
            chat_id=MASTER_ADMIN_ID,
            text=admin_header_text,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Failed to send support ticket header to admin: {e}")
        await message.answer("\u274C <b>SYSTEM ERROR:</b> Could not reach the support desk. Please try again later.", parse_mode="HTML")
        await state.clear()
        return

    # Copy user inquiry to verifier admin
    try:
        admin_inquiry_msg = await bot.copy_message(
            chat_id=MASTER_ADMIN_ID,
            from_chat_id=user_id,
            message_id=message.message_id,
            reply_to_message_id=header_msg.message_id
        )
    except Exception as e:
        logger.error(f"Failed to copy support message to admin: {e}")
        await message.answer("\u274C <b>TRANSMISSION ERROR:</b> Could not deliver your message. Please check and try again.", parse_mode="HTML")
        await state.clear()
        return

    # Add message mappings
    await add_help_message_mapping(header_msg.message_id, user_id)
    await add_help_message_mapping(admin_inquiry_msg.message_id, user_id)

    # Post request log submission to the LOG_CHANNEL
    channel_msg_id = None
    if LOG_CHANNEL:
        try:
            log_text = (
                f"\U0001F3AB <b>SUPPORT TICKET SUBMITTED</b>\n"
                f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
                f"\U0001F464 <b>First Name:</b> {fn}\n"
                f"\U0001F464 <b>Last Name:</b> {ln}\n"
                f"\U0001F3F7\ufe0f <b>Username:</b> {un}\n"
                f"\U0001F194 <b>User ID:</b> <code>{user_id}</code>\n"
                f"\u23F1\ufe0f <b>Time:</b> <code>{now_str}</code>\n"
                f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
                f"\U0001F4CB <b>Action:</b> Support session ticket opened and routed to admin team."
            )
            log_msg = await bot.send_message(
                chat_id=LOG_CHANNEL,
                text=log_text,
                parse_mode="HTML"
            )
            channel_msg_id = log_msg.message_id
        except Exception as log_err:
            logger.warning(f"Failed to log support submission to channel: {log_err}")

    # Save ticket in SQLite with the log channel's message ID for dynamic binding
    await create_admin_help_ticket(user_id, admin_inquiry_msg.message_id, message.message_id, channel_msg_id)

    # Clear FSM State
    await state.clear()

    # Reply to User
    await message.answer(
        "\u2705 <b>SUPPORT INQUIRY RECEIVED</b>\n"
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
        "Your help request has been sent to the administrators.\n\n"
        "\U0001F4AC <i>You can now text directly in this chat, and the bot will act as a secure middleman forwarding your messages to the admin team. Please wait for a reply.</i>",
        parse_mode="HTML"
    )


# ==============================================================================
#  MIDDLEMAN: ADMIN -> USER FORWARDER & RESOLVE ACTION
# ==============================================================================

@router.message(F.reply_to_message)
async def middleman_help_admin_to_user(message: types.Message, bot: Bot):
    replied_msg_id = message.reply_to_message.message_id
    
    # Resolve user_id from support message mapping table
    user_id = await get_user_id_by_help_message(replied_msg_id)
    if not user_id:
        return

    # Check if close command
    if message.text and message.text.strip().lower() in ("/close", "/resolved"):
        ticket = await get_pending_help_ticket_by_user(user_id)
        if not ticket:
            await message.reply("\u274C This support ticket is no longer active.")
            return

        # 1. Update status in database
        await close_admin_help_ticket(user_id)

        # Retrieve user details for logs
        user_info = await get_user_by_id_or_username(user_id)
        u_username = user_info['username'] if user_info else None
        u_first = user_info['first_name'] if user_info and 'first_name' in user_info.keys() else "Unknown"
        u_last = user_info['last_name'] if user_info and 'last_name' in user_info.keys() else ""
        
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        
        u_fn = escape(u_first) if u_first else "Unknown"
        u_ln = escape(u_last) if u_last else "None"
        u_un = f"@{escape(u_username)}" if u_username else "None"

        # 2. Notify user
        try:
            await bot.send_message(
                chat_id=user_id,
                text="\U0001F6AA <b>SUPPORT TICKET CLOSED</b>\n"
                     "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
                     "Your active support session has been closed by the administrator.\n\n"
                     "\u2139\ufe0f <i>If you need further help in the future, you can open a new request using /help.</i>",
                 parse_mode="HTML"
             )
        except Exception as notify_err:
            logger.warning(f"Failed to notify user {user_id} of ticket closure: {notify_err}")

        # 3. Confirm to admin
        await message.reply(
            f"\u2705 <b>Support ticket closed!</b>\n"
            f"Active session resolved and ticket closed for user ID <code>{user_id}</code>."
        )

        # 4. Log closure to logging channel & compile transcript
        if LOG_CHANNEL:
            try:
                admin_username = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name or "Admin"
                log_text = (
                    f"\U0001F6AA <b>SUPPORT TICKET CLOSED / RESOLVED</b>\n"
                    f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
                    f"\U0001F464 <b>First Name:</b> {u_fn}\n"
                    f"\U0001F464 <b>Last Name:</b> {u_ln}\n"
                    f"\U0001F3F7\ufe0f <b>Username:</b> {u_un}\n"
                    f"\U0001F194 <b>User ID:</b> <code>{user_id}</code>\n"
                    f"\u23F1\ufe0f <b>Time:</b> <code>{now_str}</code>\n"
                    f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
                    f"\U0001F46E <b>Closed By:</b> {escape(admin_username)} (ID: {message.from_user.id})"
                )

                # Fetch chat history
                chat_history = await get_help_chat_history(user_id)
                
                if chat_history:
                    bubbles_html = []
                    for h_msg in chat_history:
                        h_role = h_msg.get('sender_role', 'user')
                        h_name = escape(h_msg.get('sender_name', 'Unknown'))
                        h_text = escape(h_msg.get('message_text', ''))
                        h_ts = escape(h_msg.get('timestamp', ''))
                        
                        row_class = "user" if h_role == "user" else "admin"
                        bubbles_html.append(f"""
        <div class="message-row {row_class}">
            <div class="bubble">
                <span class="sender-name">{h_name}</span>
                <div class="message-text">{h_text}</div>
                <span class="timestamp">{h_ts}</span>
            </div>
        </div>
                        """)
                    
                    chat_bubbles_joined = "\n".join(bubbles_html)
                    
                    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Support Ticket Transcript - {user_id}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #f5f5f7;
            color: #1d1d1f;
            margin: 0;
            padding: 20px;
            display: flex;
            justify-content: center;
        }}
        .container {{
            width: 100%;
            max-width: 700px;
            background: #ffffff;
            border-radius: 16px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }}
        .header {{
            background: linear-gradient(135deg, #1d1d1f, #434343);
            color: #ffffff;
            padding: 24px;
            border-bottom: 1px solid #e5e5ea;
        }}
        .header h1 {{
            margin: 0 0 8px 0;
            font-size: 20px;
            font-weight: 600;
            letter-spacing: -0.5px;
        }}
        .header-meta {{
            font-size: 13px;
            color: #aeaeb2;
            line-height: 1.6;
        }}
        .header-meta span {{
            color: #ffffff;
            font-weight: 500;
        }}
        .chat-area {{
            padding: 24px;
            background-color: #f9f9fb;
            display: flex;
            flex-direction: column;
            gap: 16px;
            min-height: 150px;
        }}
        .message-row {{
            display: flex;
            width: 100%;
        }}
        .message-row.user {{
            justify-content: flex-start;
        }}
        .message-row.admin {{
            justify-content: flex-end;
        }}
        .bubble {{
            max-width: 75%;
            padding: 12px 16px;
            border-radius: 18px;
            position: relative;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
            line-height: 1.45;
            font-size: 15px;
            word-wrap: break-word;
        }}
        .message-row.user .bubble {{
            background-color: #e5e5ea;
            color: #000000;
            border-bottom-left-radius: 4px;
        }}
        .message-row.admin .bubble {{
            background-color: #007aff;
            color: #ffffff;
            border-bottom-right-radius: 4px;
        }}
        .sender-name {{
            font-size: 11px;
            font-weight: 600;
            margin-bottom: 4px;
            display: block;
            letter-spacing: 0.2px;
        }}
        .message-row.user .sender-name {{
            color: #8e8e93;
        }}
        .message-row.admin .sender-name {{
            color: rgba(255, 255, 255, 0.8);
            text-align: right;
        }}
        .message-text {{
            white-space: pre-wrap;
        }}
        .timestamp {{
            font-size: 10px;
            margin-top: 4px;
            display: block;
        }}
        .message-row.user .timestamp {{
            color: #aeaeb2;
            text-align: left;
        }}
        .message-row.admin .timestamp {{
            color: rgba(255, 255, 255, 0.7);
            text-align: right;
        }}
        .footer {{
            padding: 16px;
            text-align: center;
            font-size: 12px;
            color: #8e8e93;
            background-color: #ffffff;
            border-top: 1px solid #f2f2f7;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Support Chat Transcript</h1>
            <div class="header-meta">
                <div>User ID: <span>{user_id}</span></div>
                <div>User Username: <span>{u_un}</span></div>
                <div>User Display Name: <span>{u_fn} {u_ln}</span></div>
                <div>Closed At: <span>{now_str}</span></div>
                <div>Closed By: <span>{admin_username}</span></div>
            </div>
        </div>
        <div class="chat-area">
{chat_bubbles_joined}
        </div>
        <div class="footer">
            Generated securely by Reputation Bot Admin Help System
        </div>
    </div>
</body>
</html>"""
                    
                    transcript_file = BufferedInputFile(
                        html_content.encode("utf-8"),
                        filename=f"ticket_transcript_{user_id}.html"
                    )
                    
                    await bot.send_document(
                        chat_id=LOG_CHANNEL,
                        document=transcript_file,
                        caption=log_text,
                        parse_mode="HTML"
                    )
                else:
                    await bot.send_message(
                        chat_id=LOG_CHANNEL,
                        text=log_text,
                        parse_mode="HTML"
                    )
            except Exception as log_err:
                logger.warning(f"Failed to log support closure or send transcript: {log_err}")
            finally:
                # Perform post-resolution garbage collection
                try:
                    await delete_help_chat_history(user_id)
                except Exception as gc_err:
                    logger.warning(f"Failed to delete help chat history: {gc_err}")
        else:
            # If log channel not configured, still garbage collect
            try:
                await delete_help_chat_history(user_id)
            except Exception as gc_err:
                logger.warning(f"Failed to delete help chat history: {gc_err}")
        return

    # -- CONVERSATIONAL FORWARD ADMIN -> USER --
    ticket = await get_pending_help_ticket_by_user(user_id)
    if not ticket:
        await message.reply("\u274C This support ticket is no longer active.")
        return

    try:
        # Copy message to user's DM as reply to their last message
        user_msg = await bot.copy_message(
            chat_id=user_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            reply_to_message_id=ticket['user_message_id']
        )
        
        # Record admin's reply in chat history
        admin_name = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name or "Admin"
        reply_text = message.text or message.caption or "(Media/Attachment)"
        await add_help_chat_message(user_id, admin_name, "admin", reply_text)

        # Add message mapping & update ticket
        await add_help_message_mapping(message.message_id, user_id)
        await update_help_ticket_last_messages(
            user_id,
            admin_chat_id=message.chat.id,
            admin_message_id=message.message_id,
            user_message_id=user_msg.message_id
        )
    except Exception as e:
        logger.error(f"Failed to forward admin support reply to user {user_id}: {e}")
        await message.reply("\u274C Failed to deliver message to user's DM. (They may have blocked the bot).")


# ==============================================================================
#  MIDDLEMAN: USER -> ADMIN FORWARDER (CONVERSATIONAL REPLY)
# ==============================================================================

@router.message(F.chat.type == "private")
async def middleman_help_user_to_admin(message: types.Message, bot: Bot):
    user_id = message.from_user.id
    
    # Ignore commands
    if message.text and message.text.startswith("/"):
        return

    # Check if user has an active support ticket
    ticket = await get_pending_help_ticket_by_user(user_id)
    if not ticket:
        return

    admin_chat_id = ticket.get('admin_chat_id', MASTER_ADMIN_ID) or MASTER_ADMIN_ID

    try:
        # Copy the user's message to admin as reply to last admin message
        admin_msg = await bot.copy_message(
            chat_id=admin_chat_id,
            from_chat_id=user_id,
            message_id=message.message_id,
            reply_to_message_id=ticket['admin_message_id']
        )

        # Record user's reply in the chat history DB
        user_name = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name or "User"
        reply_text = message.text or message.caption or "(Media/Attachment)"
        await add_help_chat_message(user_id, user_name, "user", reply_text)

        # Add message mapping & update ticket
        await add_help_message_mapping(admin_msg.message_id, user_id)
        await update_help_ticket_last_messages(user_id, admin_message_id=admin_msg.message_id, user_message_id=message.message_id)
    except Exception as e:
        logger.error(f"Failed to forward user support message to admin: {e}")
