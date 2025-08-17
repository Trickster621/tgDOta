# bot.py — финальная интегрированная версия, использующая API
import logging
import os
import re
from io import BytesIO
from urllib.parse import urljoin
from datetime import datetime

import requests
import cloudscraper
from bs4 import BeautifulSoup
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ---------- НАСТРОЙКИ ----------
TOKEN = os.environ.get("BOT_TOKEN") or "ВАШ_ТОКЕН_ТЕЛЕГРАМ"
OWNER_ID = 741409144  # Замените на ваш Telegram ID, если нужно
USER_LOG_FILE = "user_messages.txt"
BASE_URL = "https://dota1x6.com"
# URL к API для получения информации об обновлений
API_UPDATES_URL = "https://stats.dota1x6.com/api/v2/updates/?page=1&count=20"

# ---------- ЛОГИ ----------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# cloudscraper для обхода Cloudflare
scraper = cloudscraper.create_scraper()

# ---------- Утилиты ----------
if not os.path.exists(USER_LOG_FILE):
    open(USER_LOG_FILE, "w", encoding="utf-8").close()

def log_user_message(user, text):
    try:
        with open(USER_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(
                f"{datetime.now()} | ID:{getattr(user, 'id', None)} | "
                f"Имя:{getattr(user, 'first_name', None)} | "
                f"Username:@{getattr(user, 'username', None)} | {text}\n"
            )
    except Exception:
        logger.exception("Не удалось записать лог пользователя")

def escape_markdown(text):
    """Экранирует специальные символы Markdown V2."""
    if not isinstance(text, str):
        return ""
    
    # Символы, которые нужно экранировать в Markdown V2
    # _, *, [, ], (, ), ~, `, >, #, +, -, =, |, {, }, ., !
    escape_chars = r"[_*[\]()~`>#+\-=|{}.!]"
    return re.sub(escape_chars, r'\\\g<0>', text)


# ---------- Conversation states ----------
WAITING_FOR_DOTA_ID = 1

# ---------- API ----------
def get_latest_update_info_from_api():
    """
    Получает информацию о последнем обновлении с API.
    Возвращает словарь с данными или None в случае ошибки.
    """
    try:
        r = requests.get(API_UPDATES_URL, timeout=10)
        r.raise_for_status()
        
        data = r.json().get("data")
        if not data:
            logger.warning("API returned no data key")
            return None

        updates_list = data.get("values")
        
        if not updates_list or not isinstance(updates_list, list) or len(updates_list) == 0:
            logger.warning("API returned empty updates list")
            return None
            
        return updates_list[0]
            
    except requests.exceptions.HTTPError as e:
        logger.error(f"API request failed with status code {e.response.status_code}")
        return None
    except Exception:
        logger.exception("Error fetching or parsing latest update from API")
        return None

# ---------- Handlers ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_user_message(user, "/start")
    keyboard = [["Проверить статистику", "Обновления"]]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Привет! Выберите действие:", reply_markup=markup)

async def handle_updates_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_user_message(user, "Обновления")
    await update.message.reply_text("🔎 Ищу последнее обновление...")

    latest_update_info = get_latest_update_info_from_api()

    if not latest_update_info:
        await update.message.reply_text("Не удалось получить информацию об обновлениях с API. Попробуйте позже.")
        return

    update_url_slug = latest_update_info.get("url")
    if not update_url_slug:
        await update.message.reply_text("В полученных данных нет ссылки на обновление. Попробуйте позже.")
        return

    update_url = urljoin(BASE_URL, f"/updates/{update_url_slug}")

    api_update_url = f"https://stats.dota1x6.com/api/v2/updates/{update_url_slug}"
    
    try:
        response = requests.get(api_update_url, timeout=10)
        response.raise_for_status()
        api_data = response.json()
        
        # Извлекаем данные из JSON
        title = api_data.get("data", {}).get("ruName", "Без названия")
        text_content = ""
        heroes = api_data.get("data", {}).get("heroes", [])
        
        # Создаем карту эмодзи для удобства
        EMOJI_MAP = {
            "rare_talent": "🟦",
            "epic_talent": "🟪",
            "innate_talent": "🔥",
            "legendary_talent": "🟧",
            "scepter": "🔮",
            "shard": "🔷",
        }
        
        for hero in heroes:
            hero_name = hero.get("userFrendlyName", "Неизвестный герой")
            text_content += f"\n*{escape_markdown('Изменения для ')}{escape_markdown(hero_name)}*:\n"
            
            upgrades = hero.get("upgrades", [])
            if upgrades:
                for upgrade in upgrades:
                    item_type = upgrade.get("itemType")
                    emoji = ""
                    # Проверяем и добавляем эмодзи для Scepter и Shard
                    if item_type == "scepter":
                        emoji = EMOJI_MAP.get("scepter", "")
                    elif item_type == "shard":
                        emoji = EMOJI_MAP.get("shard", "")
                    
                    ru_rows = upgrade.get("ruRows")
                    if ru_rows:
                        text_content += f"{emoji} {escape_markdown(ru_rows.strip())} {emoji}\n"
            
            talents = hero.get("talents", [])
            if talents:
                for talent in talents:
                    name = talent.get("name", "")
                    emoji = ""
                    
                    # Определяем эмодзи по названию таланта
                    if name == "rare_talent":
                        emoji = EMOJI_MAP.get("rare_talent", "")
                    elif name == "epic_talent":
                        emoji = EMOJI_MAP.get("epic_talent", "")
                    elif name == "innate_talent":
                        emoji = EMOJI_MAP.get("innate_talent", "")
                    elif name == "legendary_talent":
                        emoji = EMOJI_MAP.get("legendary_talent", "")
                    
                    # Проверяем, что есть хотя бы один из талантов
                    has_talents = any(talent.get(c) for c in ["orangeRuRows", "purpleRuRows", "blueRuRows", "abilityRuRows"])
                    if not has_talents:
                        continue

                    # Если имя таланта совпадает с одним из типов, используем его
                    if name in ["rare_talent", "epic_talent", "innate_talent", "legendary_talent"]:
                        text_content += f"\n{emoji} {escape_markdown(name.capitalize())} {emoji}\n"
                    else:
                        text_content += f"\n*{escape_markdown(name.capitalize())}*:\n"
                    
                    # Добавляем строки с описанием
                    for color in ["orangeRuRows", "purpleRuRows", "blueRuRows", "abilityRuRows"]:
                        ru_rows = talent.get(color)
                        # Используем ваши подсказки для определения типа таланта
                        talent_emoji = ""
                        if color == "orangeRuRows":
                            talent_emoji = EMOJI_MAP.get("legendary_talent", "")
                        elif color == "purpleRuRows":
                            talent_emoji = EMOJI_MAP.get("epic_talent", "")
                        elif color == "blueRuRows":
                            talent_emoji = EMOJI_MAP.get("rare_talent", "")
                            
                        if ru_rows:
                            formatted_rows = ru_rows.replace("\r\n", "\n").strip()
                            text_content += f" {talent_emoji} \- {escape_markdown(formatted_rows)}\n"
        
        text_to_send = f"*{escape_markdown(title)}*\n\n{text_content}"
        if len(text_to_send) > 4096:
            text_to_send = text_to_send[:4000] + "\n\n_(текст обрезан)_"
        
        await update.message.reply_text(text_to_send, parse_mode='MarkdownV2')

        kb = [[
            InlineKeyboardButton("Источник", url=update_url),
            InlineKeyboardButton("Все обновления", url=urljoin(BASE_URL, "/updates"))
        ]]
        await update.message.reply_text("Смотреть на сайте:", reply_markup=InlineKeyboardMarkup(kb))

    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP Error: {e.response.status_code} on {e.request.url}")
        await update.message.reply_text("Не удалось получить информацию об обновлении. Возможно, сайт недоступен.")
    except Exception as e:
        logger.exception("Error fetching update from API")
        await update.message.reply_text("Произошла ошибка при получении данных. Попробуйте позже.")


async def check_stats_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_user_message(user, "Проверить статистику (start)")
    await update.message.reply_text("Введите числовой Dota ID:")
    return WAITING_FOR_DOTA_ID

async def check_stats_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()
    log_user_message(user, text)

    if not text.isdigit():
        await update.message.reply_text("Пожалуйста, введите только числовой Dota ID. Для отмены введите /cancel")
        return ConversationHandler.END

    dota_id = text
    url = f"https://stats.dota1x6.com/api/v2/players/?playerId={dota_id}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            await update.message.reply_text("Не удалось получить данные. Возможно, сервис недоступен.")
            return ConversationHandler.END
        
        data = r.json().get("data")
        if not data:
            await update.message.reply_text("Игрок с таким ID не найден.")
            return ConversationHandler.END

        msg = (
            f"📊 Статистика для ID: {dota_id}\n\n"
            f"Всего игр: {data.get('matchCount', 'н/д')}\n"
            f"Среднее место: {round(data.get('avgPlace', 0), 2)}\n"
            f"🏆 Первых мест: {data.get('firstPlaces', 'н/д')}\n"
            f"Рейтинг: {data.get('rating', 'н/д')}"
        )
        await update.message.reply_text(msg)

        player_url = f"https://dota1x6.com/players/{dota_id}"
        inline = [[InlineKeyboardButton("Подробная история игр", web_app=WebAppInfo(url=player_url))]]
        await update.message.reply_text("Смотреть всю историю матчей:", reply_markup=InlineKeyboardMarkup(inline))

    except Exception:
        logger.exception("Ошибка при получении статистики")
        await update.message.reply_text("Произошла ошибка при получении данных.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_user_message(user, "/cancel")
    await update.message.reply_text("Действие отменено.")
    return ConversationHandler.END

async def getlog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != OWNER_ID:
        return
    log_user_message(user, "/getlog")
    if not os.path.exists(USER_LOG_FILE):
        await update.message.reply_text("Файл логов пуст.")
        return
    await update.message.reply_document(document=open(USER_LOG_FILE, 'rb'), filename="user_messages.txt")

async def previewlog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != OWNER_ID:
        return
    log_user_message(user, "/previewlog")
    try:
        with open(USER_LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        last_lines = "".join(lines[-50:]) if lines else "(пусто)"
        if len(last_lines) > 4000:
            last_lines = "..." + last_lines[-4000:]
        await update.message.reply_text(f"Последние 50 строк лога:\n\n```\n{last_lines}\n```", parse_mode='MarkdownV2')
    except Exception:
        await update.message.reply_text("Не удалось прочитать лог.")

async def unknown_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Неизвестная команда. Пожалуйста, используйте кнопки.")

def main():
    if TOKEN == "ВАШ_ТОКЕН_ТЕЛЕГРАМ":
        logger.critical("!!! TOKEN не установлен. Замените 'ВАШ_ТОКЕН_ТЕЛЕГРАМ' в коде или установите переменную окружения BOT_TOKEN.")
        return

    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Проверить статистику$"), check_stats_start)],
        states={WAITING_FOR_DOTA_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_stats_id)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("getlog", getlog))
    app.add_handler(CommandHandler("previewlog", previewlog))
    app.add_handler(conv)
    app.add_handler(MessageHandler(filters.Regex("^Обновления$"), handle_updates_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_text))

    logger.info("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
