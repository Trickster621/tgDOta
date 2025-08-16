import logging
import os
from urllib.parse import urljoin

import cloudscraper
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# === Настройки ===
BOT_TOKEN = os.getenv("BOT_TOKEN", "ВАШ_ТОКЕН")
BASE_URL = "https://dota1x6.com"

# Логгер
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Scraper для обхода Cloudflare
scraper = cloudscraper.create_scraper()


# === Парсинг страницы обновлений ===
def fetch_updates_list_first_item():
    """Парсит HTML /updates и возвращает dict с {title, url} для самого свежего обновления."""
    try:
        r = scraper.get(f"{BASE_URL}/updates", timeout=10)
        if r.status_code != 200:
            logger.warning("Updates page returned %s", r.status_code)
            return None
        soup = BeautifulSoup(r.text, "html.parser")

        # Берем первую карточку
        first_card = soup.find("div", class_="card")
        if not first_card:
            logger.warning("no .card found on updates page")
            return None

        link_tag = first_card.find("a", href=True)
        if not link_tag:
            logger.warning("no <a> in first card")
            return None

        title = link_tag.get_text(strip=True)
        link = urljoin(BASE_URL, link_tag["href"])

        return {"title": title, "url": link}
    except Exception as e:
        logger.warning("Cannot parse updates list: %s", e)
        return None


def fetch_update_detail(link):
    """Забирает текст с конкретной страницы обновления"""
    try:
        r = scraper.get(link, timeout=10)
        if r.status_code != 200:
            logger.warning("Update detail returned %s", r.status_code)
            return None

        soup = BeautifulSoup(r.text, "html.parser")
        content_div = soup.find("div", class_="news-detail")
        if not content_div:
            logger.warning("no news-detail content")
            return None

        # Собираем текст
        paragraphs = content_div.find_all(["p", "li"])
        text = "\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
        return text
    except Exception as e:
        logger.warning("Cannot parse update detail: %s", e)
        return None


# === Команды бота ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я бот. Используй /last_update чтобы получить последнее обновление.")


async def last_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    item = fetch_updates_list_first_item()
    if not item:
        await update.message.reply_text("❌ Не удалось получить список обновлений")
        return

    detail = fetch_update_detail(item["url"])
    if not detail:
        await update.message.reply_text(f"Последнее обновление: {item['title']}\n{item['url']}")
    else:
        text = f"📌 {item['title']}\n\n{detail[:3500]}"  # ограничение на длину
        await update.message.reply_text(text)


# === Main ===
def main():
    logger.info("Bot started")
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("last_update", last_update))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, start))

    app.run_polling()


if __name__ == "__main__":
    main()
