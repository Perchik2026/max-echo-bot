import asyncio
import logging
from maxapi import Bot, Dispatcher, F
from maxapi.types import MessageCreated, MessageCallback, CallbackButton, ButtonsPayload, Attachment
from maxapi.enums.intent import Intent
from maxapi.context import MemoryContext, StatesGroup, State

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Токен берется из переменных окружения на Bothost
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN не задан! Укажите токен в настройках бота на Bothost")

bot = Bot(TOKEN)
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


def create_riddle_buttons(riddle_num: int, options: list) -> Attachment:
    """Создаёт кнопки для загадки"""
    
    buttons = []
    row = []
    
    for option in options:
        btn = CallbackButton(
            text=option,
            payload=f"riddle_{riddle_num}_{option}",
            intent=Intent.DEFAULT
        )
        row.append(btn)
    
    buttons.append(row)
    buttons_payload = ButtonsPayload(buttons=buttons)
    return Attachment(type="inline_keyboard", payload=buttons_payload)


async def show_riddle(chat_id: int, context: MemoryContext, riddle_num: int):
    """Показывает загадку с кнопками"""
    riddle = RIDDLES[riddle_num]
    keyboard = create_riddle_buttons(riddle_num, riddle['options'])
    
    await context.update_data(current_riddle=riddle_num)
    
    if riddle_num == 1:
        await context.set_state(RiddleGame.riddle1)
    else:
        await context.set_state(RiddleGame.riddle2)
    
    await bot.send_message(
        chat_id=chat_id,
        text=f'❓ Загадка {riddle_num}:\n{riddle["question"]}',
        attachments=[keyboard]
    )


@dp.message_created()
async def cmd_start(event: MessageCreated):
    """Обработчик команды /start"""
    if event.message.body.text == '/start':
        chat_id = event.message.recipient.chat_id
        await bot.send_message(
            chat_id=chat_id,
            text="👋 Привет! Я бот с загадками.\n\n"
                 "Доступные команды:\n"
                 "/riddles - начать игру в загадки\n"
                 "/help - получить помощь"
        )


@dp.message_created()
async def cmd_help(event: MessageCreated):
    """Обработчик команды /help"""
    if event.message.body.text == '/help':
        chat_id = event.message.recipient.chat_id
        await bot.send_message(
            chat_id=chat_id,
            text="📋 **Помощь**\n\n"
                 "Правила игры:\n"
                 "1. Введи /riddles чтобы начать\n"
                 "2. Выбери ответ из кнопок\n"
                 "3. Угадай все загадки до конца\n\n"
                 "Удачи! 🍀"
        )


@dp.message_created()
async def start_riddles(event: MessageCreated, context: MemoryContext):
    """Начинаем игру с первой загадкой"""
    if event.message.body.text == '/riddles':
        chat_id = event.message.recipient.chat_id
        
        current_state = await context.get_state()
        if current_state:
            await bot.send_message(
                chat_id=chat_id,
                text="⚠️ Вы уже в игре! Введите /cancel чтобы выйти"
            )
            return
            
        await show_riddle(chat_id, context, 1)


@dp.message_created()
async def cmd_cancel(event: MessageCreated, context: MemoryContext):
    """Отмена текущей игры"""
    if event.message.body.text == '/cancel':
        chat_id = event.message.recipient.chat_id
        current_state = await context.get_state()
        
        if current_state:
            await context.clear()
            await bot.send_message(
                chat_id=chat_id,
                text="✅ Игра отменена. Введите /riddles чтобы начать заново."
            )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text="❌ Нет активной игры."
            )


@dp.message_callback(F.callback.payload.startswith("riddle_1_"))
async def riddle1_handler(event: MessageCallback, context: MemoryContext):
    """Обработка ответа на первую загадку"""
    payload = event.callback.payload
    user_answer = payload.replace("riddle_1_", "")
    
    if user_answer == RIDDLES[1]['correct']:
        await event.answer(notification="✅ Правильно!")
        chat_id = event.message.recipient.chat_id
        await bot.send_message(
            chat_id=chat_id,
            text="✅ Правильно! Следующая загадка:"
        )
        await show_riddle(chat_id, context, 2)
    else:
        await event.answer(notification="❌ Неправильно! Попробуй еще раз.")


@dp.message_callback(F.callback.payload.startswith("riddle_2_"))
async def riddle2_handler(event: MessageCallback, context: MemoryContext):
    """Обработка ответа на вторую загадку"""
    payload = event.callback.payload
    user_answer = payload.replace("riddle_2_", "")
    
    if user_answer == RIDDLES[2]['correct']:
        await event.answer(notification="🎉 Поздравляю!")
        chat_id = event.message.recipient.chat_id
        await bot.send_message(
            chat_id=chat_id,
            text="🎉 Поздравляю! Ты отгадал все загадки!"
        )
        await context.clear()
    else:
        await event.answer(notification="❌ Неправильно! Попробуй еще раз.")


@dp.message_created()
async def handle_unknown(event: MessageCreated):
    """Обработчик неизвестных команд"""
    if event.message.body.text.startswith('/'):
        chat_id = event.message.recipient.chat_id
        await bot.send_message(
            chat_id=chat_id,
            text="❌ Неизвестная команда. Введите /help"
        )


async def main():
    logger.info("Бот с загадками запущен на Bothost!")
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
