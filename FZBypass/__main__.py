from FZBypass import Bypass, LOGGER, Config
from wzgram import idle
from wzgram.filters import command, user
from os import path as ospath, execl, remove
from asyncio import create_subprocess_exec, run
from sys import executable
from hashlib import md5
from glob import glob


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


async def main():
    # Only wipe session files when credentials have actually changed
    if _credentials_changed():
        for f in glob("*.session") + glob("*.session-journal"):
            try:
                remove(f)
                LOGGER.info("Credentials changed — removed stale session: %s", f)
            except Exception:
                pass
    await Bypass.start()
    LOGGER.info("FZ Bot Started!")
    await notify_restart()
    await idle()
    await Bypass.stop()


run(main())
