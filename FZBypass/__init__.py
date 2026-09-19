from os import getenv
from time import time
from wzgram import Client
from wzgram.enums import ParseMode
from logging import getLogger, FileHandler, StreamHandler, INFO, ERROR, basicConfig
try:
    from uvloop import install
    install()
except ImportError:
    pass  # uvloop is Linux-only; Windows uses the default asyncio event loop
basicConfig(
    format="[%(asctime)s] [%(levelname)s] - %(message)s",  #  [%(filename)s:%(lineno)d]
    datefmt="%d-%b-%y %I:%M:%S %p",
    handlers=[FileHandler("log.txt"), StreamHandler()],
    level=INFO,
)

getLogger("pyrogram").setLevel(ERROR)
LOGGER = getLogger(__name__)

try:
    import config
except ImportError:
    config = None


def conf(key, default=""):
    return getattr(config, key, None) or getenv(key, default)


BOT_START = time()


class Config:
    BOT_TOKEN = conf("BOT_TOKEN")
    API_HASH = conf("API_HASH")
    API_ID = conf("API_ID")
    OWNER_ID = int(conf("OWNER_ID", 0) or 0)
    if not BOT_TOKEN or not API_HASH or not API_ID or not OWNER_ID:
        LOGGER.critical("Variables Missing. Exiting Now...")
        exit(1)
    CMD_SUFFIX = str(conf("CMD_SUFFIX") or "")
    AUTO_BYPASS = str(conf("AUTO_BYPASS", "False")).lower() == "true"
    _auth = conf("AUTH_CHATS")
    AUTH_CHATS = _auth.split() if isinstance(_auth, str) else [str(c) for c in _auth]
    DIRECT_INDEX = conf("DIRECT_INDEX").rstrip("/")
    LARAVEL_SESSION = conf("LARAVEL_SESSION")
    XSRF_TOKEN = conf("XSRF_TOKEN")
    GDTOT_CRYPT = conf("GDTOT_CRYPT")
    DRIVEFIRE_CRYPT = conf("DRIVEFIRE_CRYPT")
    HUBDRIVE_CRYPT = conf("HUBDRIVE_CRYPT")
    KATDRIVE_CRYPT = conf("KATDRIVE_CRYPT")
    TERA_COOKIE = conf("TERA_COOKIE")
    TERABOX_API_URL = conf("TERABOX_API_URL").rstrip("/")
    _channels = conf("AUTH_CHANNELS")
    AUTH_CHANNELS = _channels.split() if isinstance(_channels, str) and _channels else []


Bypass = Client(
    "FZ",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    plugins=dict(root="FZBypass/handlers"),
    parse_mode=ParseMode.HTML,
)
