import logging
import os
import re
import json
import asyncio
import aiohttp
from io import BytesIO
from urllib.parse import urljoin
from datetime import datetime

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
    CallbackQueryHandler,
)

# ---------- НАСТРОЙКИ ----------
TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = 741409144  # Замените на ваш Telegram ID, если нужно
USER_LOG_FILE = "user_messages.txt"
BASE_URL = "https://dota1x6.com"
API_UPDATES_URL = "https://stats.dota1x6.com/api/v2/updates/?page=1&count=20"
API_HEROES_URL = "https://stats.dota1x6.com/api/v2/heroes/"
CDN_HEROES_URL = "https://cdn.dota1x6.com/shared/"

# ---------- ЛОГИ ----------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Cостояния для ConversationHandler
GET_DOTA_ID = 1

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
    
    escape_chars = r"[_*[\]()~`>#+\-=|{}.!]"
    return re.sub(escape_chars, r'\\\g<0>', text)

# ---------- API ----------
async def fetch_json(url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15) as response:
                response.raise_for_status()
                return await response.json()
    except aiohttp.ClientError as e:
        logger.error(f"HTTP error fetching {url}: {e}")
        return None
    except asyncio.TimeoutError:
        logger.error(f"Timeout fetching {url}")
        return None
    except Exception as e:
        logger.error(f"An error occurred while fetching {url}: {e}")
        return None

# ---------- Handlers ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_user_message(user, "/start")
    keyboard = [
        ["Проверить статистику", "Обновления"],
        ["Герои"]
    ]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Привет! Выберите действие:", reply_markup=markup)

async def handle_updates_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_user_message(user, "Обновления")
    await update.message.reply_text("🔎 Ищу последнее обновление...")

    latest_update_info = await fetch_json(API_UPDATES_URL)
    if not latest_update_info or not latest_update_info.get("data", {}).get("values"):
        await update.message.reply_text("Не удалось получить информацию об обновлениях с API. Попробуйте позже.")
        return

    update_url_slug = latest_update_info["data"]["values"][0].get("url")
    if not update_url_slug:
        await update.message.reply_text("В полученных данных нет ссылки на обновление. Попробуйте позже.")
        return

    update_url = urljoin(BASE_URL, f"/updates/{update_url_slug}")
    api_update_url = f"https://stats.dota1x6.com/api/v2/updates/{update_url_slug}"
    
    api_data = await fetch_json(api_update_url)
    if not api_data or not api_data.get("data"):
        await update.message.reply_text("Произошла ошибка при получении данных об обновлении. Попробуйте позже.")
        return

    data = api_data.get("data")
    title = data.get("ruName", "Без названия")
    text_content = ""
    heroes = data.get("heroes", [])

    EMOJI_MAP = {
        "purple": "🟪", "blue": "🟦", "orange": "🟧", "scepter": "🔮",
        "innate": "🔥", "shard": "🔷", "up": "🟢", "down": "🔴",
        "change": "🟡", "hero_talent": "🤓",
    }
    
    RU_NAMES = {
        "purple": "Эпический талант", "blue": "Редкий талант", "orange": "Легендарный талант",
        "scepter": "Аганим", "innate": "Врожденный талант", "shard": "Аганим шард",
        "hero_talent": "Таланты героя", "ability": "Изменения способностей",
    }
    
    SKILL_EMOJI_MAP = {
        "mist": "☁️", "aphotic": "🛡️", "curse": "💀", "borrowed": "🛡️",
        "acid": "🧪", "unstable": "💥", "greed": "💰", "chemical": "🧪",
        "manabreak": "⚡", "antimage_blink": "⚡", "counterspell": "🪄",
        "manavoid": "💥", "flux": "⚡", "field": "🛡️", "spark": "💥",
        "double": "👥", "call": "🛡️", "hunger": "🩸", "helix": "🌪️",
        "culling": "🔪", "enfeeble": "👻", "brain": "🧠", "nightmare": "💤",
        "grip": "✊", "bloodrage": "🩸", "bloodrite": "🩸", "thirst": "🩸",
        "rupture": "🩸", "goo": "💦", "spray": "💥", "back": "🛡️",
        "warpath": "🏃", "stomp": "🦶", "edge": "⚔️", "retaliate": "🛡️",
        "stampede": "🐎", "crystal": "🧊", "frostbite": "❄️", "arcane": "🪄",
        "freezing": "❄️", "frost": "❄️", "gust": "💨", "multishot": "🏹",
        "marksman": "🎯", "chain": "⛓️", "fist": "👊", "guard": "🛡️",
        "fireremnant": "🔥", "malefice": "🔮", "conversion": "🌑",
        "midnight": "🌑", "blackhole": "🌌", "acorn": "🌰", "bush": "🐿️",
        "scurry": "🏃", "sharp": "🎯", "inner_fire": "🔥", "burning_spears": "🔥",
        "berserkers_blood": "🩸", "life_break": "💔", "quas": "🧊", "wex": "💨",
        "exort": "🔥", "invoke": "🪄", "blade_fury": "🌪️", "healing_ward": "💚",
        "blade_dance": "🗡️", "omnislash": "🗡️", "odds": "🛡️", "press": "💚",
        "moment": "⚔️", "duel": "⚔️", "earth": "🌎", "edict": "💥", "storm": "⚡",
        "nova": "☄️", "lifestealer_rage": "🩸", "wounds": "🩸", "ghoul": "🧟",
        "infest": "🦠", "dragon": "🔥", "array": "⚡", "soul": "🔥", "laguna": "⚡",
        "dispose": "🤾", "rebound": "🤸", "sidekick": "🤜", "unleash": "👊",
        "spear": "🔱", "rebuke": "🛡️", "bulwark": "🛡️", "arena": "🏟️",
        "boundless": "🌳", "tree": "🌳", "mastery": "👊", "command": "👑",
        "wave": "🌊", "adaptive": "🔀", "attribute": "💪", "morph": "💧",
        "dead": "👻", "calling": "👻", "gun": "🔫", "veil": "👻", "sprout": "🌲",
        "teleport": " teleport", "nature_call": "🌳", "nature_wrath": "🌲",
        "fireblast": "🔥", "ignite": "🔥", "bloodlust": "🩸", "multicast": "💥",
        "buckle": "🛡️", "shield": "🛡️", "lucky": "🎲", "rolling": "🎳",
        "stifling_dagger": "🔪", "phantom_strike": "👻", "blur": "💨",
        "coup_de_grace": "🔪", "onslaught": "🐾", "trample": "🐾", "uproar": "🔊",
        "pulverize": "💥", "orb": "🔮", "rift": "🌌", "shift": "💨", "coil": "🌌",
        "hook": "⛓️", "rot": "🤢", "flesh": "💪", "dismember": "🔪", "dagger": "🔪",
        "blink": "⚡", "scream": "🗣️", "sonic": "💥", "plasma": "⚡", "link": "⛓️",
        "current": "🌊", "eye": "👁️", "burrow": " burrow", "sand": "⏳",
        "stinger": "🦂", "epicenter": "💥", "shadowraze": "💥", "frenzy": "👻",
        "dark_lord": "💀", "requiem": "💀", "arcane_bolt": "🔮", "concussive": "💥",
        "seal": "📜", "flare": " flare", "pact": "👻", "pounce": "🐾", "essence": "👻",
        "dance": "🕺", "scatter": "🔫", "cookie": "🍪", "shredder": "⚙️",
        "kisses": "💋", "shrapnel": "💣", "headshot": "🎯", "aim": "🎯",
        "assassinate": "🔪", "hammer": "🔨", "cleave": "🪓", "cry": "🗣️", "god": "⚔️",
        "refraction": "🪄", "meld": "🪞", "psiblades": "🗡️", "psionic": "💥",
        "reflection": "🪞", "illusion": "👻", "meta": "👹", "sunder": "💔",
        "laser": "💥", "march": "🤖", "matrix": "🛡️", "rearm": "🔄", "rage": "👹",
        "axes": "🪓", "fervor": "🔥", "trance": "🕺", "remnant": "🔮", "astral": "👻",
        "pulse": "💥", "step": "👟", "blast": "💥", "vampiric": "🩸",
        "strike": "⚔️", "reincarnation": "💀", "arc": "⚡", "bolt": "⚡", "jump": "⚡",
        "wrath": "⛈️"
    }

    for hero in heroes:
        hero_name = hero.get("userFriendlyName", "Неизвестный герой")
        text_content += f"\n*{escape_markdown('Изменения для ')}{escape_markdown(hero_name)}*\n"
        
        # Обработка Upgrades
        upgrades = hero.get("upgrades", [])
        for upgrade in upgrades:
            item_type = upgrade.get("type", "").lower()
            ru_rows = upgrade.get("ruRows")
            change_type = upgrade.get("changeType", "").lower()
            
            if ru_rows:
                item_emoji = EMOJI_MAP.get(item_type, "✨")
                change_emoji = EMOJI_MAP.get(change_type, "")
                name = RU_NAMES.get(item_type, "")
                
                text_content += f"\n{item_emoji} {escape_markdown(name)} {item_emoji}\n"
                
                for line in ru_rows.replace("\r\n", "\n").split('\n'):
                    if line.strip():
                        text_content += f"  {change_emoji} {escape_markdown(line.strip())}\n"

        # Обработка Talents
        talents = hero.get("talents", [])
        for talent in talents:
            talent_name = talent.get("name", "")
            
            if talent_name == "hero_talent":
                name = RU_NAMES.get("hero_talent")
                emoji = EMOJI_MAP.get("hero_talent")
                text_content += f"\n{emoji} *{escape_markdown(name)}* {emoji}\n"
            else:
                skill_emoji = SKILL_EMOJI_MAP.get(talent_name.lower(), "✨")
                text_content += f"\n{skill_emoji} *{escape_markdown(talent_name.capitalize())}* {skill_emoji}\n"
            
            for color_key in ["orange", "purple", "blue", "ability"]:
                ru_rows = talent.get(f"{color_key}RuRows")
                if ru_rows:
                    formatted_rows = ru_rows.replace("\r\n", "\n").strip()
                    emoji = EMOJI_MAP.get(color_key, "")
                    name = RU_NAMES.get(color_key, "")
                    change_type = talent.get("changeType", "").lower()
                    change_emoji = EMOJI_MAP.get(change_type, "🟡")

                    if name:
                        text_content += f" {emoji} *{escape_markdown(name)}* {emoji}\n"
                    
                    for line in formatted_rows.split('\n'):
                        if line.strip():
                            text_content += f"  {change_emoji} {escape_markdown(line.strip())}\n"
    
    text_to_send = f"*{escape_markdown(title)}*\n\n{text_content}"
    
    if len(text_to_send) > 4096:
        text_to_send = text_to_send[:4000] + "\n\n_(текст обрезан)_"
    
    await update.message.reply_text(text_to_send, parse_mode='MarkdownV2')

    kb = [[
        InlineKeyboardButton("Источник", url=update_url),
        InlineKeyboardButton("Все обновления", url=urljoin(BASE_URL, "/updates"))
    ]]
    await update.message.reply_text("Смотреть на сайте:", reply_markup=InlineKeyboardMarkup(kb))

async def handle_heroes_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_user_message(user, "Герои")
    
    keyboard = [
        [InlineKeyboardButton("Strength", callback_data="attribute_Strength")],
        [InlineKeyboardButton("Agility", callback_data="attribute_Agility")],
        [InlineKeyboardButton("Intellect", callback_data="attribute_Intellect")],
        [InlineKeyboardButton("Universal", callback_data="attribute_All")],
    ]
    
    markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите атрибут героя:", reply_markup=markup)

async def handle_attribute_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    attribute = query.data.split("_")[1]
    context.user_data['selected_attribute'] = attribute
    
    heroes_data = await fetch_json(API_HEROES_URL)
    if not heroes_data:
        await query.message.reply_text("Не удалось получить список героев.")
        return
        
    heroes = heroes_data.get("data", {}).get("heroes", [])
    
    filtered_heroes = [h for h in heroes if h.get("attribute") == attribute or attribute == "All"]
    
    keyboard = []
    row = []
    for hero in sorted(filtered_heroes, key=lambda x: x.get("userFriendlyName")):
        hero_id = hero.get("heroId")
        name = hero.get("userFriendlyName")
        row.append(InlineKeyboardButton(name, callback_data=f"hero_{hero_id}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("Назад", callback_data="back_to_attributes")])
    markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text="Выберите героя:",
        reply_markup=markup
    )

async def handle_hero_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    hero_id = query.data.split("_")[1]
    
    hero_data = await fetch_json(f"{API_HEROES_URL}{hero_id}")
    if not hero_data:
        await query.edit_message_text("Не удалось получить данные о герое. Попробуйте позже.")
        return

    data = hero_data.get("data")
    if not data:
        await query.edit_message_text("Не удалось получить данные о герое.")
        return

    hero_name = data.get("userFriendlyName", "Неизвестный герой")
    hero_lore = data.get("lore", "Описания нет")
    hero_attribute = data.get("attribute", "Неизвестно")
    hero_icon_url = data.get("icon", "")
    
    message_text = (
        f"*{escape_markdown(hero_name)}*\n\n"
        f"*{escape_markdown('Атрибут')}:* {escape_markdown(hero_attribute)}\n\n"
        f"*{escape_markdown('История')}:* {escape_markdown(hero_lore)}"
    )

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(hero_icon_url) as resp:
                if resp.status == 200:
                    image_data = await resp.read()
                    await context.bot.send_photo(
                        chat_id=query.message.chat_id,
                        photo=BytesIO(image_data),
                        caption=message_text,
                        parse_mode='MarkdownV2'
                    )
                else:
                    await query.edit_message_text(
                        text=message_text,
                        parse_mode='MarkdownV2'
                    )
    except Exception as e:
        logger.error(f"Failed to send photo: {e}")
        await query.edit_message_text(
            text=message_text,
            parse_mode='MarkdownV2'
        )
    
    keyboard = [
        [InlineKeyboardButton("Назад", callback_data=f"back_to_heroes_{context.user_data.get('selected_attribute')}")],
    ]
    markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text("Что еще?", reply_markup=markup)

async def handle_back_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "back_to_attributes":
        await handle_heroes_button(update, context)
    else:
        attribute = query.data.split("_")[3]
        query.data = f"attribute_{attribute}"
        await handle_attribute_selection(update, context)

async def handle_unknown_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_user_message(update.effective_user, update.message.text)
    await update.message.reply_text("Простите, я не понял эту команду. Пожалуйста, используйте кнопки.")

def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Regex(r'^Обновления$'), handle_updates_button))
    application.add_handler(MessageHandler(filters.Regex(r'^Герои$'), handle_heroes_button))
    
    application.add_handler(CallbackQueryHandler(handle_attribute_selection, pattern=r'^attribute_'))
    application.add_handler(CallbackQueryHandler(handle_hero_selection, pattern=r'^hero_'))
    application.add_handler(CallbackQueryHandler(handle_back_buttons, pattern=r'^back_'))
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unknown_message))

    # Для Railway
    # PORT = int(os.environ.get('PORT', '8443'))
    # application.run_webhook(
    #     listen="0.0.0.0",
    #     port=PORT,
    #     url_path=TOKEN,
    #     webhook_url="https://<YOUR-RAILWAY-APP-NAME>.up.railway.app/" + TOKEN
    # )

    # Для локального запуска
    application.run_polling()

if __name__ == "__main__":
    main()
