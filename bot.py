import os
import asyncio
from maxapi import Bot, Dispatcher
from maxapi.types import MessageCreated

# Токен берется из переменной окружения (bothosting сам его подставит)
TOKEN = os.environ.get("BOT_TOKEN")

bot = Bot(TOKEN)
dp = Dispatcher()

@dp.message_created()
async def echo_handler(event: MessageCreated):
    """Отвечает тем же текстом"""
    # Получаем текст сообщения
    user_text = event.message.body.text
    # Отправляем ответ
    await event.message.answer(f"Эхо: {user_text}")

async def main():
    # Запускаем бота в режиме long polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
