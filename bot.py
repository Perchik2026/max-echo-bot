import asyncio
from maxapi import Bot, Dispatcher, F
from config import bot_token
from maxapi.types import Command, MessageCreated, CallbackQuery
from maxapi.types import MessageButton
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder
from maxapi.context import MemoryContext, StatesGroup, State


bot = Bot(token=bot_token)
dp = Dispatcher()


class RiddleGame(StatesGroup):
    riddle1 = State()
    riddle2 = State()


# Словарь с загадками
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


@dp.message_created(Command('riddles'))
async def start_riddles(event: MessageCreated, context: MemoryContext):
    """Начинаем игру с первой загадкой"""
    await show_riddle(event.from_user.user_id, context, 1)


async def show_riddle(user_id: int, context: MemoryContext, riddle_num: int):
    """Показывает загадку с кнопками"""
    riddle = RIDDLES[riddle_num]
    
    # Создаем клавиатуру с вариантами ответов
    reply_kb = InlineKeyboardBuilder()
    for option in riddle['options']:
        # Используем callback_data для передачи ответа
        reply_kb.row(MessageButton(text=option, callback_data=option))
    
    # Сохраняем номер текущей загадки в контекст
    await context.update_data(current_riddle=riddle_num)
    
    # Устанавливаем состояние для текущей загадки
    if riddle_num == 1:
        await context.set_state(RiddleGame.riddle1)
    else:
        await context.set_state(RiddleGame.riddle2)
    
    await bot.send_message(
        user_id=user_id, 
        text=f'❓ Загадка {riddle_num}:\n{riddle["question"]}', 
        attachments=[reply_kb.as_markup()]
    )


@dp.callback_query(RiddleGame.riddle1)
async def riddle1_handler(event: CallbackQuery, context: MemoryContext):
    """Обработка ответа на первую загадку"""
    riddle = RIDDLES[1]
    user_answer = event.data  # Получаем callback_data с текстом ответа
    
    # Проверяем правильность ответа
    if user_answer == riddle['correct']:
        await bot.answer_callback_query(
            query_id=event.query_id,
            text='✅ Правильно!',
            show_alert=False
        )
        await bot.send_message(
            user_id=event.from_user.user_id, 
            text='✅ Правильно! Переходим к следующей загадке...'
        )
        # Переходим ко второй загадке
        await show_riddle(event.from_user.user_id, context, 2)
    else:
        await bot.answer_callback_query(
            query_id=event.query_id,
            text='❌ Неправильно!',
            show_alert=True  # Показываем как всплывающее уведомление
        )
        # Неправильный ответ - загадка остается той же


@dp.callback_query(RiddleGame.riddle2)
async def riddle2_handler(event: CallbackQuery, context: MemoryContext):
    """Обработка ответа на вторую загадку"""
    riddle = RIDDLES[2]
    user_answer = event.data
    
    if user_answer == riddle['correct']:
        await bot.answer_callback_query(
            query_id=event.query_id,
            text='🎉 Поздравляю!',
            show_alert=False
        )
        await bot.send_message(
            user_id=event.from_user.user_id, 
            text='🎉 Поздравляю! Ты отгадал все загадки!'
        )
        await context.clear()
    else:
        await bot.answer_callback_query(
            query_id=event.query_id,
            text='❌ Попробуй еще раз!',
            show_alert=True
        )
        # Неправильный ответ - остаемся на той же загадке


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
