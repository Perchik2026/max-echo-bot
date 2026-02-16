import os
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
    raise ValueError("Переменная BOT_TOKEN не задана!")

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
    
    for i, option in enumerate(options):
        # Создаём кнопку с payload, содержащим номер загадки и ответ
        btn = CallbackButton(
            text=option,
            payload=f"riddle_{riddle_num}_{option}",
            intent=Intent.DEFAULT
        )
        row.append(btn)
    
    buttons.append(row)  # Все кнопки в одном ряду
    
    # Создаём payload и attachment
    buttons_payload = ButtonsPayload(buttons=buttons)
    return Attachment(type="inline_keyboard", payload=buttons_payload)


async def show_riddle(chat_id: int, context: MemoryContext, riddle_num: int):
    """Показывает загадку с кнопками"""
    riddle = RIDDLES[riddle_num]
    
    # Создаём кнопки для загадки
    keyboard = create_riddle_buttons(riddle_num, riddle['options'])
    
    # Сохраняем номер текущей загадки в контекст
    await context.update_data(current_riddle=riddle_num)
    
    # Устанавливаем состояние для текущей загадки
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
async def start_riddles(event: MessageCreated, context: MemoryContext):
    """Начинаем игру с первой загадкой по команде /riddles"""
    if event.message.body.text == '/riddles':
        chat_id = event.message.recipient.chat_id
        await show_riddle(chat_id, context, 1)


@dp.message_callback(F.callback.payload.startswith("riddle_1_"))
async def riddle1_handler(event: MessageCallback, context: MemoryContext):
    """Обработка ответа на первую загадку"""
    
    # Получаем payload и извлекаем ответ
    payload = event.callback.payload
    user_answer = payload.replace("riddle_1_", "")
    
    riddle = RIDDLES[1]
    chat_id = event.message.recipient.chat_id
    
    # Проверяем правильность ответа
    if user_answer == riddle['correct']:
        # Отправляем уведомление
        await event.answer(notification="✅ Правильно!")
        
        # Отправляем сообщение
        await bot.send_message(
            chat_id=chat_id,
            text="✅ Правильно! Переходим к следующей загадке..."
        )
        
        # Переходим ко второй загадке
        await show_riddle(chat_id, context, 2)
    else:
        # Отправляем уведомление об ошибке
        await event.answer(notification="❌ Неправильно! Попробуй еще раз.")


@dp.message_callback(F.callback.payload.startswith("riddle_2_"))
async def riddle2_handler(event: MessageCallback, context: MemoryContext):
    """Обработка ответа на вторую загадку"""
    
    # Получаем payload и извлекаем ответ
    payload = event.callback.payload
    user_answer = payload.replace("riddle_2_", "")
    
    riddle = RIDDLES[2]
    chat_id = event.message.recipient.chat_id
    
    if user_answer == riddle['correct']:
        # Отправляем уведомление
        await event.answer(notification="🎉 Поздравляю!")
        
        # Отправляем сообщение
        await bot.send_message(
            chat_id=chat_id,
            text="🎉 Поздравляю! Ты отгадал все загадки!"
        )
        
        # Очищаем состояние
        await context.clear()
    else:
        # Отправляем уведомление об ошибке
        await event.answer(notification="❌ Неправильно! Попробуй еще раз.")


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
