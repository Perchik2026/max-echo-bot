import asyncio
import logging
from maxapi import Bot, Dispatcher, F
from maxapi.types import MessageCreated, MessageCallback, CallbackButton, ButtonsPayload, Attachment
from maxapi.enums.intent import Intent
from maxapi.context import MemoryContext, StatesGroup, State

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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


def create_main_menu() -> Attachment:
    """Создаёт главное меню с кнопкой Начать"""
    
    buttons = []
    
    # Создаём кнопку "Начать игру"
    start_btn = CallbackButton(
        text="🎮 Начать игру",
        payload="cmd_start_game",
        intent=Intent.POSITIVE
    )
    buttons.append([start_btn])  # Один ряд с одной кнопкой
    
    # Создаём кнопку "Помощь"
    help_btn = CallbackButton(
        text="📋 Помощь",
        payload="cmd_help",
        intent=Intent.DEFAULT
    )
    buttons.append([help_btn])  # Второй ряд с кнопкой помощи
    
    buttons_payload = ButtonsPayload(buttons=buttons)
    return Attachment(type="inline_keyboard", payload=buttons_payload)


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
    """Обработчик команды /start - показывает меню с кнопками"""
    if event.message.body.text == '/start':
        chat_id = event.message.recipient.chat_id
        main_menu = create_main_menu()
        
        await bot.send_message(
            chat_id=chat_id,
            text="👋 **Добро пожаловать в игру Загадки!**\n\n"
                 "Нажми кнопку **«Начать игру»** чтобы приступить\n"
                 "или **«Помощь»** для справки.",
            attachments=[main_menu]
        )


@dp.message_callback(F.callback.payload == "cmd_start_game")
async def callback_start_game(event: MessageCallback, context: MemoryContext):
    """Обработка нажатия кнопки 'Начать игру'"""
    
    await event.answer(notification="🎮 Запускаю игру...")
    chat_id = event.message.recipient.chat_id
    
    # Проверяем, не в игре ли уже пользователь
    current_state = await context.get_state()
    if current_state:
        await bot.send_message(
            chat_id=chat_id,
            text="⚠️ Вы уже в игре! Введите /cancel чтобы выйти"
        )
        return
    
    # Можно отредактировать сообщение с кнопками или отправить новое
    await event.message.edit(
        text="🎮 **Игра начинается!**\n\nПервая загадка:"
    )
    
    await show_riddle(chat_id, context, 1)


@dp.message_callback(F.callback.payload == "cmd_help")
async def callback_help(event: MessageCallback):
    """Обработка нажатия кнопки 'Помощь'"""
    
    await event.answer(notification="📋 Открываю справку...")
    chat_id = event.message.recipient.chat_id
    
    help_text = (
        "📋 **Помощь по игре**\n\n"
        "**Правила:**\n"
        "• Нажми «Начать игру» для старта\n"
        "• Выбирай ответ из предложенных кнопок\n"
        "• Если ответ правильный - переходишь к следующей загадке\n"
        "• Введи /cancel чтобы выйти из игры\n\n"
        "**Команды:**\n"
        "/start - показать меню\n"
        "/riddles - начать игру (если нет кнопок)\n"
        "/help - эта справка\n"
        "/cancel - выйти из игры\n\n"
        "Удачи! 🍀"
    )
    
    # Можно отредактировать текущее сообщение
    await event.message.edit(
        text=help_text,
        attachments=[create_main_menu()]  # Показываем меню снова
    )


@dp.message_created()
async def cmd_help_text(event: MessageCreated):
    """Обработчик команды /help"""
    if event.message.body.text == '/help':
        chat_id = event.message.recipient.chat_id
        main_menu = create_main_menu()
        
        help_text = (
            "📋 **Помощь по игре**\n\n"
            "**Правила:**\n"
            "• Нажми «Начать игру» для старта\n"
            "• Выбирай ответ из предложенных кнопок\n"
            "• Если ответ правильный - переходишь к следующей загадке\n"
            "• Введи /cancel чтобы выйти из игры\n\n"
            "**Команды:**\n"
            "/start - показать меню\n"
            "/riddles - начать игру (если нет кнопок)\n"
            "/help - эта справка\n"
            "/cancel - выйти из игры\n\n"
            "Удачи! 🍀"
        )
        
        await bot.send_message(
            chat_id=chat_id,
            text=help_text,
            attachments=[main_menu]
        )


@dp.message_created()
async def start_riddles(event: MessageCreated, context: MemoryContext):
    """Начинаем игру с первой загадкой по команде /riddles"""
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
            main_menu = create_main_menu()
            await bot.send_message(
                chat_id=chat_id,
                text="✅ Игра отменена. Хочешь сыграть снова?",
                attachments=[main_menu]
            )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text="❌ Нет активной игры. Нажми /start чтобы начать."
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
            text="🎉 **Поздравляю!** Ты отгадал все загадки!\n\nХочешь сыграть еще раз?",
            attachments=[create_main_menu()]
        )
        await context.clear()
    else:
        await event.answer(notification="❌ Неправильно! Попробуй еще раз.")


@dp.message_created()
async def handle_unknown(event: MessageCreated):
    """Обработчик неизвестных команд"""
    if event.message.body.text.startswith('/'):
        chat_id = event.message.recipient.chat_id
        main_menu = create_main_menu()
        
        await bot.send_message(
            chat_id=chat_id,
            text="❌ Неизвестная команда.\n\nВот что я умею:",
            attachments=[main_menu]
        )


async def main():
    logger.info("Бот с загадками запущен на MAX!")
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
