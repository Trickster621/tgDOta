import logging
import os
from io import BytesIO
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ---- Настройки ----
TOKEN = os.environ.get("BOT_TOKEN") or "ВАШ_ТОКЕН_ТЕЛЕГРАМ"
UPDATE_PAGE = "https://dota1x6.com/updates/?page=1&count=20"
BASE_URL = "https://dota1x6.com"

# ---- Логирование ----
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def fetch_updates_list():
    """Запрашивает список обновлений из API и возвращает первый элемент (или None)."""
    try:
        resp = requests.get(UPDATE_PAGE, timeout=10)
    except Exception as e:
        logger.warning("HTTP error while requesting updates list: %s", e)
        return None

    if resp.status_code != 200:
        logger.warning("Updates API returned status %s", resp.status_code)
        return None

    try:
        j = resp.json()
    except ValueError:
        logger.warning("Updates endpoint did not return JSON (len=%d)", len(resp.text))
        return None

    # Попробуем найти массив элементов в наиболее вероятных полях
    items = None
    if isinstance(j, dict):
        for key in ("data", "items", "result", "updates"):
            if key in j and isinstance(j[key], (list, tuple)):
                items = j[key]
                break
    elif isinstance(j, list):
        items = j

    if not items:
        logger.warning("No updates items found in JSON response")
        return None

    if len(items) == 0:
        return None

    return items[0]  # первый элемент — последнее обновление


def fetch_update_detail(link_or_slug):
    """По ссылке/слагу возращает (title, text, [image_urls], full_link) или None при ошибке."""
    if not link_or_slug:
        return None

    full_link = link_or_slug if link_or_slug.startswith("http") else urljoin(BASE_URL, link_or_slug)
    try:
        resp = requests.get(full_link, timeout=10)
    except Exception as e:
        logger.warning("Error requesting detail page %s: %s", full_link, e)
        return None

    if resp.status_code != 200:
        logger.warning("Detail page returned status %s for %s", resp.status_code, full_link)
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # Попытки найти основной контейнер с содержимым
    content_div = (
        soup.find("div", class_="update-content")
        or soup.find("article")
        or soup.find("div", attrs={"role": "article"})
        or soup.find("div", class_=lambda c: c and "update" in c)
        or soup.body
    )

    title = soup.title.string.strip() if soup.title and soup.title.string else None
    text = content_div.get_text(separator="\n", strip=True) if content_div else None

    # картинки (абсолютные URL)
    images = []
    if content_div:
        for img in content_div.find_all("img"):
            src = img.get("src")
            if not src:
                continue
            images.append(src if src.startswith("http") else urljoin(BASE_URL, src))

    return {"title": title or "Без названия", "text": text or "", "images": images, "url": full_link}


async def last_update_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Асинхронный обработчик команды /lastupdate"""
    await update.message.chat.send_action("typing")
    item = fetch_updates_list()
    if not item:
        await update.message.reply_text("Не удалось получить список обновлений (API недоступен).")
        return

    # В разных вариантах поля названия/ссылки могут называться по-разному
    link = item.get("url") or item.get("link") or item.get("slug") or item.get("path") or item.get("href")
    title_from_list = item.get("title") or item.get("name") or item.get("header")

    detail = fetch_update_detail(link)
    if not detail:
        # fallback: если не удалось получить детальную страницу, попробуем собрать из того, что есть в элементе списка
        summary = item.get("summary") or item.get("excerpt") or item.get("content") or ""
        title = title_from_list or "Последнее обновление"
        body = summary or "(нет содержимого)"
        await update.message.reply_text(f"{title}\n\n{body}")
        await update.message.reply_text("Смотреть все обновления: https://dota1x6.com/updates")
        return

    # отправляем текст — plain text (чтобы не ломать Markdown)
    text_to_send = f"{detail['title']}\n\n{detail['text']}"
    # Обрезаем, если слишком длинно для одного сообщения
    if len(text_to_send) > 3900:
        text_to_send = text_to_send[:3900] + "\n\n(Текст обрезан...)"

    await update.message.reply_text(text_to_send)

    # отправляем картинки (если есть)
    for img_url in detail["images"]:
        try:
            # можно отправлять URL напрямую
            await update.message.reply_photo(photo=img_url)
        except Exception as e:
            logger.warning("Failed to send image %s: %s", img_url, e)
            # пробуем скачать и отправить как BytesIO
            try:
                r = requests.get(img_url, timeout=10)
                if r.status_code == 200 and r.content:
                    bio = BytesIO(r.content)
                    bio.name = os.path.basename(img_url)
                    bio.seek(0)
                    await update.message.reply_photo(photo=bio)
            except Exception as ee:
                logger.warning("Also failed to fetch image %s: %s", img_url, ee)
                continue

    # кнопка "Все обновления"
    keyboard = [[InlineKeyboardButton("Все обновления", url=f"{BASE_URL}/updates")]]
    await update.message.reply_text("Смотрите все обновления:", reply_markup=InlineKeyboardMarkup(keyboard))


def main():
    if TOKEN == "ВАШ_ТОКЕН_ТЕЛЕГРАМ":
        logger.warning("TOKEN is placeholder. Set BOT_TOKEN env var or replace token in code.")

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("lastupdate", last_update_command))
    logger.info("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
