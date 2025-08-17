import logging
import os
import re
import asyncio
import aiohttp
from urllib.parse import urljoin
from datetime import datetime
from collections import deque

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
    ContextTypes,
    filters,
    CallbackQueryHandler,
    ConversationHandler,
)
from telegram.error import Conflict

# ---------- НАСТРОЙКИ ----------
TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID"))
USER_LOG_FILE = "user_messages.txt"
BASE_URL = "https://dota1x6.com"
API_UPDATES_URL = "https://stats.dota1x6.com/api/v2/updates/?page=1&count=20"
API_HEROES_URL = "https://stats.dota1x6.com/api/v2/heroes/"
API_LEADERBOARD_URL = "https://stats.dota1x6.com/api/v2/leaderboard/"
CDN_HEROES_INFO_URL = "https://cdn.dota1x6.com/shared/"
API_PLAYERS_URL = "https://stats.dota1x6.com/api/v2/players/"
LEADERBOARD_PAGE_SIZE = 50

# ---------- СОСТОЯНИЯ ДЛЯ CONVERSATIONHANDLER ----------
GET_DOTA_ID = 1

# ---------- ЛОГИ ----------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------- УТИЛИТЫ ----------
if not os.path.exists(USER_LOG_FILE):
    open(USER_LOG_FILE, "w", encoding="utf-8").close()

RECENT_MESSAGES = deque(maxlen=3000)

def log_user_message(user, text):
    try:
        log_line = (
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | ID:{getattr(user, 'id', None)} | "
            f"Имя:{getattr(user, 'first_name', None)} | "
            f"Username:@{getattr(user, 'username', None)} | {text}\n"
        )
        with open(USER_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_line)
        RECENT_MESSAGES.append(log_line)
    except Exception:
        logger.exception("Не удалось записать лог пользователя")

SKILL_EMOJI_MAP = {
    "Spear of Mars": "🔱", "God's Rebuke": "⚔️", "Bulwark": "🛡️", "Arena of Blood": "🏟️",
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
    "wrath": "⛈️",
    "movespeed": "🥾"
}
EMOJI_MAP = {
    "purple": "🟪", "blue": "🟦", "orange": "🟧", "scepter": "🔮",
    "innate": "🔥", "shard": "🔷", "up": "🟢", "down": "🔴",
    "change": "🟡", "hero_talent": "🤓",
    "Aghanim Scepter": "🔮 Aghanim Scepter",
    "Aghanim Shard": "🔷 Aghanim Shard",
    "online": "🟩",
    "offline": "🟥"
}
COMBINED_EMOJI_MAP = {**SKILL_EMOJI_MAP, **EMOJI_MAP}

# Словарь для маппинга urlName на имя файла на CDN
CDN_HERO_NAME_MAPPING = {
    'antimage': 'antimage',
    'invoker': 'invoker',
    'natures-prophet': 'furion',
    'shadow-fiend': 'nevermore',
    # Добавьте другие исключения, если они будут возникать
}

def escape_markdown_v2(text):
    if not isinstance(text, str):
        return ""
    
    escape_chars = r"[_*[\]()~`>#+\-=|{}.!]"
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

def format_text_from_html(text):
    if not isinstance(text, str):
        return ""

    formatted_text = re.sub(r'<br\s*?/><br\s*?>|<br\s*?><br\s*?>|<br><br>', '\n\n', text, flags=re.IGNORECASE)
    formatted_text = re.sub(r'<br\s*?/>|<br>', '\n', formatted_text, flags=re.IGNORECASE)
    formatted_text = re.sub(r'<[^>]+>', '', formatted_text)
    formatted_text = re.sub(r'([а-яё])([А-ЯЁ])', r'\1 \2', formatted_text)
    
    return formatted_text

def format_text_with_emojis(text):
    formatted_text = format_text_from_html(text)
    
    sorted_keys = sorted(COMBINED_EMOJI_MAP.keys(), key=len, reverse=True)
    for key in sorted_keys:
        emoji = COMBINED_EMOJI_MAP[key]
        if key.lower() == 'scepter' or key.lower() == 'shard':
            continue
            
        pattern = r'\b' + re.escape(key) + r'\b'
        formatted_text = re.sub(pattern, f"{emoji} {key}", formatted_text, flags=re.IGNORECASE)
    
    formatted_text = re.sub(
        r'\bAghanim Scepter\b',
        EMOJI_MAP.get("Aghanim Scepter", "🔮 Aghanim Scepter"),
        formatted_text,
        flags=re.IGNORECASE
    )
    formatted_text = re.sub(
        r'\bAghanim Shard\b',
        EMOJI_MAP.get("Aghanim Shard", "🔷 Aghanim Shard"),
        formatted_text,
        flags=re.IGNORECASE
    )
        
    return escape_markdown_v2(formatted_text)


async def send_long_message(context: ContextTypes.DEFAULT_TYPE, chat_id, text, parse_mode='MarkdownV2'):
    max_length = 4096
    
    parts = text.split('\n')
    current_message = ""
    
    for part in parts:
        if len(current_message) + len(part) + 1 < max_length:
            current_message += part + "\n"
        else:
            if current_message:
                await context.bot.send_message(chat_id=chat_id, text=current_message, parse_mode=parse_mode)
                await asyncio.sleep(0.5)
            current_message = part + "\n"
            
    if current_message:
        await context.bot.send_message(chat_id=chat_id, text=current_message, parse_mode=parse_mode)

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
        ["Герои", "Ладдер"]
    ]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Привет! Выберите действие:", reply_markup=markup)

async def start_dota_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_user_message(update.effective_user, "Нажал 'Проверить статистику'")
    await update.message.reply_text("Введите числовой Dota ID:")
    return GET_DOTA_ID

async def get_dota_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dota_id = update.message.text
    log_user_message(update.effective_user, f"Ввел ID: {dota_id}")

    url = f"{API_PLAYERS_URL}?playerId={dota_id}"
    data = await fetch_json(url)

    if not data or not data.get("data"):
        await update.message.reply_text("Игрок с таким ID не найден или произошла ошибка API.")
        return ConversationHandler.END

    player_data = data.get("data")
    match_count = player_data.get("matchCount", "неизвестно")
    avg_place = round(player_data.get("avgPlace", 0), 2)
    first_places = player_data.get("firstPlaces", "неизвестно")
    rating = player_data.get("rating", "неизвестно")
    
    # ИСПРАВЛЕНО: Проверяем, что social_data - словарь, иначе используем пустой.
    social_data = player_data.get("social", {})
    if social_data is None:
        social_data = {}
    
    youtube_url = social_data.get("youtube")
    twitch_url = social_data.get("twitch")
    is_youtube_live = social_data.get("isYoutubeLive")
    is_twitch_live = social_data.get("isTwitchLive")

    msg = f"*Статистика игрока*\n"
    msg += f"Всего игр: {match_count}\n"
    msg += f"Среднее место: {avg_place}\n"
    msg += f"Первых мест: {first_places}\n"
    msg += f"Рейтинг: {rating}\n\n"

    msg_social = ""
    if youtube_url:
        yt_status = EMOJI_MAP.get("online") if is_youtube_live else EMOJI_MAP.get("offline")
        msg_social += f"YouTube: {yt_status} [{escape_markdown_v2('Канал')}]({escape_markdown_v2(youtube_url)})\n"
    if twitch_url:
        twitch_status = EMOJI_MAP.get("online") if is_twitch_live else EMOJI_MAP.get("offline")
        msg_social += f"Twitch: {twitch_status} [{escape_markdown_v2('Канал')}]({escape_markdown_v2(twitch_url)})"
        
    final_msg = escape_markdown_v2(msg)
    if msg_social:
        final_msg += f"*{escape_markdown_v2('Социальные сети')}*\n{msg_social}"

    await update.message.reply_text(final_msg, parse_mode='MarkdownV2')

    player_url = f"{BASE_URL}/players/{dota_id}"
    inline_keyboard = [
        [InlineKeyboardButton("Посмотреть историю игр", web_app=WebAppInfo(url=player_url))]
    ]
    await update.message.reply_text(
        "Вы можете посмотреть историю игр:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard)
    )

    return ConversationHandler.END

async def cancel_dota_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Действие отменено.")
    return ConversationHandler.END

async def handle_updates_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_user_message(user, "Обновления")
    await update.message.reply_text("🔎 Ищу последнее обновление...")

    latest_update_info = await fetch_json(API_UPDATES_URL)
    if not latest_update_info or not latest_update_info.get("data", {}).get("values"):
        await update.message.reply_text("Не удалось получить информацию об обновлениях с API. Попробуйте позже.")
        return ConversationHandler.END

    update_url_slug = latest_update_info["data"]["values"][0].get("url")
    if not update_url_slug:
        await update.message.reply_text("В полученных данных нет ссылки на обновление. Попробуйте позже.")
        return ConversationHandler.END

    update_url = urljoin(BASE_URL, f"/updates/{update_url_slug}")
    api_update_url = f"https://stats.dota1x6.com/api/v2/updates/{update_url_slug}"
    
    api_data = await fetch_json(api_update_url)
    if not api_data or not api_data.get("data"):
        await update.message.reply_text("Произошла ошибка при получении данных об обновлении. Попробуйте позже.")
        return ConversationHandler.END

    data = api_data.get("data")
    title = data.get("ruName", "Без названия")
    text_content = ""
    heroes = data.get("heroes", [])

    RU_NAMES = {
        "purple": "Эпический талант", "blue": "Редкий талант", "orange": "Легендарный талант",
        "scepter": "Аганим", "innate": "Врожденный талант", "shard": "Аганим шард",
        "hero_talent": "Таланты героя", "ability": "Изменения способностей",
    }
    
    for hero in heroes:
        hero_name = hero.get("userFriendlyName", "Неизвестный герой")
        if text_content:
            text_content += "\n\n"
        text_content += f"*{escape_markdown_v2('Изменения для ')}{escape_markdown_v2(hero_name)}*\n"
        
        upgrades = hero.get("upgrades", [])
        for upgrade in upgrades:
            item_type = upgrade.get("type", "").lower()
            ru_rows = upgrade.get("ruRows")
            change_type = upgrade.get("changeType", "").lower()
            
            if ru_rows:
                if text_content.strip().endswith((']')):
                    text_content += "\n"
                item_emoji = EMOJI_MAP.get(item_type, "✨")
                change_emoji = EMOJI_MAP.get(change_type, "")
                name = RU_NAMES.get(item_type, "")
                
                text_content += f"\n{item_emoji} {escape_markdown_v2(name)} {item_emoji}\n"
                
                for line in ru_rows.replace("\r\n", "\n").split('\n'):
                    if line.strip():
                        formatted_line = format_text_with_emojis(line.strip())
                        text_content += f"  {change_emoji} {formatted_line}\n"

        talents = hero.get("talents", [])
        for talent in talents:
            talent_name = talent.get("name", "")
            
            if talent_name == "hero_talent":
                if text_content.strip().endswith((']')):
                    text_content += "\n"
                name = RU_NAMES.get("hero_talent")
                emoji = EMOJI_MAP.get("hero_talent")
                text_content += f"\n{emoji} *{escape_markdown_v2(name)}* {emoji}\n"
            else:
                if text_content.strip().endswith((']')):
                    text_content += "\n"
                skill_emoji = SKILL_EMOJI_MAP.get(talent_name.lower(), "✨")
                text_content += f"\n{skill_emoji} *{escape_markdown_v2(talent_name.capitalize())}* {skill_emoji}\n"
            
            for color_key in ["orange", "purple", "blue", "ability"]:
                ru_rows = talent.get(f"{color_key}RuRows")
                if ru_rows:
                    formatted_rows = ru_rows.replace("\r\n", "\n").strip()
                    emoji = EMOJI_MAP.get(color_key, "")
                    name = RU_NAMES.get(color_key, "")
                    change_type = talent.get("changeType", "").lower()
                    change_emoji = EMOJI_MAP.get(change_type, "🟡")

                    if name:
                        text_content += f" {emoji} *{escape_markdown_v2(name)}* {emoji}\n"
                    
                    for line in formatted_rows.split('\n'):
                        if line.strip():
                            formatted_line = format_text_with_emojis(line.strip())
                            text_content += f"  {change_emoji} {formatted_line}\n"
    
    text_to_send = f"*{escape_markdown_v2(title)}*\n\n{text_content}"
    
    await send_long_message(context, update.effective_chat.id, text_to_send)

    kb = [[
        InlineKeyboardButton("Источник", url=update_url),
        InlineKeyboardButton("Все обновления", url=urljoin(BASE_URL, "/updates"))
    ]]
    await update.message.reply_text("Смотреть на сайте:", reply_markup=InlineKeyboardMarkup(kb))
    return ConversationHandler.END

async def handle_leaderboard_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_user_message(user, "Ладдер")

    sent_message = await update.message.reply_text("🏆 Загружаю ладдер...")
    
    leaderboard_data = await fetch_json(API_LEADERBOARD_URL)
    
    if not leaderboard_data or not leaderboard_data.get("data"):
        await sent_message.edit_text("Не удалось получить данные ладдера. Попробуйте позже.")
        return
        
    players = leaderboard_data.get("data")
    players_to_display = players[:50]
    
    message_text = f"*{escape_markdown_v2('ТОП-50 ИГРОКОВ LADDER.')}*\n\n"
    
    for player in players_to_display:
        place = player.get("place")
        nickname = player.get("nickname")
        rating = player.get("rating")
        match_count = player.get("matchCount")
        
        # ИСПРАВЛЕНО: Проверяем, что social_data - словарь, иначе используем пустой.
        social_data = player.get("social", {})
        if social_data is None:
            social_data = {}
        
        youtube_url = social_data.get("youtube")
        twitch_url = social_data.get("twitch")
        is_youtube_live = social_data.get("isYoutubeLive")
        is_twitch_live = social_data.get("isTwitchLive")

        player_info = (
            f"*{place}\\. {escape_markdown_v2(nickname)}*\n"
            f"Рейтинг: {rating}\n"
            f"Игр: {match_count}\n"
        )
        
        if youtube_url or twitch_url:
            player_info += f"Социальные сети: "
            social_links = []
            if youtube_url:
                yt_status = EMOJI_MAP.get("online") if is_youtube_live else EMOJI_MAP.get("offline")
                social_links.append(f"{yt_status} [{escape_markdown_v2('Ютуб')}]({escape_markdown_v2(youtube_url)})")
            if twitch_url:
                twitch_status = EMOJI_MAP.get("online") if is_twitch_live else EMOJI_MAP.get("offline")
                social_links.append(f"{twitch_status} [{escape_markdown_v2('Твич')}]({escape_markdown_v2(twitch_url)})")
            player_info += " | ".join(social_links)
            player_info += "\n"

        message_text += player_info + "\n"
        
    keyboard = [
        [InlineKeyboardButton("Весь ладдер на сайте", web_app=WebAppInfo(url=f"{BASE_URL}/leaderboard"))]
    ]
    
    markup = InlineKeyboardMarkup(keyboard)
    
    await sent_message.edit_text(message_text, reply_markup=markup, parse_mode='MarkdownV2')


async def handle_heroes_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_user_message(user, "Герои")

    keyboard = [
        [InlineKeyboardButton("Strength", callback_data="attribute_Strength")],
        [InlineKeyboardButton("Agility", callback_data="attribute_Agility")],
        [InlineKeyboardButton("Intellect", callback_data="attribute_Intellect")],
        [InlineKeyboardButton("Universal", callback_data="attribute_All")],
        [InlineKeyboardButton("Посмотреть на сайте", web_app=WebAppInfo(url=f"{BASE_URL}/heroes"))]
    ]
    
    markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text("Выберите атрибут героя:", reply_markup=markup)
    elif update.callback_query and update.callback_query.message:
        await update.callback_query.message.edit_text("Выберите атрибут героя:", reply_markup=markup)
    return ConversationHandler.END


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
    
    filtered_heroes = [h for h in heroes if h.get("attribute") == attribute]
    
    if not filtered_heroes:
        await query.edit_message_text(
            text="К сожалению, героев этого атрибута не найдено. Попробуйте выбрать другой.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Назад", callback_data="back_to_attributes")]
            ])
        )
        return

    keyboard = []
    row = []
    for hero in sorted(filtered_heroes, key=lambda x: x.get("userFriendlyName")):
        name = hero.get("userFriendlyName")
        url_name = hero.get("urlName")
        
        if name and url_name:
            row.append(InlineKeyboardButton(name, callback_data=f"hero_name_{url_name}"))
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
    
async def send_hero_details(update: Update, context: ContextTypes.DEFAULT_TYPE, hero_json, hero_name):
    text_parts = []
    
    text_parts.append(f"*{escape_markdown_v2(hero_name)}*\n")
    
    changes = hero_json.get('changes', [])
    upgrades = hero_json.get('upgrades', [])

    if changes:
        text_parts.append(f"*{escape_markdown_v2('Отличия от Dota:')}*")
        for change in changes:
            name = change.get('name')
            description = change.get('description', '')
            
            if name == 'innate':
                text_parts.append("")
                formatted_desc = format_text_with_emojis(description)
                text_parts.append(f"• {EMOJI_MAP.get('innate', '')} *{escape_markdown_v2('Врожденная способность:')}*\n_{formatted_desc}_")
            else:
                text_parts.append("")
                skill_name_lower = name.lower() if name else None
                
                if skill_name_lower in SKILL_EMOJI_MAP:
                    skill_emoji = SKILL_EMOJI_MAP[skill_name_lower]
                elif skill_name_lower in EMOJI_MAP:
                    skill_emoji = EMOJI_MAP[skill_name_lower]
                else:
                    skill_emoji = ""
                
                if name:
                    formatted_name = f"*{escape_markdown_v2(name.capitalize())}*"
                    if skill_emoji:
                        formatted_name = f"{skill_emoji} {formatted_name}"
                    
                    formatted_desc = format_text_with_emojis(description)
                    text_parts.append(f"• {formatted_name}: _{formatted_desc}_")
                else:
                    formatted_desc = format_text_with_emojis(description)
                    text_parts.append(f"• _{formatted_desc}_")
        text_parts.append("")
    
    if upgrades:
        text_parts.append("*Улучшения:*")
        
        grouped_upgrades = {}
        for upgrade in upgrades:
            upgrade_type = upgrade.get('upgradeType', 'unknown')
            if upgrade_type not in grouped_upgrades:
                grouped_upgrades[upgrade_type] = []
            grouped_upgrades[upgrade_type].append(upgrade)
            
        upgrade_order = ['scepter', 'shard']
        
        for upgrade_type in upgrade_order:
            if upgrade_type in grouped_upgrades:
                upgrades_to_print = grouped_upgrades[upgrade_type]
                
                upgrade_title = "Неизвестное улучшение"
                if upgrade_type == 'scepter':
                    upgrade_title = "Аганим"
                elif upgrade_type == 'shard':
                    upgrade_title = "Аганим Шард"
                
                text_parts.append("")
                emoji = EMOJI_MAP.get(upgrade_type, "✨")
                text_parts.append(f"• {emoji} *{escape_markdown_v2(upgrade_title)}:*")
                
                for upgrade in upgrades_to_print:
                    description = format_text_with_emojis(upgrade.get('description', ''))
                    extra_values_text = ""
                    for extra_value_pair in upgrade.get('extraValues', []):
                        key = extra_value_pair[0]
                        value = extra_value_pair[1]
                        extra_values_text += f"_{format_text_with_emojis(key)}: {format_text_with_emojis(value)}_\n"

                    text_parts.append(f"{extra_values_text}{description}")

        text_parts.append("")

    talents_data = {
        'purple': {'title': 'Эпические таланты', 'data': hero_json.get('purpleTalents', {})},
        'blue': {'title': 'Редкие таланты', 'data': hero_json.get('blueTalents', {})},
        'orange': {'title': 'Легендарные таланты', 'data': hero_json.get('orangeTalents', {})},
    }
    
    for color, info in talents_data.items():
        if info['data']:
            text_parts.append(f"*{escape_markdown_v2(info['title'])}:*")
            talent_emoji = EMOJI_MAP.get(color, "✨")
            for skill_key, skill_talents in info['data'].items():
                for talent in skill_talents:
                    description = talent.get('description', '')
                    if description:
                        text_parts.append("")
                        formatted_desc = format_text_with_emojis(description)
                        text_parts.append(f"• {talent_emoji} {formatted_desc}")
            text_parts.append("")

    message_text = "\n".join(text_parts).strip()
    
    if not message_text:
        message_text = "Информация по этому герою не найдена."
    
    await send_long_message(context, update.callback_query.message.chat_id, message_text)


async def handle_hero_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        hero_url_name = query.data.split("_", 2)[2]
        if not hero_url_name:
            await query.message.reply_text("Не удалось получить имя героя. Пожалуйста, попробуйте выбрать героя еще раз.")
            return
    except (IndexError, ValueError):
        await query.message.reply_text("Произошла ошибка при обработке данных. Пожалуйста, сообщите об этом разработчику.")
        return
    
    await query.message.edit_text(f"Загружаю информацию о герое {hero_url_name}...")
    
    hero_api_url_name = CDN_HERO_NAME_MAPPING.get(hero_url_name, hero_url_name.replace('-', '_'))
    full_api_url = f"{CDN_HEROES_INFO_URL}ru_npc_dota_hero_{hero_api_url_name}.json"
    
    hero_json_data = await fetch_json(full_api_url)
    
    if not hero_json_data:
        await query.message.edit_text(f"Не удалось получить данные для героя {hero_url_name}. Попробуйте позже.")
        return
        
    hero_name = hero_json_data.get('userFriendlyName', 'Герой')

    await query.message.delete()
    
    await send_hero_details(update, context, hero_json_data, hero_name)
    
    keyboard = [
        [InlineKeyboardButton("Назад", callback_data="back_to_attributes")],
    ]
    markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=query.message.chat_id, 
        text="Выберите следующий шаг:", 
        reply_markup=markup
    )

async def handle_back_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "back_to_attributes":
        keyboard = [
            [InlineKeyboardButton("Strength", callback_data="attribute_Strength")],
            [InlineKeyboardButton("Agility", callback_data="attribute_Agility")],
            [InlineKeyboardButton("Intellect", callback_data="attribute_Intellect")],
            [InlineKeyboardButton("Universal", callback_data="attribute_All")],
            [InlineKeyboardButton("Посмотреть на сайте", web_app=WebAppInfo(url=f"{BASE_URL}/heroes"))]
        ]
        await update.callback_query.message.edit_text("Выберите атрибут героя:", reply_markup=InlineKeyboardMarkup(keyboard))

async def preview_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("У вас нет прав для выполнения этой команды.")
        return

    if not RECENT_MESSAGES:
        await update.message.reply_text("В памяти нет последних сообщений.")
        return
    
    last_10_messages = list(RECENT_MESSAGES)[-10:]
    log_text = "".join(last_10_messages)
    
    await update.message.reply_text(f"Последние 10 сообщений:\n```\n{log_text}\n```", parse_mode='MarkdownV2')

async def get_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("У вас нет прав для выполнения этой команды.")
        return
        
    if not RECENT_MESSAGES:
        await update.message.reply_text("В памяти нет сообщений.")
        return

    log_text = "".join(list(RECENT_MESSAGES))
    
    await send_long_message(context, update.effective_chat.id, f"Весь лог из памяти:\n```\n{log_text}\n```")

async def handle_unknown_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_user_message(update.effective_user, update.message.text)
    await update.message.reply_text("Простите, я не понял эту команду. Пожалуйста, используйте кнопки.")


def main():
    application = Application.builder().token(TOKEN).build()

    dota_stats_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r'^Проверить статистику$'), start_dota_stats)],
        states={
            GET_DOTA_ID: [MessageHandler(filters.Regex(r'^\d+$'), get_dota_id)]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_dota_stats),
            MessageHandler(filters.Regex(r'^Обновления$'), handle_updates_button),
            MessageHandler(filters.Regex(r'^Герои$'), handle_heroes_button),
            MessageHandler(filters.Regex(r'^Ладдер$'), handle_leaderboard_button),
            MessageHandler(filters.TEXT, cancel_dota_stats)
        ],
        per_user=True,
    )
    application.add_handler(dota_stats_conv_handler)

    application.add_handler(CommandHandler("start", start))
    
    application.add_handler(CommandHandler("previewlog", preview_log))
    application.add_handler(CommandHandler("getlog", get_log))

    application.add_handler(MessageHandler(filters.Regex(r'^Обновления$'), handle_updates_button))
    application.add_handler(MessageHandler(filters.Regex(r'^Герои$'), handle_heroes_button))
    application.add_handler(MessageHandler(filters.Regex(r'^Ладдер$'), handle_leaderboard_button))
    
    application.add_handler(CallbackQueryHandler(handle_attribute_selection, pattern=r'^attribute_'))
    application.add_handler(CallbackQueryHandler(handle_hero_selection, pattern=r'^hero_name_'))
    application.add_handler(CallbackQueryHandler(handle_back_buttons, pattern=r'^back_'))
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unknown_message))

    try:
        application.run_polling()
    except Conflict as e:
        logger.warning(f"Conflict error on startup: {e}. Attempting to recover...")
        try:
            application.updater.bot.delete_webhook()
            application.run_polling()
        except Exception as inner_e:
            logger.error(f"Failed to recover from conflict: {inner_e}")
            
if __name__ == "__main__":
    if not OWNER_ID:
        logger.error("OWNER_ID не установлен в переменных окружения. Пожалуйста, добавьте его.")
        exit(1)
        
    main()
