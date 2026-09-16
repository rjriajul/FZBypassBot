from FZBypass import Bypass, LOGGER, Config
from wzgram import idle
from wzgram.filters import command, user
from wzgram.errors import FloodWait
from os import path as ospath, execl, remove, getenv
from asyncio import create_subprocess_exec, run
from sys import executable
from hashlib import md5
from glob import glob
from threading import Thread
from flask import Flask


# ── Flask health server ────────────────────────────────────────────────────

_app = Flask(__name__)


@_app.get("/")
def _home():
    return "FZ Bypass Bot is running", 200


@_app.get("/health")
def _health():
    return {"ok": True, "service": "fz-bypass-bot"}, 200


def _start_health_server():
    port = int(getenv("PORT", "10000"))
    _app.run(host="0.0.0.0", port=port, use_reloader=False)


# ── Session management ─────────────────────────────────────────────────────

def _credentials_changed() -> bool:
    """Returns True if bot credentials have changed since last session was created."""
    token_hash = md5(f"{Config.BOT_TOKEN}{Config.API_ID}{Config.API_HASH}".encode()).hexdigest()
    hash_file = ".session_creds_hash"
    if ospath.exists(hash_file):
        with open(hash_file) as f:
            if f.read().strip() == token_hash:
                return False
    with open(hash_file, "w") as f:
        f.write(token_hash)
    return True


# ── Bot commands ───────────────────────────────────────────────────────────

@Bypass.on_message(command("restart") & user(Config.OWNER_ID))
async def restart(client, message):
    restart_message = await message.reply("<i>Restarting...</i>")
    await (await create_subprocess_exec("python3", "update.py")).wait()
    with open(".restartmsg", "w") as f:
        f.write(f"{restart_message.chat.id}\n{restart_message.id}\n")
    try:
        execl(executable, executable, "-m", "FZBypass")
    except Exception:
        execl(executable, executable, "-m", "FZBypassBot/FZBypass")


async def notify_restart():
    if ospath.isfile(".restartmsg"):
        with open(".restartmsg") as f:
            chat_id, msg_id = map(int, f)
        try:
            await Bypass.edit_message_text(
                chat_id=chat_id, message_id=msg_id, text="<i>Restarted !</i>"
            )
        except Exception as e:
            LOGGER.error(e)


# ── Main ───────────────────────────────────────────────────────────────────

async def main():
    # Wipe stale session files only when credentials change
    if _credentials_changed():
        for f in glob("*.session") + glob("*.session-journal"):
            try:
                remove(f)
                LOGGER.info("Credentials changed — removed stale session: %s", f)
            except Exception:
                pass

    # FloodWait retry loop — keeps the health server alive while waiting
    while True:
        try:
            await Bypass.start()
            break
        except FloodWait as exc:
            wait = max(int(getattr(exc, "value", 60)), 60)
            LOGGER.error(
                "Telegram FloodWait during startup — retrying in %s seconds.", wait
            )
            from asyncio import sleep as asleep
            await asleep(wait)

    LOGGER.info("FZ Bot Started!")
    await notify_restart()
    await idle()
    await Bypass.stop()


# Start health server in background then run the bot
Thread(target=_start_health_server, daemon=True).start()
run(main())
