import os
import asyncio
from maxapi import Bot
from maxapi.types import MessageCreated, CallbackQuery
from maxapi.types import InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = os.environ.get("BOT_TOKEN")
bot = Bot(TOKEN)

# ===== ТЕКСТЫ =====
WELCOME_TEXT = """
🎓 ДОБРО ПОЖАЛОВАТЬ!

Выберите направление:

📋 ОТЧЕТ О ПП
📚 ВКР
📝 ОБЩИЕ ТРЕБОВАНИЯ
📄 ПОЛЬЗОВАТЕЛЬСКОЕ СОГЛАШЕНИЕ
"""

PP_TEXT = "📋 РАЗДЕЛ ОТЧЕТА О ПП. Выберите тему:"
REQ_TEXT = "📝 РАЗДЕЛ ОБЩИХ ТРЕБОВАНИЙ. Выберите тему:"

# ===== КНОПКИ =====
def main_menu():
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("📋 ОТЧЕТ О ПП", callback_data="menu_pp"),
        InlineKeyboardButton("📚 ВКР", callback_data="menu_vkr")
    )
    kb.add(
        InlineKeyboardButton("📝 ОБЩИЕ ТРЕБОВАНИЯ", callback_data="menu_req"),
        InlineKeyboardButton("📄 СОГЛАШЕНИЕ", callback_data="menu_privacy")
    )
    return kb

def pp_menu():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📄 О бланках", callback_data="pp_blanks"))
    kb.add(InlineKeyboardButton("📋 Индивидуальное задание", callback_data="pp_individual"))
    kb.add(InlineKeyboardButton("✅ Требования", callback_data="pp_requirements"))
    kb.add(InlineKeyboardButton("💰 Финансовый анализ", callback_data="pp_financial"))
    kb.add(InlineKeyboardButton("🌍 PESTLE", callback_data="pp_pestle"))
    kb.add(InlineKeyboardButton("⚖️ SWOT", callback_data="pp_swot"))
    kb.add(InlineKeyboardButton("🔙 НАЗАД", callback_data="back_main"))
    return kb

def req_menu():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📚 Источники", callback_data="req_sources"))
    kb.add(InlineKeyboardButton("📝 Оформление ссылок", callback_data="req_links"))
    kb.add(InlineKeyboardButton("📋 Список литературы", callback_data="req_list"))
    kb.add(InlineKeyboardButton("🐦 Птичий язык", callback_data="req_bird"))
    kb.add(InlineKeyboardButton("🔙 НАЗАД", callback_data="back_main"))
    return kb

def back_button():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔙 НАЗАД", callback_data="back_main"))
    return kb

# ===== ОБРАБОТЧИК СООБЩЕНИЙ =====
@bot.on(MessageCreated)
async def handle_message(event: MessageCreated):
    if event.message.body.text == "/start":
        await event.message.answer(WELCOME_TEXT, inline_keyboard_markup=main_menu())

# ===== ОБРАБОТЧИК КНОПОК =====
@bot.on(CallbackQuery)
async def handle_callback(event: CallbackQuery):
    data = event.data
    
    # Главное меню
    if data == "back_main":
        await event.message.edit(WELCOME_TEXT, inline_keyboard_markup=main_menu())
    
    elif data == "menu_pp":
        await event.message.edit(PP_TEXT, inline_keyboard_markup=pp_menu())
    
    elif data == "menu_req":
        await event.message.edit(REQ_TEXT, inline_keyboard_markup=req_menu())
    
    elif data == "menu_privacy":
        await event.message.edit("📄 Пользовательское соглашение...", inline_keyboard_markup=back_button())
    
    elif data == "menu_vkr":
        await event.message.edit("📚 ВКР в разработке", inline_keyboard_markup=back_button())
    
    # Разделы ПП
    elif data == "pp_blanks":
        await event.message.edit("📋 Информация о бланках...", inline_keyboard_markup=back_button())
    elif data == "pp_individual":
        await event.message.edit("📋 Индивидуальное задание...", inline_keyboard_markup=back_button())
    elif data == "pp_requirements":
        await event.message.edit("✅ Требования к отчету...", inline_keyboard_markup=back_button())
    elif data == "pp_financial":
        await event.message.edit("💰 Финансовый анализ...", inline_keyboard_markup=back_button())
    elif data == "pp_pestle":
        await event.message.edit("🌍 PESTLE-анализ...", inline_keyboard_markup=back_button())
    elif data == "pp_swot":
        await event.message.edit("⚖️ SWOT-анализ...", inline_keyboard_markup=back_button())
    
    # Разделы требований
    elif data == "req_sources":
        await event.message.edit("📚 Информация об источниках...", inline_keyboard_markup=back_button())
    elif data == "req_links":
        await event.message.edit("📝 Оформление ссылок...", inline_keyboard_markup=back_button())
    elif data == "req_list":
        await event.message.edit("📋 Список литературы...", inline_keyboard_markup=back_button())
    elif data == "req_bird":
        await event.message.edit("🐦 Про птичий язык...", inline_keyboard_markup=back_button())

# ===== ЗАПУСК =====
async def main():
    await bot.polling()

if __name__ == "__main__":
    asyncio.run(main())
