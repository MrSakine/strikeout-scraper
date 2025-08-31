import logging
import json
import traceback
from main import fetch_live_matches, load_proxies, SPORTS_MAP
from pyrogram import Client, filters, enums
from uuid import uuid4
from datetime import datetime, timedelta
from pyrogram.types import InlineQueryResultArticle, InputTextMessageContent, InlineQuery, Message

logger = logging.getLogger(__name__)
log_format = (
    "[%(name)s-%(levelname)s] "
    "%(asctime)s - %(message)s"
)

logging.basicConfig(level=logging.DEBUG, format=log_format)

config = json.load(open("config.json", "r", encoding="utf-8"))
API_ID = config["API_ID"]
API_HASH = config["API_HASH"]
BOT_TOKEN = config["BOT_TOKEN"]
ADMIN_ID = config["ADMIN_ID"]

bot = Client("strikeout_bot", api_id=API_ID,
             api_hash=API_HASH, bot_token=BOT_TOKEN)

CACHE = {
    "date": None,
    "data": {}
}

SPORT_ICONS = {
    "soccer": "⚽",
    "basketball": "🏀",
}

ADBLOCK_NOTE = (
    "\n⚠️ Consider using an adblocker for a better experience:\n"
    "- Brave Browser: 🔗 https://brave.com/\n"
    "- AdBlock for Chrome: 🔗 https://chrome.google.com/webstore/detail/adblock-%E2%80%94-block-ads-acros/"
    "gighmmpiobklfepjocnamgkkbiglidom?hl=en-US&utm_source=ext_sidebar"
)

ADBLOCK_NOTE_INLINE = InlineQueryResultArticle(
    id=str(uuid4()),
    title="⚠️ Tip: Use an ad blocker",
    description="Brave Browser, AdBlock for Chrome...",
    input_message_content=InputTextMessageContent(
        "\n⚠️ Consider using an adblocker for a better experience:\n"
        "- Brave Browser: 🔗 https://brave.com/\n"
        "- AdBlock for Chrome: 🔗 https://chrome.google.com/webstore/detail/adblock-%E2%80%94-block-ads-acros/"
        "gighmmpiobklfepjocnamgkkbiglidom?hl=en-US&utm_source=ext_sidebar"
    )
)


def get_cached_matches():
    """Return cached matches, refresh if new day or older than 2h"""
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")

    should_refresh = (
        CACHE["date"] != today or
        CACHE["last_update"] is None or
        (now - CACHE["last_update"]) >= timedelta(hours=2)
    )

    if should_refresh:
        logger.info("Cache is outdated or empty, fetching new matches...")
        CACHE["data"] = {}
        logger.info("Loading proxies...")
        proxies = load_proxies("socks5")
        for sport in SPORTS_MAP:
            _, matches_by_league = fetch_live_matches(
                sport, proxies_list=proxies)
            CACHE["data"][sport] = matches_by_league

        CACHE["date"] = today
        CACHE["last_update"] = now
    else:
        logger.info("Using cached matches (last update: %s)",
                    CACHE["last_update"])

    return CACHE["data"]


@bot.on_inline_query()
async def inline_handler(client: Client, query: InlineQuery):
    """
    Handle inline queries from users.
    """
    try:
        text = query.query.strip().lower()
        results = []
        matches_data = get_cached_matches()

        if not text:
            await query.answer([], switch_pm_text="Type a league name", switch_pm_parameter="start")
            return

        found = False
        for sport, leagues in SPORTS_MAP.items():
            matches_by_league = matches_data.get(sport, {})

            for key, league_name in leagues.items():
                if text in league_name.lower():
                    found = True
                    games = matches_by_league.get(league_name, [])
                    if not games:
                        results.append(
                            InlineQueryResultArticle(
                                id=str(uuid4()),
                                title=f"No matches in {league_name}",
                                input_message_content=InputTextMessageContent(
                                    f"❌ No live matches found for {league_name}"
                                )
                            )
                        )
                    else:
                        for match in games:
                            icon = SPORT_ICONS.get(sport, "📌")
                            results.append(
                                InlineQueryResultArticle(
                                    id=str(uuid4()),
                                    title=f"{match['hour']} {match['teams']}",
                                    description=f"{league_name}",
                                    input_message_content=InputTextMessageContent(
                                        f"📌 {league_name}\n"
                                        f"⏰ {match['hour']}\n"
                                        f"{icon} {match['teams']}\n"
                                        f"🔗 {match['link']}"
                                    )
                                )
                            )
                        results.append(ADBLOCK_NOTE_INLINE)

        if not found:
            results.append(
                InlineQueryResultArticle(
                    id=str(uuid4()),
                    title="League not found",
                    input_message_content=InputTextMessageContent(
                        "❌ League not found")
                )
            )

        await query.answer(results, cache_time=0)
    except Exception as e:
        logger.error("Error occurred while processing inline query: %s", e)
        traceback.print_exc()
        await query.answer([], switch_pm_text="An error occurred", switch_pm_parameter="start")


@bot.on_message(filters.command("matches"))
async def matches_handler(client: Client, message: Message):
    """
    Handle /matches command.
    """
    try:
        query = " ".join(message.command[1:]).lower().strip()
        if not query:
            await message.reply_text("⚠️ Usage: `/matches <league name>`", quote=True, parse_mode=enums.ParseMode.MARKDOWN)
            return

        status_msg = await message.reply_text(f"🔍 Searching live matches for {query}...")
        matches_data = get_cached_matches()
        found = False
        for sport, leagues in SPORTS_MAP.items():
            matches_by_league = matches_data.get(sport, {})

            for key, league_name in leagues.items():
                if query in league_name.lower():
                    found = True
                    games = matches_by_league.get(league_name, [])
                    if not games:
                        await status_msg.edit_text(f"❌ No live matches found for {league_name}")
                    else:
                        text_lines = [f"📌 Live matches - {league_name}:"]
                        for match in games:
                            icon = SPORT_ICONS.get(sport, "📌")
                            text_lines.append(
                                f"⏰ {match['hour']} - {icon} {match['teams']}\n🔗 {match['link']}"
                            )
                        text_lines.append(ADBLOCK_NOTE)
                        await status_msg.edit_text("\n\n".join(text_lines))
        if not found:
            await status_msg.edit_text("❌ League not found")
    except Exception as e:
        logger.error("Error occurred while processing /matches command: %s", e)
        traceback.print_exc()
        if status_msg:
            await status_msg.edit_text("❌ An error occurred while processing your request.")
        else:
            await message.reply_text("❌ An error occurred while processing your request.")


@bot.on_message(filters.command("refresh"))
async def refresh_handler(client: Client, message: Message):
    """
    Handle /refresh command.
    """
    try:
        status_msg = await message.reply_text(f"🔄 Refreshing cache...")
        if message.from_user.id != ADMIN_ID:
            await status_msg.edit_text("⛔ You are not allowed to refresh cache.")
            return
        CACHE["date"] = None  # reset cache
        get_cached_matches()  # force refresh
        await status_msg.edit_text("✅ Cache has been refreshed for today.")
    except Exception as e:
        logger.error("Error occurred while processing /refresh command: %s", e)
        traceback.print_exc()
        await status_msg.edit_text("❌ An error occurred while refreshing the cache.")


# --- /start and /help ---
@bot.on_message(filters.command("start"))
async def start_handler(client: Client, message: Message):
    """
    Handle /start command.
    """
    try:
        await message.reply_text(
            "👋 Welcome to the Strikeout Live Bot!\n\n"
            "Use /help to see how to search for live matches."
        )
    except Exception as e:
        logger.error("Error occurred while processing /start command: %s", e)
        traceback.print_exc()
        await message.reply_text("❌ An error occurred while processing your request.")


@bot.on_message(filters.command("help"))
async def help_handler(client: Client, message: Message):
    """
    Handle /help command.
    """
    try:
        commands_list = []
        for sport, leagues in SPORTS_MAP.items():
            commands_list.append(f"⚽ {sport.capitalize()} leagues:")
            for key, league_name in leagues.items():
                cmd = key.replace("-", "")
                commands_list.append(f"  • /{cmd} → {league_name}")
        commands_list.append("  • /matches <league name> → Search by name")
        commands_list.append("  • /refresh (admin only) → Refresh cache")

        help_text = (
            "📖 **How to use this bot**\n\n"
            "👉 **Inline search**:\n"
            "Type `@YourBotName premier league` in any chat to search live matches.\n\n"
            "👉 **Commands**:\n"
            + "\n".join(commands_list)
            + "\n\nℹ️ **About the bot**: /about\n"
            + "✉️ **Contact the bot owner**: /contact\n"
        )

        await message.reply_text(help_text, disable_web_page_preview=True, parse_mode=enums.ParseMode.MARKDOWN)
    except Exception as e:
        logger.error("Error occurred while processing /help command: %s", e)
        traceback.print_exc()
        await message.reply_text("❌ An error occurred while processing your request.")


@bot.on_message(filters.command("about"))
async def about_handler(client: Client, message: Message) -> None:
    """
    Handle /about command: show info about the bot.
    """
    text = (
        "🤖 **Strikeout Live Bot**\n\n"
        "This bot provides live sports matches from Strikeout.im.\n"
        "Supports soccer and basketball leagues.\n"
        "Matches are cached daily to improve speed.\n\n"
        "Use /help to see all commands."
    )
    await message.reply_text(text, disable_web_page_preview=True, parse_mode=enums.ParseMode.MARKDOWN)


@bot.on_message(filters.command("contact"))
async def contact_handler(client: Client, message: Message) -> None:
    """
    Handle /contact command: show owner's Telegram contact.
    """
    text = (
        "📬 **Contact the bot owner:**\n"
        "Telegram: [@Fly_3r](https://t.me/Fly_3r)"
    )
    await message.reply_text(text, disable_web_page_preview=True, parse_mode=enums.ParseMode.MARKDOWN)


def register_league_commands():
    """
    Dynamically register commands for all leagues in SPORTS_MAP.
    Uses cached matches instead of scraping every time.
    """

    for sport, leagues in SPORTS_MAP.items():
        for key, league_name in leagues.items():
            command = key.replace("-", "")  # e.g. /premierleague

            @bot.on_message(filters.command(command))
            async def league_handler(
                client: Client,
                message: Message,
                sport: str = sport,
                league_name: str = league_name
            ) -> None:
                try:
                    """Handle individual league command using cached matches."""
                    status_msg = await message.reply_text(f"🔍 Searching live matches for {league_name}...")
                    matches_data = get_cached_matches()  # get cached matches
                    matches_by_league = matches_data.get(sport, {})
                    games = matches_by_league.get(league_name, [])
                    if not games:
                        await status_msg.edit_text(f"❌ No live matches found for {league_name}")
                        return
                    text_lines = [f"📌 Live matches - {league_name}:"]
                    for match in games:
                        icon = SPORT_ICONS.get(sport, "📌")
                        text_lines.append(
                            f"⏰ {match['hour']} - {icon} {match['teams']}\n🔗 {match['link']}"
                        )
                    text_lines.append(ADBLOCK_NOTE)
                    await status_msg.edit_text("\n\n".join(text_lines))
                except Exception as e:
                    logger.error(
                        "Error occurred while processing /%s command: %s", command, e)
                    traceback.print_exc()
                    await status_msg.edit_text("❌ An error occurred while processing your request.")


if __name__ == "__main__":
    logger.info("Starting bot...")
    logger.info("Registering league commands...")
    register_league_commands()
    bot.run()
    logger.info("Bot stopped.")
