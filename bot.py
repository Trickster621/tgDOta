# bot.py — финальная интегрированная версия (ReplyKeyboard + ConversationHandler + updates via API)
import logging
import os
from io import BytesIO
from urllib.parse import urljoin
from datetime import datetime

import requests
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
OWNER_ID = 741409144
USER_LOG_FILE = "user_messages.txt"

UPDATE_PAGE = "https://dota1x6.com/updates/?page=1&count=20"
BASE_URL = "https://dota1x6.com"

# ---------- ЛОГИ ----------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------- Утилиты ----------
if not os.path.exists(USER_LOG_FILE):
    open(USER_LOG_FILE, "w", encoding="utf-8").close()

def log_user_message(user, text):
    try:
        with open(USER_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(
                f"{datetime.now()} | ID:{getattr(user,'id',None)} | "
                f"Имя:{getattr(user,'first_name',None)} | "
                f"Username:@{getattr(user,'username',None)} | {text}\n"
            )
    except Exception:
        logger.exception("Не удалось записать лог пользователя")

# ---------- Conversation states ----------
WAITING_FOR_DOTA_ID = 1

# ---------- API / парсинг апдейтов ----------
def fetch_updates_list_first_item():
    """Возвращает первый элемент списка обновлений (dict) или None."""
    try:
        r = requests.get(UPDATE_PAGE, timeout=10)
        if r.status_code != 200:
            logger.warning("Updates list returned status %s", r.status_code)
            return None
        j = r.json()  # может вызывать ValueError
    except Exception as e:
        logger.warning("Cannot fetch updates list: %s", e)
        return None

    items = None
    if isinstance(j, dict):
        for key in ("data", "items", "result", "updates"):
            if key in j and isinstance(j[key], (list, tuple)):
                items = j[key]
                break
    elif isinstance(j, list):
        items = j

    if not items:
        return None
    if len(items) == 0:
        return None
    return items[0]

def fetch_update_detail(link_or_slug):
    """Возвращает dict: {title, text, images:list, url} или None."""
    if not link_or_slug:
        return None
    full_link = link_or_slug if link_or_slug.startswith("http") else urljoin(BASE_URL, link_or_slug)
    try:
        r = requests.get(full_link, timeout=10)
        if r.status_code != 200:
            logger.warning("detail page returned %s for %s", r.status_code, full_link)
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        # Ищем контейнер с контентом
        content = (
            soup.find("div", class_="update-content")
            or soup.find("article")
            or soup.find("div", attrs={"role": "article"})
            or soup.find("div", class_=lambda c: c and "update" in c)
            or soup.body
        )
        title = (soup.title.string.strip() if soup.title and soup.title.string else None) or ""
        text = content.get_text(separator="\n", strip=True) if content else ""
        images = []
        if content:
            for img in content.find_all("img"):
                src = img.get("src")
                if not src:
                    continue
                images.append(src if src.startswith("http") else urljoin(BASE_URL, src))
        return {"title": title or "Без названия", "text": text or "", "images": images, "url": full_link}
    except Exception as e:
        logger.warning("Error fetching detail %s: %s", link_or_slug, e)
        return None

# ---------- Handlers ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_user_message(user, "/start")
    keyboard = [["Проверить статистику", "Обновления"]]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Привет! Выберите действие:", reply_markup=markup)

# Обработчик: кнопка "Обновления" — берём последний апдейт и шлём текст + картинки
async def handle_updates_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_user_message(user, "Обновления")
    item = fetch_updates_list_first_item()
    if not item:
        await update.message.reply_text("Не удалось получить список обновлений.")
        return

    # возможные поля ссылки/слага
    link = item.get("url") or item.get("link") or item.get("slug") or item.get("path") or item.get("href")
    title_in_list = item.get("title") or item.get("name") or item.get("header") or ""
    detail = fetch_update_detail(link)

    if not detail:
        # fallback — попытаться взять текст прямо из item
        summary = item.get("summary") or item.get("excerpt") or item.get("content") or ""
        title = title_in_list or "Последнее обновление"
        body = summary or "(нет содержимого)"
        await update.message.reply_text(f"{title}\n\n{body}")
        await update.message.reply_text("Все обновления: https://dota1x6.com/updates")
        return

    # отправляем текст (без markdown, plain text)
    text_to_send = f"{detail['title']}\n\n{detail['text']}"
    if len(text_to_send) > 3900:
        text_to_send = text_to_send[:3900] + "\n\n(текст обрезан)"
    await update.message.reply_text(text_to_send)

    # отправляем картинки
    for img_url in detail["images"]:
        try:
            # попытаемся отправить URL напрямую
            await update.message.reply_photo(photo=img_url)
        except Exception:
            # если не получится — скачиваем и отправляем как BytesIO
            try:
                r = requests.get(img_url, timeout=10)
                if r.status_code == 200 and r.content:
                    bio = BytesIO(r.content)
                    bio.name = os.path.basename(img_url)
                    bio.seek(0)
                    await update.message.reply_photo(photo=bio)
            except Exception:
                logger.warning("Failed to send image %s", img_url)
                continue

    # кнопка "Все обновления"
    kb = [[InlineKeyboardButton("Все обновления", url=f"{BASE_URL}/updates")]]
    await update.message.reply_text("Смотреть все обновления:", reply_markup=InlineKeyboardMarkup(kb))

# Conversation: старт проверки статистики
async def check_stats_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_user_message(user, "Проверить статистику (start)")
    await update.message.reply_text("Введите числовой Dota ID:")
    return WAITING_FOR_DOTA_ID

# Conversation: получили ID
async def check_stats_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()
    log_user_message(user, text)

    if not text.isdigit():
        await update.message.reply_text("Пожалуйста, введите только числовой Dota ID или отправьте /cancel")
        return WAITING_FOR_DOTA_ID

    dota_id = text
    url = f"https://stats.dota1x6.com/api/v2/players/?playerId={dota_id}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            await update.message.reply_text("Не удалось получить данные с API.")
            return ConversationHandler.END
        data = r.json().get("data")
        if not data:
            await update.message.reply_text("Игрок с таким ID не найден.")
            return ConversationHandler.END

        match_count = data.get("matchCount", "неизвестно")
        avg_place = round(data.get("avgPlace", 0), 2)
        first_places = data.get("firstPlaces", "неизвестно")
        rating = data.get("rating", "неизвестно")

        msg = (
            f"Всего игр: {match_count}\n"
            f"Среднее место: {avg_place}\n"
            f"Первых мест: {first_places}\n"
            f"Рейтинг: {rating}"
        )
        await update.message.reply_text(msg)

        # mini app кнопка
        player_url = f"https://dota1x6.com/players/{dota_id}"
        inline = [[InlineKeyboardButton("Посмотреть историю игр", web_app=WebAppInfo(url=player_url))]]
        await update.message.reply_text("Вы можете посмотреть историю игр:", reply_markup=InlineKeyboardMarkup(inline))

    except Exception as e:
        logger.exception("Ошибка при получении статистики")
        await update.message.reply_text("Произошла ошибка при получении данных.")
    return ConversationHandler.END

# /cancel — выйти из Conversation
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_user_message(user, "/cancel")
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END

# /getlog для владельца
async def getlog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_user_message(user, "/getlog")
    if user.id != OWNER_ID:
        await update.message.reply_text("Нет доступа")
        return
    if not os.path.exists(USER_LOG_FILE):
        await update.message.reply_text("Файл логов пуст.")
        return
    with open(USER_LOG_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    bio = BytesIO()
    bio.write(content.encode("utf-8"))
    bio.seek(0)
    await update.message.reply_document(document=bio, filename="user_messages.txt")

# /previewlog
async def previewlog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_user_message(user, "/previewlog")
    if user.id != OWNER_ID:
        await update.message.reply_text("Нет доступа")
        return
    with open(USER_LOG_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    last_lines = "".join(lines[-50:]) if lines else "(пусто)"
    if len(last_lines) > 3500:
        last_lines = last_lines[-3500:]
    await update.message.reply_text(f"Последние строки лога:\n\n{last_lines}")

# ---------- main ----------
def main():
    if TOKEN == "ВАШ_ТОКЕН_ТЕЛЕГРАМ":
        logger.warning("TOKEN — плейсхолдер. Задайте BOT_TOKEN в окружении или замените в коде.")

    app = ApplicationBuilder().token(TOKEN).build()

    # ConversationHandler для проверки статистики
    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Проверить статистику$"), check_stats_start)],
        states={WAITING_FOR_DOTA_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_stats_id)]},
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    # handler: кнопка Обновления (текстовая кнопка)
    updates_handler = MessageHandler(filters.Regex("^Обновления$"), handle_updates_button)

    # start and logs
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("getlog", getlog))
    app.add_handler(CommandHandler("previewlog", previewlog))

    app.add_handler(conv)
    app.add_handler(updates_handler)

    # любой другой текст (кроме команд) — подсказка
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u,c: u.message.reply_text("Используйте кнопки внизу.")))

    logger.info("Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()
