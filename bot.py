import asyncio
import logging
from maxapi import Bot, Dispatcher
from config import bot_token
from maxapi.types import MessageCreated, CallbackQuery
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder
from maxapi.context import MemoryContext, StatesGroup, State

logging.basicConfig(level=logging.INFO)

bot = Bot(token=bot_token)
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
    logging.info(f"Старт игры для пользователя {event.user_id}")
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

@dp.callback_query(RiddleGame.riddle1)
async def riddle1_handler(event: CallbackQuery, context: MemoryContext):
    riddle = RIDDLES[1]
    user_answer = event.callback_data  # <-- исправлено
    
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

@dp.callback_query(RiddleGame.riddle2)
async def riddle2_handler(event: CallbackQuery, context: MemoryContext):
    riddle = RIDDLES[2]
    user_answer = event.callback_data  # <-- исправлено
    
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
    logging.info("Запуск бота...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
