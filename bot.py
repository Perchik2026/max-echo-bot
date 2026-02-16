import os
import asyncio
import logging
from maxapi import Bot, Dispatcher
from maxapi.types import MessageCreated
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder
from maxapi.context import MemoryContext, StatesGroup, State

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise ValueError("Переменная BOT_TOKEN не задана!")

bot = Bot(TOKEN)
dp = Dispatcher()

class RiddleGame(StatesGroup):
    riddle1 = State()
    riddle2 = State()

RIDDLES = {
    1: {
        'question': 'Сам дубовый, а пояс ивовый',
        'options': ['Бочка', 'Лавка'],
        'correct': 'Бочка'
    },
    2: {
        'question': 'Почему лиса оглядывается когда за ней бежит собака?',
        'options': ['Нет глаз на хвосте', 'Чтобы посмотреть'],
        'correct': 'Нет глаз на хвосте'
    }
}

@dp.message_created(lambda event: event.text and event.text.strip() == '/riddles')
async def start_riddles(event: MessageCreated, context: MemoryContext):
    logger.info(f"Старт игры для {event.user_id}")
    await show_riddle(event.user_id, context, 1)

async def show_riddle(user_id: int, context: MemoryContext, riddle_num: int):
    riddle = RIDDLES[riddle_num]
    reply_kb = InlineKeyboardBuilder()
    for option in riddle['options']:
        reply_kb.row(MessageButton(text=option, callback_data=option))
    
    await context.update_data(current_riddle=riddle_num)
    if riddle_num == 1:
        await context.set_state(RiddleGame.riddle1)
    else:
        await context.set_state(RiddleGame.riddle2)

    await bot.send_message(
        user_id=user_id,
        text=f'❓ Загадка {riddle_num}:\n{riddle["question"]}',
        keyboard=reply_kb.as_markup()
    )

# Обработчик нажатий кнопок (через message_created + проверка callback_data)
@dp.message_created(
    lambda e: e.callback_data is not None
)
async def button_handler(event: MessageCreated, context: MemoryContext):
    state = await context.get_state()

    if state == RiddleGame.riddle1:
        riddle = RIDDLES[1]
        user_answer = event.callback_data
        if user_answer == riddle['correct']:
            await bot.send_message(
                user_id=event.user_id,
                text='✅ Правильно! Переходим к следующей загадке...'
            )
            await show_riddle(event.user_id, context, 2)
        else:
            await bot.send_message(
                user_id=event.user_id,
                text='❌ Неправильно! Попробуй ещё раз.'
            )

    elif state == RiddleGame.riddle2:
        riddle = RIDDLES[2]
        user_answer = event.callback_data
        if user_answer == riddle['correct']:
            await bot.send_message(
                user_id=event.user_id,
                text='🎉 Поздравляю! Ты отгадал все загадки!'
            )
            await context.clear()
        else:
            await bot.send_message(
                user_id=event.user_id,
                text='❌ Попробуй ещё раз!'
            )

async def main():
    logger.info("Запуск бота...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
