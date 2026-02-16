import asyncio
from maxapi import Bot, Dispatcher, F
from config import bot_token
from maxapi.types import Command, MessageCreated
from maxapi.types import MessageButton
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder
from maxapi.context import MemoryContext, StatesGroup, State


bot = Bot(token=bot_token)
dp = Dispatcher()


class DialogForm(StatesGroup):
    first_choice = State()
    second_choice = State()


@dp.message_created(Command('test'))
async def test_message(event: MessageCreated, context: MemoryContext):
    reply_kb = InlineKeyboardBuilder()
    reply_kb.row(MessageButton(text='Да'),
                 MessageButton(text='Нет'))

    await context.set_state(DialogForm.first_choice)
    await bot.send_message(user_id=event.from_user.user_id, text='Сделай первый выбор', attachments=[reply_kb.as_markup()])


@dp.message_created(DialogForm.first_choice)
async def first_choice_handler(event: MessageCreated, context: MemoryContext):
    reply_kb = InlineKeyboardBuilder()
    reply_kb.row(MessageButton(text='Да'),
                 MessageButton(text='Нет'))

    await context.update_data(first_choice=event.message.body.text)
    await context.set_state(DialogForm.second_choice)
    await bot.send_message(user_id=event.from_user.user_id, text='Сделай второй выбор', attachments=[reply_kb.as_markup()])


@dp.message_created(DialogForm.second_choice)
async def first_choice_handler(event: MessageCreated, context: MemoryContext):

    await context.update_data(second_choice=event.message.body.text)

    data = await context.get_data()
    await bot.send_message(user_id=event.from_user.user_id, text=f'''
Первый выбор: {data['first_choice']}
Второй выбор: {data['second_choice']}
''')
    await context.clear()
    
    
async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
