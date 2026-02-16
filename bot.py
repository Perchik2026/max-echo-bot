import os
import asyncio
import logging
from maxapi import Bot, Dispatcher
from maxapi.types import MessageCreated, CallbackQuery
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder
from maxapi.context import MemoryContext, StatesGroup, State

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Получение токена из переменной окружения
TOKEN = os.environ.get("BOT_TOKEN")

if not TOKEN:
    raise ValueError(
        "Переменная окружения BOT_TOKEN не задана!\n"
        "Установите её через:\n"
        "  export BOT_TOKEN=ваш_токен  # Linux/macOS\n"
        "  set BOT_TOKEN=ваш_токен     # Windows (cmd)\n"
        "  $env:BOT_TOKEN='ваш_токен' # Windows (PowerShell)"
    )

# Инициализация бота и диспетчера
bot = Bot(TOKEN)
dp = Dispatcher()

# Группа состояний для игры в загадки
class RiddleGame(StatesGroup):
    riddle1 = State()
    riddle2 = State()

# База загадок
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

# Команда /riddles — старт игры
@dp.message_created(lambda event: event.text and event.text.strip() == '/riddles')
async def start_riddles(event: MessageCreated, context: MemoryContext):
    logger.info(f"Пользователь {event.user_id} начал игру в загадки")
    await show_riddle(event.user_id, context, 1)

# Функция показа загадки с клавиатурой
async def show_riddle(user_id: int, context: MemoryContext, riddle_num: int):
    riddle = RIDDLES[riddle_num]
    
    # Создаём клавиатуру с вариантами ответов
    reply_kb = InlineKeyboardBuilder()
    for option in riddle['options']:
        reply_kb.row(MessageButton(text=option, callback_data=option))
    
    # Сохраняем номер текущей загадки в контекст
    await context.update_data(current_riddle=riddle_num)
    
    # Устанавливаем состояние
    if riddle_num == 1:
        await context.set_state(RiddleGame.riddle1)
    else:
        await context.set_state(RiddleGame.riddle2)
    
    # Отправляем сообщение с клавиатурой
    await bot.send_message(
        user_id=user_id,
        text=f'❓ Загадка {riddle_num}:\n{riddle["question"]}',
        keyboard=reply_kb.as_markup()
    )

# Обработчик ответа на первую загадку
@dp.callback_query(RiddleGame.riddle1)
async def riddle1_handler(event: CallbackQuery, context: MemoryContext):
    riddle = RIDDLES[1]
    user_answer = event.callback_data  # Получаем ответ из callback_data
    
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

# Обработчик ответа на вторую загадку
@dp.callback_query(RiddleGame.riddle2)
async def riddle2_handler(event: CallbackQuery, context: MemoryContext):
    riddle = RIDDLES[2]
    user_answer = event.callback_data
    
    if user_answer == riddle['correct']:
        await bot.send_message(
            user_id=event.user_id,
            text='🎉 Поздравляю! Ты отгадал все загадки!'
        )
        await context.clear()  # Очищаем контекст после победы
    else:
        await bot.send_message(
            user_id=event.user_id,
            text='❌ Попробуй ещё раз!'
        )

# Основная функция запуска
async def main():
    logger.info("Запуск бота...")
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")

# Точка входа
if __name__ == '__main__':
    asyncio.run(main())
