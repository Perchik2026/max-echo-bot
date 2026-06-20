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

STATS_FILE = 'user_data.json'

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

# ==================== РАБОТА С ДАННЫМИ ====================

class ScheduleStates(StatesGroup):
    """Состояния бота"""
    searching = State()
    selecting_teacher = State()
    selecting_period = State()
    awaiting_start_date = State()
    awaiting_end_date = State()
    showing_schedule = State()

def load_user_data():
    """Загрузка статистики пользователей"""
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.info(f"ЗАГРУЖЕНО: {len(data)} пользователей")
                return data
        except Exception as e:
            logger.error(f"Ошибка загрузки: {e}")
    return {}

def save_user_data(data):
    """Сохранение статистики пользователей"""
    try:
        temp_file = STATS_FILE + '.tmp'
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(temp_file, STATS_FILE)
        logger.info(f"СОХРАНЕНО: {len(data)} пользователей")
    except Exception as e:
        logger.error(f"ОШИБКА сохранения: {e}")

def record_user_search(chat_id, username, first_name, query):
    """Запись поискового запроса"""
    try:
        user_data = load_user_data()
        chat_id_str = str(chat_id)
        
        if chat_id_str not in user_data:
            user_data[chat_id_str] = {
                'username': username or 'unknown',
                'first_name': first_name or 'user',
                'created_at': datetime.now().isoformat(),
                'search_requests': []
            }
        
        search_request = {
            'query': query,
            'timestamp': datetime.now().isoformat()
        }
        user_data[chat_id_str]['search_requests'].append(search_request)
        
        if len(user_data[chat_id_str]['search_requests']) > 50:
            user_data[chat_id_str]['search_requests'] = user_data[chat_id_str]['search_requests'][-50:]
        
        save_user_data(user_data)
        logger.info(f"📊 Запрос '{query}' от пользователя {username}")
    except Exception as e:
        logger.error(f"ОШИБКА записи статистики: {e}")

# ==================== API КЛИЕНТ РГГУ ====================

class RGGUAPIClient:
    """Клиент для работы с API расписания РГГУ"""
    
    def __init__(self):
        self.base_url = 'https://raspis.rggu.ru'
        self.timeout = 10

    def get_teachers_list(self):
        """Получение списка преподавателей"""
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
        """Поиск преподавателей по фамилии"""
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
        """Получение расписания преподавателя"""
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
    """Создание главного меню"""
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
                text="📊 Статистика",
                payload="cmd_stats",
                intent=Intent.DEFAULT
            ),
            CallbackButton(
                text="📋 Помощь",
                payload="cmd_help",
                intent=Intent.DEFAULT
            )
        ]
    ]
    return Attachment(type="inline_keyboard", payload=ButtonsPayload(buttons=buttons))

def create_teacher_list_buttons(teachers: list) -> Attachment:
    """Создание кнопок со списком преподавателей"""
    buttons = []
    for i, teacher in enumerate(teachers):
        # Обрезаем длинные имена
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
    """Создание кнопок выбора периода"""
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
    """Создание меню продолжения после показа расписания"""
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

def format_schedule(schedule, teacher_name) -> str:
    """Форматирование расписания для отправки"""
    if not schedule or 'tblData' not in schedule:
        return "❌ Не удалось загрузить расписание"
    
    if not schedule['tblData']:
        return "📭 Занятий нет в выбранный период"
    
    result = f"📅 {schedule.get('itemName', 'Расписание')}\n"
    result += f"👤 {teacher_name}\n"
    result += f"📆 {schedule.get('interval', '')}\n\n"
    
    days_displayed = 0
    for day in schedule['tblData']:
        if days_displayed >= 15:
            break
            
        result += f"📅 {day.get('date', '')}\n"
        
        if 'pairs' in day and day['pairs']:
            for pair in day['pairs']:
                if 'flows' in pair and pair['flows']:
                    for flow in pair['flows']:
                        pair_num = pair.get('pair', '')
                        pair_time = PAIR_TIMES.get(str(pair_num), '')
                        
                        result += f"🕒 Пара {pair_num} ({pair_time})\n"
                        result += f"📚 {flow.get('subject', '')}\n"
                        result += f"🎯 {flow.get('lessontype', '')}\n"
                        
                        flow_name = flow.get('flow', '')
                        course = flow.get('course', '')
                        
                        if flow_name and flow_name != '-':
                            if course and course != '-':
                                result += f"👥 Поток: {flow_name} (курс {course})\n"
                            else:
                                result += f"👥 Поток: {flow_name}\n"
                        
                        room = flow.get('room', '')
                        if room:
                            result += f"🏫 Аудитория: {room}\n"
                        
                        result += "\n"
        else:
            result += "📭 Нет занятий\n"
            
        result += "─" * 10 + "\n\n"
        days_displayed += 1
    
    if days_displayed < len(schedule['tblData']):
        result += f"... и еще {len(schedule['tblData']) - days_displayed} дней\n\n"
    
    return result

def is_valid_date(date_string):
    """Проверка формата даты"""
    try:
        datetime.strptime(date_string, '%d.%m.%Y')
        return True
    except ValueError:
        return False

def is_valid_date_range(start_date, end_date):
    """Проверка диапазона дат"""
    try:
        start = datetime.strptime(start_date, '%d.%m.%Y')
        end = datetime.strptime(end_date, '%d.%m.%Y')
        return end >= start
    except ValueError:
        return False

# ==================== ОБРАБОТЧИКИ СООБЩЕНИЙ ====================

@dp.bot_started()
async def on_bot_started(event: BotStarted, context: MemoryContext):
    """Приветствие при первом запуске"""
    chat_id = event.chat.chat_id
    try:
        await bot.send_message(
            chat_id=chat_id,
            text="🎓 **Бот расписания РГГУ**\n\n"
                 "Я помогу найти расписание преподавателей.\n\n"
                 "🔍 Нажми кнопку **«Найти преподавателя»** чтобы начать поиск.",
            attachments=[create_main_menu()]
        )
    except Exception as e:
        logger.error(f"Ошибка в on_bot_started: {e}")

@dp.message_created(F.message.body.text == '/start')
async def cmd_start(event: MessageCreated):
    """Обработчик команды /start"""
    chat_id = event.message.recipient.chat_id
    try:
        await bot.send_message(
            chat_id=chat_id,
            text="🎓 **Бот расписания РГГУ**\n\n"
                 "Я помогу найти расписание преподавателей.\n\n"
                 "🔍 Нажми кнопку **«Найти преподавателя»** чтобы начать поиск.",
            attachments=[create_main_menu()]
        )
    except Exception as e:
        logger.error(f"Ошибка в cmd_start: {e}")

@dp.message_created(F.message.body.text == '/help')
async def cmd_help(event: MessageCreated):
    """Обработчик команды /help"""
    chat_id = event.message.recipient.chat_id
    try:
        await bot.send_message(
            chat_id=chat_id,
            text="📋 **Помощь**\n\n"
                 "/start - Главное меню\n"
                 "/cancel - Отмена текущего действия\n"
                 "/help - Эта справка\n\n"
                 "**Как пользоваться:**\n"
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
    """Обработчик команды /cancel"""
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
    """Обработка кнопки 'Найти преподавателя'"""
    chat_id = event.message.recipient.chat_id
    
    # Всегда отправляем ответ на callback
    await event.answer(notification="🔍 Начинаем поиск...")
    
    try:
        await context.clear()
        await context.set_state(ScheduleStates.searching)
        
        await bot.send_message(
            chat_id=chat_id,
            text="🔍 **Введите фамилию преподавателя**\n\n"
                 "Например: Иванов, Петрова, Смирнов\n\n"
                 "❌ Для отмены введите /cancel"
        )
    except Exception as e:
        logger.error(f"Ошибка в callback_search: {e}")

@dp.message_callback(F.callback.payload == "cmd_stats")
async def callback_stats(event: MessageCallback):
    """Обработка кнопки 'Статистика'"""
    chat_id = event.message.recipient.chat_id
    
    await event.answer(notification="📊 Загружаю статистику...")
    
    try:
        user_data = load_user_data()
        
        if not user_data:
            await bot.send_message(
                chat_id=chat_id,
                text="📊 Статистика пока пуста.\n\n"
                     "Начните искать расписание, и данные появятся здесь!",
                attachments=[create_main_menu()]
            )
            return
        
        total_users = len(user_data)
        total_searches = sum(len(u.get('search_requests', [])) for u in user_data.values())
        
        stats_text = f"📊 **Статистика бота**\n\n"
        stats_text += f"👥 Всего пользователей: {total_users}\n"
        stats_text += f"🔍 Всего поисков: {total_searches}\n\n"
        
        top_users = sorted(
            user_data.items(),
            key=lambda x: len(x[1].get('search_requests', [])),
            reverse=True
        )[:5]
        
        if top_users:
            stats_text += "🏆 **Топ 5 активных пользователей:**\n"
            for i, (chat_id_str, data) in enumerate(top_users, 1):
                username = data.get('username', 'unknown')
                searches = len(data.get('search_requests', []))
                stats_text += f"{i}. @{username} — {searches} запросов\n"
        
        await bot.send_message(
            chat_id=chat_id,
            text=stats_text,
            attachments=[create_main_menu()]
        )
    except Exception as e:
        logger.error(f"Ошибка в callback_stats: {e}")

@dp.message_callback(F.callback.payload == "cmd_help")
async def callback_help(event: MessageCallback):
    """Обработка кнопки 'Помощь'"""
    await event.answer(notification="📋 Справка")
    
    chat_id = event.message.recipient.chat_id
    try:
        await bot.send_message(
            chat_id=chat_id,
            text="📋 **Помощь**\n\n"
                 "/start - Главное меню\n"
                 "/cancel - Отмена текущего действия\n"
                 "/help - Эта справка\n\n"
                 "**Как пользоваться:**\n"
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
    """Обработка кнопки 'Главное меню'"""
    await event.answer()
    
    chat_id = event.message.recipient.chat_id
    try:
        await context.clear()
        await bot.send_message(
            chat_id=chat_id,
            text="🏠 **Главное меню**\n\nВыберите действие:",
            attachments=[create_main_menu()]
        )
    except Exception as e:
        logger.error(f"Ошибка в callback_main: {e}")

@dp.message_callback(F.callback.payload == "cmd_cancel")
async def callback_cancel(event: MessageCallback, context: MemoryContext):
    """Обработка кнопки 'Отмена'"""
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
    """Обработка кнопки 'Другой период'"""
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
                     f"**Выберите период:**",
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
    """Обработка выбора преподавателя из списка"""
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
                text=f"✅ **Выбран преподаватель:** {teacher['name']}\n\n"
                     f"**Выберите период:**",
                attachments=[create_period_buttons()]
            )
        else:
            await event.answer(notification="❌ Ошибка выбора")
    except Exception as e:
        logger.error(f"Ошибка выбора преподавателя: {e}")
        await event.answer(notification="❌ Ошибка")

@dp.message_callback(F.callback.payload.startswith("period_"))
async def callback_select_period(event: MessageCallback, context: MemoryContext):
    """Обработка выбора периода"""
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
            # Произвольные даты
            await context.set_state(ScheduleStates.awaiting_start_date)
            await bot.send_message(
                chat_id=chat_id,
                text="📅 **Введите начальную дату** в формате ДД.ММ.ГГГГ\n"
                     "Пример: 15.12.2025\n\n"
                     "❌ Для отмены введите /cancel"
            )
            return
        
        # Загружаем расписание
        schedule = api_client.get_teacher_schedule(teacher['id'], period_info['mode'])
        
        if schedule:
            formatted = format_schedule(schedule, teacher['name'])
            
            # Разбиваем длинные сообщения
            if len(formatted) > 4000:
                parts = [formatted[i:i+4000] for i in range(0, len(formatted), 4000)]
                for part in parts:
                    await bot.send_message(chat_id=chat_id, text=part)
            else:
                await bot.send_message(chat_id=chat_id, text=formatted)
            
            await context.set_state(ScheduleStates.showing_schedule)
            await bot.send_message(
                chat_id=chat_id,
                text="✅ Расписание показано!\n\n"
                     "**Что дальше?**",
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
    """Обработка текстовых сообщений"""
    chat_id = event.message.recipient.chat_id
    text = event.message.body.text
    
    if not text or text.startswith('/'):
        return
    
    try:
        current_state = await context.get_state()
        username = event.message.sender.username or 'unknown'
        first_name = event.message.sender.first_name or 'user'
        
        # Состояние: поиск преподавателя
        if current_state == ScheduleStates.searching:
            await handle_teacher_search(chat_id, text, username, first_name, context)
            return
        
        # Состояние: ожидание начальной даты
        if current_state == ScheduleStates.awaiting_start_date:
            await handle_start_date(chat_id, text, context)
            return
        
        # Состояние: ожидание конечной даты
        if current_state == ScheduleStates.awaiting_end_date:
            await handle_end_date(chat_id, text, context)
            return
        
        # Если пользователь ввел текст в непонятном состоянии
        await bot.send_message(
            chat_id=chat_id,
            text="❓ Используйте кнопки для навигации или введите /start для начала.",
            attachments=[create_main_menu()]
        )
    except Exception as e:
        logger.error(f"Ошибка в handle_message: {e}")

async def handle_teacher_search(chat_id: int, query: str, username: str, first_name: str, context: MemoryContext):
    """Обработка поиска преподавателя"""
    try:
        # Записываем статистику
        record_user_search(chat_id, username, first_name, query)
        
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
        
        # Сохраняем список преподавателей в контексте
        await context.update_data(teachers_list=teachers)
        await context.set_state(ScheduleStates.selecting_teacher)
        
        await bot.send_message(
            chat_id=chat_id,
            text=f"📋 **Найдено преподавателей:** {len(teachers)}\n\n"
                 f"**Выберите преподавателя:**",
            attachments=[create_teacher_list_buttons(teachers)]
        )
    except Exception as e:
        logger.error(f"Ошибка в handle_teacher_search: {e}")

async def handle_start_date(chat_id: int, text: str, context: MemoryContext):
    """Обработка ввода начальной даты"""
    try:
        if is_valid_date(text):
            await context.update_data(start_date=text)
            await context.set_state(ScheduleStates.awaiting_end_date)
            await bot.send_message(
                chat_id=chat_id,
                text="📅 **Введите конечную дату** в формате ДД.ММ.ГГГГ\n"
                     "Пример: 20.12.2025\n\n"
                     "❌ Для отмены введите /cancel"
            )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text="❌ **Неверный формат даты!**\n\n"
                     "Используйте формат: ДД.ММ.ГГГГ\n"
                     "Пример: 15.12.2025"
            )
    except Exception as e:
        logger.error(f"Ошибка в handle_start_date: {e}")

async def handle_end_date(chat_id: int, text: str, context: MemoryContext):
    """Обработка ввода конечной даты"""
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
                        formatted = format_schedule(schedule, teacher['name'])
                        
                        if len(formatted) > 4000:
                            parts = [formatted[i:i+4000] for i in range(0, len(formatted), 4000)]
                            for part in parts:
                                await bot.send_message(chat_id=chat_id, text=part)
                        else:
                            await bot.send_message(chat_id=chat_id, text=formatted)
                        
                        await context.set_state(ScheduleStates.showing_schedule)
                        await bot.send_message(
                            chat_id=chat_id,
                            text="✅ Расписание показано!\n\n"
                                 "**Что дальше?**",
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
                    text="❌ **Конечная дата не может быть раньше начальной!**\n\n"
                         f"Начальная: {start_date}\n"
                         f"Введите конечную дату позже:"
                )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text="❌ **Неверный формат даты!**\n\n"
                     "Используйте формат: ДД.ММ.ГГГГ\n"
                     "Пример: 20.12.2025"
            )
    except Exception as e:
        logger.error(f"Ошибка в handle_end_date: {e}")

# ==================== ЗАПУСК БОТА ====================

async def main():
    logger.info("🎓 Бот расписания РГГУ для MAX запущен!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
