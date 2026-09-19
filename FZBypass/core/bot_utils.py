from wzgram.filters import create
from wzgram.enums import MessageEntityType
from re import search, match, escape
from requests import get as rget
from urllib.parse import urlparse, parse_qs
from FZBypass import Config
from FZBypass.core.commands import BotCommands

BYPASS_CMDS = "|".join(escape(c) for c in BotCommands.BypassCommand)
EXEC_CMDS = "|".join(escape(c) for c in BotCommands.ExecCommands)


async def auth_topic(_, __, message):
    for chat in Config.AUTH_CHATS:
        if ":" in chat:
            chat_id, topic_id = chat.split(":")
            if (
                int(chat_id) == message.chat.id
                and message.is_topic_message
                and message.message_thread_id == int(topic_id)
            ):
                return True
        elif int(chat) == message.chat.id:
            return True
    return False


AuthChatsTopics = create(auth_topic)


async def auth_channel(_, __, message):
    """Filter for channel posts in AUTH_CHANNELS."""
    from wzgram.enums import ChatType
    if message.chat.type != ChatType.CHANNEL:
        return False
    return str(message.chat.id) in Config.AUTH_CHANNELS


AuthChannels = create(auth_channel)


async def auto_bypass(_, c, message):
    if (
        Config.AUTO_BYPASS
        and message.entities
        and not match(rf"^\/({EXEC_CMDS})($| )", message.text)
        and any(
            enty.type in [MessageEntityType.TEXT_LINK, MessageEntityType.URL]
            for enty in message.entities
        )
    ):
        return True
    elif (
        not Config.AUTO_BYPASS
        and (txt := message.text)
        and match(rf"^\/({BYPASS_CMDS})(@{c.me.username})?($| )", txt)
        and not match(rf"^\/({EXEC_CMDS})($| )", txt)
    ):
        return True
    return False


BypassFilter = create(auto_bypass)


def get_gdriveid(link):
    if "folders" in link or "file" in link:
        res = search(
            r"https:\/\/drive\.google\.com\/(?:drive(.*?)\/folders\/|file(.*?)?\/d\/)([-\w]+)",
            link,
        )
        return res.group(3)
    parsed = urlparse(link)
    return parse_qs(parsed.query)["id"][0]


def get_dl(link, direct_mode=False):
    if direct_mode and not Config.DIRECT_INDEX:
        return "No Direct Index Added !"
    try:
        return rget(
            f"{Config.DIRECT_INDEX}/generate.aspx?id={get_gdriveid(link)}"
        ).json()["link"]
    except:
        return f"{Config.DIRECT_INDEX}/direct.aspx?id={get_gdriveid(link)}"


def convert_time(seconds):
    mseconds = seconds * 1000
    periods = [("d", 86400000), ("h", 3600000), ("m", 60000), ("s", 1000), ("ms", 1)]
    result = ""
    for period_name, period_seconds in periods:
        if mseconds >= period_seconds:
            period_value, mseconds = divmod(mseconds, period_seconds)
            result += f"{int(period_value)}{period_name}"
    if result == "":
        return "0ms"
    return result


SIZE_UNITS = ["B", "KB", "MB", "GB", "TB", "PB"]


def get_readable_size(size):
    if not size:
        return "0B"
    i = 0
    while size >= 1024 and i < len(SIZE_UNITS) - 1:
        size /= 1024
        i += 1
    return f"{size:.2f}{SIZE_UNITS[i]}"


def progress_bar(percent, slots=12):
    percent = min(max(float(percent or 0), 0), 100)
    filled = int(percent / 100 * slots)
    return f"[{'■' * filled}{'□' * (slots - filled)}]"
