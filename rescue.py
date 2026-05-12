import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

TOKEN = "8502950869:AAGSp_8-dH9SKuZeHBMvRxqtZ8zLcZ5ysgE"
bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message()
async def rescue_handler(message: types.Message):
    print(f"!!! RECEIVED MESSAGE: {message.text} from {message.from_user.id}")
    await message.answer(f"✅ I SEE YOU!\n\nYour ID: `{message.from_user.id}`\nMessage: `{message.text}`")

async def main():
    print("RESCUE BOT STARTING...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
