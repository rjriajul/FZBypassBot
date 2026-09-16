from os import getenv
from time import time
from dotenv import load_dotenv
from wzgram import Client
from wzgram.enums import ParseMode
from logging import getLogger, FileHandler, StreamHandler, INFO, ERROR, basicConfig
from uvloop import install

install()
basicConfig(
    format="[%(asctime)s] [%(levelname)s] - %(message)s",  #  [%(filename)s:%(lineno)d]
    datefmt="%d-%b-%y %I:%M:%S %p",
    handlers=[FileHandler("log.txt"), StreamHandler()],
    level=INFO,
)

getLogger("pyrogram").setLevel(ERROR)
LOGGER = getLogger(__name__)

load_dotenv("config.env", override=True)
BOT_START = time()


class Config:
    BOT_TOKEN = getenv("BOT_TOKEN", "")
    API_HASH = getenv("API_HASH", "")
    API_ID = getenv("API_ID", "")
    if BOT_TOKEN == "" or API_HASH == "" or API_ID == "":
        LOGGER.critical("Variables Missing. Exiting Now...")
        exit(1)
    AUTO_BYPASS = getenv("AUTO_BYPASS", "False").lower() == "true"
    AUTH_CHATS = getenv("AUTH_CHATS", "").split()
    OWNER_ID = int(getenv("OWNER_ID", 0))
    DIRECT_INDEX = getenv("DIRECT_INDEX", "").rstrip("/")
    LARAVEL_SESSION = getenv("LARAVEL_SESSION", "")
    XSRF_TOKEN = getenv("XSRF_TOKEN", "")
    GDTOT_CRYPT = getenv("GDTOT_CRYPT", "")
    DRIVEFIRE_CRYPT = getenv("DRIVEFIRE_CRYPT", "")
    HUBDRIVE_CRYPT = getenv("HUBDRIVE_CRYPT", "")
    TERA_COOKIE = getenv("TERA_COOKIE", "")
    TERA_API_URL = getenv("TERA_API_URL", "https://terabox-downloader-api-pqxy.onrender.com").rstrip("/")
    KATDRIVE_CRYPT = getenv("KATDRIVE_CRYPT", "")

Bypass = Client(
    "FZ",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    plugins=dict(root="FZBypass/plugins"),
    parse_mode=ParseMode.HTML,
)
