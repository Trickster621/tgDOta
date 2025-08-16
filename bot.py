# bot.py — финальная интегрированная версия
import logging
import os
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
UPDATES_PAGE_URL = urljoin(BASE_URL, "/updates")

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

# ---------- Conversation states ----------
WAITING_FOR_DOTA_ID = 1

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

    try:
        # Шаг 1: Получаем страницу со списком обновлений
        updates_page_response = scraper.get(UPDATES_PAGE_URL, timeout=10)
        updates_page_response.raise_for_status()

        updates_soup = BeautifulSoup(updates_page_response.text, "html.parser")
        
        # Шаг 2: Находим ссылку на последнее обновление, используя новый селектор
        latest_update_link = updates_soup.find("a", class_="updates-item")
        
        if not latest_update_link:
            await update.message.reply_text("Не удалось найти ссылки на обновления на сайте. Попробуйте позже.")
            return
            
        latest_update_url = urljoin(BASE_URL, latest_update_link.get("href"))

        # Шаг 3: Переходим по ссылке и парсим страницу обновления
        update_page_response = scraper.get(latest_update_url, timeout=10)
        update_page_response.raise_for_status()

        update_soup = BeautifulSoup(update_page_response.text, "html.parser")
        
        # Находим заголовок и контент
        title = update_soup.find("h1", class_="updates-title").get_text(strip=True) if update_soup.find("h1", class_="updates-title") else "Без названия"
        content_div = update_soup.find("div", class_="updates-content")
        
        if not content_div:
            await update.message.reply_text("Не удалось найти контент обновления. Попробуйте позже.")
            return

        text = content_div.get_text(separator="\n", strip=True)
        images = [urljoin(BASE_URL, img.get("src")) for img in content_div.find_all("img") if img.get("src")]

        # Отправляем текст
        text_to_send = f"*{title}*\n\n{text}"
        if len(text_to_send) > 4096:
            text_to_send = text_to_send[:4000] + "\n\n_(текст обрезан)_"
        
        await update.message.reply_text(text_to_send, parse_mode='Markdown')

        # Отправляем картинки
        for img_url in images[:10]:
            try:
                await update.message.reply_photo(photo=img_url)
            except Exception:
                try:
                    r = scraper.get(img_url, timeout=10)
                    if r.status_code == 200 and r.content:
                        bio = BytesIO(r.content)
                        await update.message.reply_photo(photo=bio)
                except Exception as e:
                    logger.warning(f"Failed to send image {img_url}: {e}")

        # Кнопка "Читать на сайте"
        kb = [[InlineKeyboardButton("Читать на сайте", url=latest_update_url)]]
        await update.message.reply_text("Источник:", reply_markup=InlineKeyboardMarkup(kb))

    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP Error: {e.response.status_code} on {e.request.url}")
        await update.message.reply_text("Не удалось получить информацию об обновлениях. Возможно, сайт недоступен.")
    except Exception as e:
        logger.exception("Error scraping latest update from website")
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
        return WAITING_FOR_DOTA_ID

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
