# bot.py
import asyncio
import logging
import os
import json
import requests
from datetime import datetime
from maxapi import Bot, Dispatcher, F
from maxapi.types import MessageCreated, MessageCallback, CallbackButton, ButtonsPayload, Attachment, BotStarted
from maxapi.enums.intent import Intent
from maxapi.context import MemoryContext, StatesGroup, State

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN не задан!")

bot = Bot(TOKEN)
dp = Dispatcher()

# ==================== КОНСТАНТЫ ====================

PAIR_TIMES = {
    '1': '8:45-10:05', '2': '10:15-11:35', '3': '12:10-13:30', '4': '13:40-15:00',
    '5': '15:35-16:55', '6': '17:05-18:25', '7': '18:50-20:10', '8': '20:20-21:40'
}

INTERVAL_MODES = {
    '1': {'name': '📅 Сегодня/завтра', 'mode': 1},
    '2': {'name': '📅 Неделя', 'mode': 2},
    '3': {'name': '📅 Месяц', 'mode': 3},
    '4': {'name': '📅 Семестр', 'mode': 4},
    '5': {'name': '📅 Произвольные даты', 'mode': 5}
}

# ==================== СОСТОЯНИЯ ====================

class ScheduleStates(StatesGroup):
    searching = State()
    selecting_teacher = State()
    selecting_period = State()
    awaiting_start_date = State()
    awaiting_end_date = State()
    showing_schedule = State()

# ==================== API КЛИЕНТ РГГУ ====================

class RGGUAPIClient:
    def __init__(self):
        self.base_url = 'https://raspis.rggu.ru'
        self.timeout = 10

    def get_teachers_list(self):
        try:
            response = requests.get(f'{self.base_url}/api/Get_Teachers_List', timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                return data if isinstance(data, list) else []
            return []
        except Exception as e:
            logger.error(f"Ошибка получения списка преподавателей: {e}")
            return []

    def search_teachers(self, query):
        if not query or len(query.strip()) < 2:
            return []
        
        teachers = self.get_teachers_list()
        if not teachers:
            return []
        
        results = []
        query_lower = query.lower().strip()
        
        for teacher in teachers:
            if not teacher or not isinstance(teacher, dict):
                continue
            teacher_name = teacher.get('data', '')
            if teacher_name:
                name_parts = teacher_name.split()
                if name_parts and name_parts[0].lower().startswith(query_lower):
                    results.append({
                        'id': teacher.get('id'),
                        'name': teacher_name
                    })
        
        return results[:20]

    def get_teacher_schedule(self, teacher_id, interval_mode=2, start_date=None, end_date=None):
        try:
            payload = {
                'teacher': int(teacher_id),
                'intervalMode': int(interval_mode),
                'menuMode': 'teacher'
            }
            
            if interval_mode == 5 and start_date and end_date:
                payload['startDate'] = start_date
                payload['endDate'] = end_date
            
            logger.info(f"API ЗАПРОС: teacher_id={teacher_id}, mode={interval_mode}")
            
            response = requests.post(
                f'{self.base_url}/api/Get_Schedule_Table',
                data=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"Ошибка получения расписания: {e}")
            return None

api_client = RGGUAPIClient()

# ==================== СОЗДАНИЕ КЛАВИАТУР ====================

def create_main_menu() -> Attachment:
    buttons = [
        [
            CallbackButton(
                text="🔍 Найти преподавателя",
                payload="cmd_search",
                intent=Intent.POSITIVE
            )
        ],
        [
            CallbackButton(
                text="📋 Помощь",
                payload="cmd_help",
                intent=Intent.DEFAULT
            )
        ]
    ]
    return Attachment(type="inline_keyboard", payload=ButtonsPayload(buttons=buttons))

def create_teacher_list_buttons(teachers: list) -> Attachment:
    buttons = []
    for i, teacher in enumerate(teachers):
        name = teacher['name']
        if len(name) > 30:
            name = name[:27] + '...'
        btn = CallbackButton(
            text=f"{i+1}. {name}",
            payload=f"teacher_{i}",
            intent=Intent.DEFAULT
        )
        buttons.append([btn])
    
    buttons.append([
        CallbackButton(
            text="❌ Отмена",
            payload="cmd_cancel",
            intent=Intent.NEGATIVE
        )
    ])
    
    return Attachment(type="inline_keyboard", payload=ButtonsPayload(buttons=buttons))

def create_period_buttons() -> Attachment:
    buttons = []
    for key, value in INTERVAL_MODES.items():
        btn = CallbackButton(
            text=value['name'],
            payload=f"period_{key}",
            intent=Intent.DEFAULT
        )
        buttons.append([btn])
    
    buttons.append([
        CallbackButton(
            text="❌ Отмена",
            payload="cmd_cancel",
            intent=Intent.NEGATIVE
        )
    ])
    
    return Attachment(type="inline_keyboard", payload=ButtonsPayload(buttons=buttons))

def create_continue_menu() -> Attachment:
    buttons = [
        [
            CallbackButton(
                text="📅 Другой период",
                payload="cmd_periods",
                intent=Intent.DEFAULT
            )
        ],
        [
            CallbackButton(
                text="🔍 Новый поиск",
                payload="cmd_search",
                intent=Intent.POSITIVE
            ),
            CallbackButton(
                text="🏠 Главное меню",
                payload="cmd_main",
                intent=Intent.DEFAULT
            )
        ]
    ]
    return Attachment(type="inline_keyboard", payload=ButtonsPayload(buttons=buttons))

# ==================== ФОРМАТИРОВАНИЕ РАСПИСАНИЯ ====================

def format_schedule(schedule, teacher_name) -> list:
    """
    Форматирование расписания для отправки.
    Возвращает список частей, каждая не больше 3950 символов.
    """
    if not schedule or 'tblData' not in schedule:
        return ["❌ Не удалось загрузить расписание"]
    
    if not schedule['tblData']:
        return ["📭 Занятий нет в выбранный период"]
    
    result = f"📅 {schedule.get('itemName', 'Расписание')}\n"
    result += f"👤 {teacher_name}\n"
    result += f"📆 {schedule.get('interval', '')}\n\n"
    
    days_displayed = 0
    for day in schedule['tblData']:
        if days_displayed >= 15:
            break
            
        day_text = f"📅 {day.get('date', '')}\n"
        
        if 'pairs' in day and day['pairs']:
            for pair in day['pairs']:
                if 'flows' in pair and pair['flows']:
                    for flow in pair['flows']:
                        pair_num = pair.get('pair', '')
                        pair_time = PAIR_TIMES.get(str(pair_num), '')
                        
                        day_text += f"🕒 Пара {pair_num} ({pair_time})\n"
                        day_text += f"📚 {flow.get('subject', '')}\n"
                        day_text += f"🎯 {flow.get('lessontype', '')}\n"
                        
                        flow_name = flow.get('flow', '')
                        course = flow.get('course', '')
                        
                        if flow_name and flow_name != '-':
                            if course and course != '-':
                                day_text += f"👥 Поток: {flow_name} (курс {course})\n"
                            else:
                                day_text += f"👥 Поток: {flow_name}\n"
                        
                        room = flow.get('room', '')
                        if room:
                            day_text += f"🏫 Аудитория: {room}\n"
                        
                        day_text += "\n"
        else:
            day_text += "📭 Нет занятий\n"
            
        day_text += "─" * 10 + "\n\n"
        
        # Проверяем, не превысит ли добавление дня лимит
        if len(result) + len(day_text) > 3850:  # Оставляем запас
            # Сохраняем текущий результат как часть
            # Добавляем завершающее сообщение о том, что будет продолжение
            result += "... продолжение в следующем сообщении\n\n"
            days_displayed += 1
            break
        
        result += day_text
        days_displayed += 1
    
    if days_displayed < len(schedule['tblData']):
        remaining = len(schedule['tblData']) - days_displayed
        if remaining > 0:
            result += f"... и еще {remaining} дней\n\n"
    
    # Разбиваем результат на части по 4000 символов
    parts = []
    if len(result) > 3950:
        for i in range(0, len(result), 3950):
            parts.append(result[i:i+3950])
    else:
        parts.append(result)
    
    return parts

def is_valid_date(date_string):
    try:
        datetime.strptime(date_string, '%d.%m.%Y')
        return True
    except ValueError:
        return False

def is_valid_date_range(start_date, end_date):
    try:
        start = datetime.strptime(start_date, '%d.%m.%Y')
        end = datetime.strptime(end_date, '%d.%m.%Y')
        return end >= start
    except ValueError:
        return False

# ==================== ОБРАБОТЧИКИ ====================

@dp.bot_started()
async def on_bot_started(event: BotStarted, context: MemoryContext):
    chat_id = event.chat.chat_id
    try:
        await bot.send_message(
            chat_id=chat_id,
            text="🎓 Бот расписания РГГУ\n\n"
                 "Я помогу найти расписание преподавателей.\n\n"
                 "🔍 Нажми кнопку «Найти преподавателя» чтобы начать поиск.",
            attachments=[create_main_menu()]
        )
    except Exception as e:
        logger.error(f"Ошибка в on_bot_started: {e}")

@dp.message_created(F.message.body.text == '/start')
async def cmd_start(event: MessageCreated):
    chat_id = event.message.recipient.chat_id
    try:
        await bot.send_message(
            chat_id=chat_id,
            text="🎓 Бот расписания РГГУ\n\n"
                 "Я помогу найти расписание преподавателей.\n\n"
                 "🔍 Нажми кнопку «Найти преподавателя» чтобы начать поиск.",
            attachments=[create_main_menu()]
        )
    except Exception as e:
        logger.error(f"Ошибка в cmd_start: {e}")

@dp.message_created(F.message.body.text == '/help')
async def cmd_help(event: MessageCreated):
    chat_id = event.message.recipient.chat_id
    try:
        await bot.send_message(
            chat_id=chat_id,
            text="📋 Помощь\n\n"
                 "/start - Главное меню\n"
                 "/cancel - Отмена текущего действия\n"
                 "/help - Эта справка\n\n"
                 "Как пользоваться:\n"
                 "1. Нажмите «Найти преподавателя»\n"
                 "2. Введите фамилию\n"
                 "3. Выберите преподавателя из списка\n"
                 "4. Выберите период расписания\n"
                 "5. Получите расписание!",
            attachments=[create_main_menu()]
        )
    except Exception as e:
        logger.error(f"Ошибка в cmd_help: {e}")

@dp.message_created(F.message.body.text == '/cancel')
async def cmd_cancel(event: MessageCreated, context: MemoryContext):
    chat_id = event.message.recipient.chat_id
    try:
        await context.clear()
        await bot.send_message(
            chat_id=chat_id,
            text="✅ Действие отменено. Вы вернулись в главное меню.",
            attachments=[create_main_menu()]
        )
    except Exception as e:
        logger.error(f"Ошибка в cmd_cancel: {e}")

# ==================== ОБРАБОТЧИКИ КНОПОК ====================

@dp.message_callback(F.callback.payload == "cmd_search")
async def callback_search(event: MessageCallback, context: MemoryContext):
    chat_id = event.message.recipient.chat_id
    
    await event.answer(notification="🔍 Начинаем поиск...")
    
    try:
        await context.clear()
        await context.set_state(ScheduleStates.searching)
        
        await bot.send_message(
            chat_id=chat_id,
            text="🔍 Введите фамилию преподавателя\n\n"
                 "Например: Иванов, Петрова, Смирнов\n\n"
                 "❌ Для отмены введите /cancel"
        )
    except Exception as e:
        logger.error(f"Ошибка в callback_search: {e}")

@dp.message_callback(F.callback.payload == "cmd_help")
async def callback_help(event: MessageCallback):
    await event.answer(notification="📋 Справка")
    
    chat_id = event.message.recipient.chat_id
    try:
        await bot.send_message(
            chat_id=chat_id,
            text="📋 Помощь\n\n"
                 "/start - Главное меню\n"
                 "/cancel - Отмена текущего действия\n"
                 "/help - Эта справка\n\n"
                 "Как пользоваться:\n"
                 "1. Нажмите «Найти преподавателя»\n"
                 "2. Введите фамилию\n"
                 "3. Выберите преподавателя из списка\n"
                 "4. Выберите период расписания\n"
                 "5. Получите расписание!",
            attachments=[create_main_menu()]
        )
    except Exception as e:
        logger.error(f"Ошибка в callback_help: {e}")

@dp.message_callback(F.callback.payload == "cmd_main")
async def callback_main(event: MessageCallback, context: MemoryContext):
    await event.answer()
    
    chat_id = event.message.recipient.chat_id
    try:
        await context.clear()
        await bot.send_message(
            chat_id=chat_id,
            text="🏠 Главное меню\n\nВыберите действие:",
            attachments=[create_main_menu()]
        )
    except Exception as e:
        logger.error(f"Ошибка в callback_main: {e}")

@dp.message_callback(F.callback.payload == "cmd_cancel")
async def callback_cancel(event: MessageCallback, context: MemoryContext):
    await event.answer(notification="✅ Отменено")
    
    chat_id = event.message.recipient.chat_id
    try:
        await context.clear()
        await bot.send_message(
            chat_id=chat_id,
            text="✅ Действие отменено. Вы вернулись в главное меню.",
            attachments=[create_main_menu()]
        )
    except Exception as e:
        logger.error(f"Ошибка в callback_cancel: {e}")

@dp.message_callback(F.callback.payload == "cmd_periods")
async def callback_periods(event: MessageCallback, context: MemoryContext):
    await event.answer()
    
    chat_id = event.message.recipient.chat_id
    try:
        data = await context.get_data()
        teacher = data.get('selected_teacher')
        
        if teacher:
            await context.set_state(ScheduleStates.selecting_period)
            await bot.send_message(
                chat_id=chat_id,
                text=f"✅ Выбран: {teacher['name']}\n\n"
                     f"Выберите период:",
                attachments=[create_period_buttons()]
            )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text="❌ Ошибка: преподаватель не найден. Начните заново.",
                attachments=[create_main_menu()]
            )
    except Exception as e:
        logger.error(f"Ошибка в callback_periods: {e}")

@dp.message_callback(F.callback.payload.startswith("teacher_"))
async def callback_select_teacher(event: MessageCallback, context: MemoryContext):
    chat_id = event.message.recipient.chat_id
    
    try:
        index = int(event.callback.payload.split('_')[1])
        data = await context.get_data()
        teachers = data.get('teachers_list', [])
        
        if 0 <= index < len(teachers):
            teacher = teachers[index]
            await context.update_data(selected_teacher=teacher)
            await context.set_state(ScheduleStates.selecting_period)
            
            await event.answer(notification=f"✅ Выбран: {teacher['name']}")
            
            await bot.send_message(
                chat_id=chat_id,
                text=f"✅ Выбран преподаватель: {teacher['name']}\n\n"
                     f"Выберите период:",
                attachments=[create_period_buttons()]
            )
        else:
            await event.answer(notification="❌ Ошибка выбора")
    except Exception as e:
        logger.error(f"Ошибка выбора преподавателя: {e}")
        await event.answer(notification="❌ Ошибка")

@dp.message_callback(F.callback.payload.startswith("period_"))
async def callback_select_period(event: MessageCallback, context: MemoryContext):
    chat_id = event.message.recipient.chat_id
    period_key = event.callback.payload.split('_')[1]
    
    await event.answer(notification="📅 Загружаю...")
    
    try:
        data = await context.get_data()
        teacher = data.get('selected_teacher')
        
        if not teacher:
            await bot.send_message(
                chat_id=chat_id,
                text="❌ Ошибка: преподаватель не выбран. Начните заново.",
                attachments=[create_main_menu()]
            )
            return
        
        if period_key not in INTERVAL_MODES:
            await bot.send_message(
                chat_id=chat_id,
                text="❌ Неверный период. Выберите из предложенных.",
                attachments=[create_period_buttons()]
            )
            return
        
        period_info = INTERVAL_MODES[period_key]
        
        if period_key == '5':
            await context.set_state(ScheduleStates.awaiting_start_date)
            await bot.send_message(
                chat_id=chat_id,
                text="📅 Введите начальную дату в формате ДД.ММ.ГГГГ\n"
                     "Пример: 15.12.2025\n\n"
                     "❌ Для отмены введите /cancel"
            )
            return
        
        schedule = api_client.get_teacher_schedule(teacher['id'], period_info['mode'])
        
        if schedule:
            parts = format_schedule(schedule, teacher['name'])
            for part in parts:
                await bot.send_message(chat_id=chat_id, text=part)
            
            await context.set_state(ScheduleStates.showing_schedule)
            await bot.send_message(
                chat_id=chat_id,
                text="✅ Расписание показано!\n\n"
                     "Что дальше?",
                attachments=[create_continue_menu()]
            )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text="❌ Не удалось загрузить расписание. Попробуйте позже.",
                attachments=[create_main_menu()]
            )
    except Exception as e:
        logger.error(f"Ошибка в callback_select_period: {e}")
        await bot.send_message(
            chat_id=chat_id,
            text="❌ Произошла ошибка. Попробуйте позже.",
            attachments=[create_main_menu()]
        )

# ==================== ОБРАБОТЧИК ТЕКСТОВЫХ СООБЩЕНИЙ ====================

@dp.message_created()
async def handle_message(event: MessageCreated, context: MemoryContext):
    chat_id = event.message.recipient.chat_id
    text = event.message.body.text
    
    if not text or text.startswith('/'):
        return
    
    try:
        current_state = await context.get_state()
        
        if current_state == ScheduleStates.searching:
            await handle_teacher_search(chat_id, text, context)
            return
        
        if current_state == ScheduleStates.awaiting_start_date:
            await handle_start_date(chat_id, text, context)
            return
        
        if current_state == ScheduleStates.awaiting_end_date:
            await handle_end_date(chat_id, text, context)
            return
        
        await bot.send_message(
            chat_id=chat_id,
            text="❓ Используйте кнопки для навигации или введите /start для начала.",
            attachments=[create_main_menu()]
        )
    except Exception as e:
        logger.error(f"Ошибка в handle_message: {e}")

async def handle_teacher_search(chat_id: int, query: str, context: MemoryContext):
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=f"🔍 Ищу: {query}..."
        )
        
        teachers = api_client.search_teachers(query)
        
        if not teachers:
            await bot.send_message(
                chat_id=chat_id,
                text="❌ Преподаватели не найдены.\n\n"
                     "🔍 Попробуйте ввести другую фамилию\n"
                     "❌ Для отмены введите /cancel"
            )
            return
        
        await context.update_data(teachers_list=teachers)
        await context.set_state(ScheduleStates.selecting_teacher)
        
        await bot.send_message(
            chat_id=chat_id,
            text=f"📋 Найдено преподавателей: {len(teachers)}\n\n"
                 f"Выберите преподавателя:",
            attachments=[create_teacher_list_buttons(teachers)]
        )
    except Exception as e:
        logger.error(f"Ошибка в handle_teacher_search: {e}")

async def handle_start_date(chat_id: int, text: str, context: MemoryContext):
    try:
        if is_valid_date(text):
            await context.update_data(start_date=text)
            await context.set_state(ScheduleStates.awaiting_end_date)
            await bot.send_message(
                chat_id=chat_id,
                text="📅 Введите конечную дату в формате ДД.ММ.ГГГГ\n"
                     "Пример: 20.12.2025\n\n"
                     "❌ Для отмены введите /cancel"
            )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text="❌ Неверный формат даты!\n\n"
                     "Используйте формат: ДД.ММ.ГГГГ\n"
                     "Пример: 15.12.2025"
            )
    except Exception as e:
        logger.error(f"Ошибка в handle_start_date: {e}")

async def handle_end_date(chat_id: int, text: str, context: MemoryContext):
    try:
        if is_valid_date(text):
            data = await context.get_data()
            start_date = data.get('start_date')
            
            if is_valid_date_range(start_date, text):
                teacher = data.get('selected_teacher')
                
                if teacher:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=f"📅 Загружаю расписание с {start_date} по {text}..."
                    )
                    
                    schedule = api_client.get_teacher_schedule(
                        teacher['id'], 5, start_date, text
                    )
                    
                    if schedule:
                        parts = format_schedule(schedule, teacher['name'])
                        for part in parts:
                            await bot.send_message(chat_id=chat_id, text=part)
                        
                        await context.set_state(ScheduleStates.showing_schedule)
                        await bot.send_message(
                            chat_id=chat_id,
                            text="✅ Расписание показано!\n\n"
                                 "Что дальше?",
                            attachments=[create_continue_menu()]
                        )
                    else:
                        await bot.send_message(
                            chat_id=chat_id,
                            text="❌ Не удалось загрузить расписание. Попробуйте позже.",
                            attachments=[create_main_menu()]
                        )
                else:
                    await bot.send_message(
                        chat_id=chat_id,
                        text="❌ Ошибка: преподаватель не выбран. Начните заново.",
                        attachments=[create_main_menu()]
                    )
            else:
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ Конечная дата не может быть раньше начальной!\n\n"
                         f"Начальная: {start_date}\n"
                         f"Введите конечную дату позже:"
                )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text="❌ Неверный формат даты!\n\n"
                     "Используйте формат: ДД.ММ.ГГГГ\n"
                     "Пример: 20.12.2025"
            )
    except Exception as e:
        logger.error(f"Ошибка в handle_end_date: {e}")

# ==================== ЗАПУСК ====================

async def main():
    logger.info("🎓 Бот расписания РГГУ для MAX запущен!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
