import logging
import asyncio
from datetime import datetime, timezone
from html import escape

from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from database import (
    get_user_by_id_or_username,
    verify_user,
    add_or_update_user,
    get_pending_ticket_by_user,
    create_market_verify_ticket,
    get_user_id_by_admin_message,
    add_market_message_mapping,
    update_ticket_last_messages,
    verify_market_ticket,
    bind_market_ticket_to_discussion
)
from config import LOG_CHANNEL

logger = logging.getLogger(__name__)
router = Router()

MASTER_ADMIN_ID = 834606708  # @TryForgetThis account default

class MarketVerifyStates(StatesGroup):
    waiting_for_proof = State()


# ═══════════════════════════════════════════════════════════════════════════════
#  DISCUSSION GROUP FORWARD LISTENER
# ═══════════════════════════════════════════════════════════════════════════════

@router.message(
    F.chat.type.in_({"group", "supergroup"}),
    (F.forward_from_chat.id == LOG_CHANNEL) | (F.sender_chat.id == LOG_CHANNEL)
)
async def handle_discussion_forward(message: types.Message):
    """Listens for logs forwarded from the Channel to the linked Discussion Group.
    Resolves the associated pending ticket and binds it to this discussion thread,
    and copies the user's original proof as an inline reply."""
    channel_msg_id = message.forward_from_message_id
    if not channel_msg_id and message.reply_to_message:
        channel_msg_id = message.reply_to_message.forward_from_message_id

    if channel_msg_id:
        user_id = await bind_market_ticket_to_discussion(channel_msg_id, message.chat.id, message.message_id)
        if user_id:
            await add_market_message_mapping(message.message_id, user_id)
            logger.info(f"MARKET VERIFY: Bound ticket for user {user_id} to discussion thread {message.message_id} in group {message.chat.id}")

            # Fetch the ticket details to get the user's original proof message ID
            ticket = await get_pending_ticket_by_user(user_id)
            if ticket and ticket.get('user_message_id'):
                try:
                    # Copy proof to the discussion group thread
                    proof_copy = await message.bot.copy_message(
                        chat_id=message.chat.id,
                        from_chat_id=user_id,
                        message_id=ticket['user_message_id'],
                        reply_to_message_id=message.message_id
                    )
                    await add_market_message_mapping(proof_copy.message_id, user_id)
                    await update_ticket_last_messages(user_id, admin_message_id=proof_copy.message_id)
                    logger.info(f"MARKET VERIFY: Copied proof to discussion thread for user {user_id}")
                except Exception as copy_err:
                    logger.warning(f"Failed to copy proof to discussion group: {copy_err}")


# ═══════════════════════════════════════════════════════════════════════════════
#  USER PRIVATE COMMAND: /marketverify
# ═══════════════════════════════════════════════════════════════════════════════

@router.message(Command("marketverify"), F.chat.type == "private")
async def cmd_marketverify(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username
    await add_or_update_user(user_id, username, message.from_user.first_name, message.from_user.last_name)

    # 1. Check if already verified
    user = await get_user_by_id_or_username(user_id)
    if user and user['is_verified'] == 1:
        await message.answer(
            "✅ <b>ALREADY VERIFIED</b>\n"
            "──────────────────────────\n"
            "Your profile has already been verified and whitelisted. "
            "You can claim your entry link anytime using the <code>/link</code> command.",
            parse_mode="HTML"
        )
        return

    # 2. Check if already has an open ticket
    active_ticket = await get_pending_ticket_by_user(user_id)
    if active_ticket:
        await message.answer(
            "⏳ <b>PENDING REQUEST OPEN</b>\n"
            "──────────────────────────\n"
            "You already have a pending verification request. "
            "You can type message replies directly in this chat, and they will be forwarded to the verifier.",
            parse_mode="HTML"
        )
        return

    # 3. Enter proof submission state
    await state.set_state(MarketVerifyStates.waiting_for_proof)
    await message.answer(
        "📥 <b>MARKET VERIFICATION REQUEST</b>\n"
        "──────────────────────────\n"
        "To request entry to the Whitelisted Market & Social Chat, please submit your verification proof.\n\n"
        "⚠️ <b>INSTRUCTION:</b>\n"
        "Please send all screenshots, photos, and verification evidence in a <b>SINGLE MESSAGE</b> now.\n\n"
        "<i>(You can attach multiple screenshots/photos in a single image layout, or send a combined photo caption).</i>",
        parse_mode="HTML"
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  PROOF MESSAGE HANDLER
# ═══════════════════════════════════════════════════════════════════════════════

@router.message(MarketVerifyStates.waiting_for_proof, F.chat.type == "private")
async def process_proof(message: types.Message, state: FSMContext, bot: Bot):
    if message.text and message.text.startswith("/"):
        await state.clear()
        return

    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name or ""
    
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Send Ticket Header to Verifier Admin private chat (fallback first)
    fn = escape(first_name) if first_name else "Unknown"
    ln = escape(last_name) if last_name else "None"
    un = f"@{escape(username)}" if username else "None"

    admin_header_text = (
        f"📩 <b>NEW VERIFICATION TICKET</b>\n"
        f"──────────────────────────\n"
        f"👤 <b>First Name:</b> {fn}\n"
        f"👤 <b>Last Name:</b> {ln}\n"
        f"🏷️ <b>Username:</b> {un}\n"
        f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
        f"⏱️ <b>Time:</b> <code>{now_str}</code>\n"
        f"──────────────────────────\n"
        f"👇 <i>Below is the verification proof submitted by the user. You can reply directly to any of the messages to converse with them, or send <code>/verified</code> to approve.</i>"
    )

    try:
        header_msg = await bot.send_message(
            chat_id=MASTER_ADMIN_ID,
            text=admin_header_text,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Failed to send verification ticket header to admin: {e}")
        await message.answer("❌ <b>SYSTEM ERROR:</b> Could not contact the verification desk. Please try again later.", parse_mode="HTML")
        await state.clear()
        return

    try:
        admin_proof_msg = await bot.copy_message(
            chat_id=MASTER_ADMIN_ID,
            from_chat_id=user_id,
            message_id=message.message_id,
            reply_to_message_id=header_msg.message_id
        )
    except Exception as e:
        logger.error(f"Failed to copy proof message to admin: {e}")
        await message.answer("❌ <b>TRANSMISSION ERROR:</b> Could not deliver your proof. Please check your attachments and try again.", parse_mode="HTML")
        await state.clear()
        return

    # Map header and proof message IDs to user_id
    await add_market_message_mapping(header_msg.message_id, user_id)
    await add_market_message_mapping(admin_proof_msg.message_id, user_id)

    # Post request log submission to the LOG_CHANNEL
    channel_msg_id = None
    if LOG_CHANNEL:
        try:
            log_text = (
                f"📥 <b>MARKET VERIFICATION REQUEST SUBMITTED</b>\n"
                f"──────────────────────────\n"
                f"👤 <b>First Name:</b> {fn}\n"
                f"👤 <b>Last Name:</b> {ln}\n"
                f"🏷️ <b>Username:</b> {un}\n"
                f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
                f"⏱️ <b>Time:</b> <code>{now_str}</code>\n"
                f"──────────────────────────\n"
                f"📋 <b>Action:</b> Verification ticket opened and routed to verifier."
            )
            log_msg = await bot.send_message(
                chat_id=LOG_CHANNEL,
                text=log_text,
                parse_mode="HTML"
            )
            channel_msg_id = log_msg.message_id
        except Exception as log_err:
            logger.warning(f"Failed to log verification request to channel: {log_err}")

    # Save ticket in database
    await create_market_verify_ticket(user_id, admin_proof_msg.message_id, message.message_id, channel_msg_id)

    # Clear FSM State
    await state.clear()

    # Reply to User
    await message.answer(
        "✅ <b>PROOF SUBMITTED SUCCESSFULLY</b>\n"
        "──────────────────────────\n"
        "Your verification ticket has been generated and securely sent to the verifiers.\n\n"
        "💬 <i>You can now text directly in this chat, and the bot will act as a secure middleman forwarding your messages to the verifier admin. Please wait for them to review and reply.</i>",
        parse_mode="HTML"
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  MIDDLEMAN: ADMIN -> USER FORWARDER & VERIFICATION ACTION
# ═══════════════════════════════════════════════════════════════════════════════

@router.message(F.reply_to_message)
async def middleman_admin_to_user(message: types.Message, bot: Bot):
    replied_msg_id = message.reply_to_message.message_id
    
    # Resolve user_id from message mapping table
    user_id = await get_user_id_by_admin_message(replied_msg_id)
    if not user_id:
        return

    # Check if verification command
    if message.text and message.text.strip().lower() == "/verified":
        ticket = await get_pending_ticket_by_user(user_id)
        if not ticket:
            await message.reply("❌ This ticket is no longer active (user may be verified or ticket closed).")
            return

        success_id = await verify_user(user_id, status=1, vouched_by=message.from_user.id)
        if not success_id:
            await message.reply("❌ Verification failed (database update error).")
            return

        await verify_market_ticket(user_id)

        # Fetch details for logs
        user_info = await get_user_by_id_or_username(user_id)
        u_username = user_info['username'] if user_info else None
        u_first = user_info['first_name'] if user_info and 'first_name' in user_info.keys() else "Unknown"
        u_last = user_info['last_name'] if user_info and 'last_name' in user_info.keys() else ""
        
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        
        u_fn = escape(u_first) if u_first else "Unknown"
        u_ln = escape(u_last) if u_last else "None"
        u_un = f"@{escape(u_username)}" if u_username else "None"

        # Notify user
        try:
            await bot.send_message(
                chat_id=user_id,
                text="🎉 <b>MARKET VERIFICATION APPROVED!</b>\n"
                     "──────────────────────────\n"
                     "Your verification request has been successfully reviewed and approved by the verifiers.\n\n"
                     "🔗 <i>You are now whitelisted. Use the <code>/link</code> command here to get your invite link!</i>",
                parse_mode="HTML"
            )
        except Exception as notify_err:
            logger.warning(f"Failed to notify verified user {user_id}: {notify_err}")

        # Confirm to Admin / Discussion Group
        await message.reply(
            f"✅ <b>User whitelisted successfully!</b>\n"
            f"Profile whitelisted and ticket closed for user ID <code>{user_id}</code>."
        )

        # Log whitelisting to the logging channel
        if LOG_CHANNEL:
            try:
                log_text = (
                    f"🟢 <b>MARKET VERIFICATION APPROVED</b>\n"
                    f"──────────────────────────\n"
                    f"👤 <b>First Name:</b> {u_fn}\n"
                    f"👤 <b>Last Name:</b> {u_ln}\n"
                    f"🏷️ <b>Username:</b> {u_un}\n"
                    f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
                    f"⏱️ <b>Time:</b> <code>{now_str}</code>\n"
                    f"──────────────────────────\n"
                    f"👮 <b>Approved By:</b> Admin (ID: {message.from_user.id})"
                )
                await bot.send_message(
                    chat_id=LOG_CHANNEL,
                    text=log_text,
                    parse_mode="HTML"
                )
            except Exception as log_err:
                logger.warning(f"Failed to log verification approval: {log_err}")
        return

    # ── CONVERSATIONAL FORWARD ADMIN -> USER ──
    ticket = await get_pending_ticket_by_user(user_id)
    if not ticket:
        await message.reply("❌ This ticket is no longer active.")
        return

    try:
        user_msg = await bot.copy_message(
            chat_id=user_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            reply_to_message_id=ticket['user_message_id']
        )
        
        # Update mappings
        await add_market_message_mapping(message.message_id, user_id)
        await update_ticket_last_messages(user_id, admin_message_id=message.message_id, user_message_id=user_msg.message_id)
    except Exception as e:
        logger.error(f"Failed to forward admin reply to user {user_id}: {e}")
        await message.reply("❌ Failed to deliver message to user's DM. (They may have blocked the bot).")


# ═══════════════════════════════════════════════════════════════════════════════
#  MIDDLEMAN: USER -> ADMIN FORWARDER (CONVERSATIONAL REPLY)
# ═══════════════════════════════════════════════════════════════════════════════

@router.message(F.chat.type == "private")
async def middleman_user_to_admin(message: types.Message, bot: Bot):
    user_id = message.from_user.id
    
    # Ignore commands
    if message.text and message.text.startswith("/"):
        return

    # Check if user has an active pending ticket
    ticket = await get_pending_ticket_by_user(user_id)
    if not ticket:
        return

    admin_chat_id = ticket.get('admin_chat_id', MASTER_ADMIN_ID) or MASTER_ADMIN_ID

    try:
        admin_msg = await bot.copy_message(
            chat_id=admin_chat_id,
            from_chat_id=user_id,
            message_id=message.message_id,
            reply_to_message_id=ticket['admin_message_id']
        )

        # Update mappings
        await add_market_message_mapping(admin_msg.message_id, user_id)
        await update_ticket_last_messages(user_id, admin_message_id=admin_msg.message_id, user_message_id=message.message_id)
    except Exception as e:
        logger.error(f"Failed to forward user message to admin: {e}")
