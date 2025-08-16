from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackContext
import requests
from bs4 import BeautifulSoup

BOT_TOKEN = "ВАШ_ТОКЕН_ТЕЛЕГРАМ"

UPDATE_PAGE = "https://dota1x6.com/updates/?page=1&count=20"
BASE_URL = "https://dota1x6.com"

def get_last_update():
    # Получаем список обновлений
    resp = requests.get(UPDATE_PAGE)
    data = resp.json()
    if not data or "items" not in data or len(data["items"]) == 0:
        return None

    latest = data["items"][0]
    title = latest.get("title", "Без названия")
    link = latest.get("link", "")
    full_link = link if link.startswith("http") else f"{BASE_URL}{link}"

    # Получаем текст и картинки с детальной страницы
    resp_detail = requests.get(full_link)
    soup = BeautifulSoup(resp_detail.text, "html.parser")
    content_div = soup.find("div", class_="update-content") or soup.find("article") or soup.body
    content_text = content_div.get_text(strip=True, separator="\n") if content_div else "Нет содержимого."

    images = []
    for img in content_div.find_all("img") if content_div else []:
        img_url = img.get("src")
        if img_url:
            images.append(img_url if img_url.startswith("http") else f"{BASE_URL}{img_url}")

    return title, content_text, images, full_link

async def last_update_command(update: Update, context: CallbackContext):
    result = get_last_update()
    if not result:
        await update.message.reply_text("Не удалось найти последнее обновление.")
        return

    title, content_text, images, full_link = result

    # Отправляем текст
    await update.message.reply_text(f"*{title}*\n\n{content_text}", parse_mode="Markdown")

    # Отправляем картинки
    for img_url in images:
        await update.message.reply_photo(img_url)

    # Кнопка на все обновления
    keyboard = [[InlineKeyboardButton("Все обновления", url=f"{BASE_URL}/updates")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Смотрите все обновления:", reply_markup=reply_markup)

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("lastupdate", last_update_command))
    print("Бот запущен...")
    app.run_polling()
