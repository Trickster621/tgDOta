import logging
import os
from urllib.parse import urljoin

import cloudscraper
from bs4 import BeautifulSoup
from telegram.ext import Application, CommandHandler

BOT_TOKEN = os.getenv("BOT_TOKEN", "ВАШ_ТОКЕН")
CHAT_ID = os.getenv("CHAT_ID")  # куда слать апдейт
BASE_URL = "https://dota1x6.com"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

scraper = cloudscraper.create_scraper()


def fetch_updates_list_first_item():
    try:
        r = scraper.get(f"{BASE_URL}/updates", timeout=10)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "html.parser")

        first_card = soup.find("div", class_="card")
        if not first_card:
            return None

        link_tag = first_card.find("a", href=True)
        if not link_tag:
            return None

        title = link_tag.get_text(strip=True)
        link = urljoin(BASE_URL, link_tag["href"])

        return {"title": title, "url": link}
    except Exception as e:
        logger.warning("Ошибка списка обновлений: %s", e)
        return None


def fetch_update_detail(link):
    try:
        r = scraper.get(link, timeout=10)
        if r.status_code != 200:
            return None

        soup = BeautifulSoup(r.text, "html.parser")
        content_div = soup.find("div", class_="news-detail")
        if not content_div:
            return None

        paragraphs = content_div.find_all(["p", "li"])
        text = "\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
        return text
    except Exception as e:
        logger.warning("Ошибка детали обновления: %s", e)
        return None


async def send_last_update(app: Application):
    item = fetch_updates_list_first_item()
    if not item:
        await app.bot.send_message(chat_id=CHAT_ID, text="❌ Не удалось получить список обновлений")
        return

    detail = fetch_update_detail(item["url"])
    if not detail:
        await app.bot.send_message(chat_id=CHAT_ID, text=f"{item['title']}\n{item['url']}")
    else:
        text = f"📌 {item['title']}\n\n{detail[:3500]}"
        await app.bot.send_message(chat_id=CHAT_ID, text=text)


# /start — просто существует, ничего не отвечает
async def start(update, context):
    pass


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))

    logger.info("Bot started")

    # сразу после старта контейнера шлём последнее обновление
    app.post_init = lambda _: send_last_update(app)

    app.run_polling()


if __name__ == "__main__":
    main()
