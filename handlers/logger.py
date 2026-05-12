from aiogram import Router, types

router = Router()

@router.message()
async def global_logger(message: types.Message):
    """Logs everything the bot sees for debugging. Included last to not block other handlers."""
    print(f"LOG: Message from {message.from_user.id} in {message.chat.id} ({message.chat.type}): {message.text}")
