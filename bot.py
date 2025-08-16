import logging
import requests
from datetime import datetime
from io import BytesIO
from bs4 import BeautifulSoup
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
import os

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Токен бота
TOKEN = os.environ.get("BOT_TOKEN") or "ВАШ_НОВЫЙ_ТОКЕН"

# Telegram ID владельца
OWNER_ID = 741409144

# Путь к лог-файлу
USER_LOG_FILE = "user_messages.txt"
if not os.path.exists(USER_LOG_FILE):
    open(USER_LOG_FILE, "w", encoding="utf-8").close()

def log_user_message(user, text):
    """Сохраняем данные пользователя и сообщение в файл"""
    with open(USER_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(
            f"{datetime.now()} | ID: {user.id} | "
            f"Имя: {user.first_name} | Фамилия: {user.last_name} | "
            f"Username: @{user.username} | Сообщение: {text}\n"
        )

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    log_user_message(user, "/start")
    reply_keyboard = [["Проверить статистику", "Обновления"]]
    await update.message.reply_text(
        text="Привет! Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    )

# Обработка сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    text = update.message.text.strip()
    log_user_message(user, text)

    if text == "Проверить статистику":
        await update.message.reply_text("Введите числовой Dota ID:")
        return

    if text == "Обновления":
        await send_last_update(update)
        return

    if not text.isdigit():
        await update.message.reply_text("Неизвестная команда. Используйте кнопки ниже.")
        return

    dota_id = text
    url = f"https://stats.dota1x6.com/api/v2/players/?playerId={dota_id}"
    try:
        response = requests.get(url)
        if response.status_code != 200:
            await update.message.reply_text("Не удалось получить данные с API.")
            return

        data = response.json().get("data")
        if not data:
            await update.message.reply_text("Игрок с таким ID не найден.")
            return

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

        # Mini App кнопка
        player_url = f"https://dota1x6.com/players/{dota_id}"
        inline_keyboard = [
            [InlineKeyboardButton("Посмотреть историю игр", web_app=WebAppInfo(url=player_url))]
        ]
        await update.message.reply_text(
            "Вы можете посмотреть историю игр:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard)
        )

    except Exception as e:
        logging.error(f"Ошибка при обработке ID {text}: {e}")
        await update.message.reply_text("Произошла ошибка при получении данных.")

async def send_last_update(update: Update):
    try:
        url = "https://dota1x6.com/updates"
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            await update.message.reply_text("Не удалось получить обновления с сайта.")
            return

        soup = BeautifulSoup(r.text, "html.parser")
        table = soup.find("table")
        if not table:
            await update.message.reply_text("Не удалось найти таблицу обновлений.")
            return

        rows = table.find_all("tr")[1:]  # Пропускаем заголовок
        if not rows:
            await update.message.reply_text("Нет обновлений.")
            return

        first_row = rows[0]
        tds = first_row.find_all("td")
        title_a = tds[0].find("a")
        if not title_a:
            text_update = tds[0].get_text(strip=True)
            await update.message.reply_text(f"Последнее обновление:\n\n{text_update}")
            return

        title = title_a.get_text(strip=True)
        link = title_a["href"]
        full_link = link if link.startswith("https://") else f"https://dota1x6.com{link}"

        # Загружаем страницу обновления
        r_detail = requests.get(full_link, timeout=10)
        if r_detail.status_code != 200:
            await update.message.reply_text("Не удалось загрузить страницу обновления.")
            return

        soup_detail = BeautifulSoup(r_detail.text, "html.parser")
        content_div = soup_detail.find("div", class_="update-content") or soup_detail.find("article") or soup_detail.body
        content_text = content_div.get_text(strip=True, separator="\n") if content_div else "Нет содержимого."

        await update.message.reply_text(f"Последнее обновление: {title}\n\n{content_text}")

        # Скачиваем и отправляем картинки
        images = content_div.find_all("img") if content_div else []
        for img in images:
            img_src = img.get("src")
            if not img_src:
                continue
            img_url = img_src if img_src.startswith("https://") else f"https://dota1x6.com{img_src}"
            try:
                img_resp = requests.get(img_url, timeout=10)
                if img_resp.ok:
                    await update.message.reply_photo(photo=BytesIO(img_resp.content))
            except:
                pass

        # Кнопка "Все обновления"
        inline_keyboard = [[InlineKeyboardButton("Все обновления", url="https://dota1x6.com/updates")]]
        await update.message.reply_text("Полный список обновлений:", reply_markup=InlineKeyboardMarkup(inline_keyboard))

    except Exception as e:
        logging.error(f"Ошибка при получении обновлений: {e}")
        await update.message.reply_text("Произошла ошибка при получении обновлений.")

# /getlog — присылает весь лог
async def getlog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    log_user_message(user, "/getlog")

    if user.id != OWNER_ID:
        await update.message.reply_text("Нет доступа")
        return

    if not os.path.exists(USER_LOG_FILE):
        await update.message.reply_text("Файл логов пока пуст.")
        return

    with open(USER_LOG_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    bio = BytesIO()
    bio.write(content.encode("utf-8"))
    bio.seek(0)
    await update.message.reply_document(document=bio, filename="user_messages.txt")

# /previewlog — последние 50 сообщений
async def previewlog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
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

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("getlog", getlog))
    app.add_handler(CommandHandler("previewlog", previewlog))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
