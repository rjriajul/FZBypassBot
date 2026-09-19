from FZBypass import Bypass, LOGGER, Config, conf
from FZBypass.core.commands import BotCommands
from wzgram import idle
from wzgram.filters import command, user
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from os import path as ospath, execl, remove as _remove
from glob import glob as _glob
from asyncio import create_subprocess_exec
from sys import executable
from threading import Thread


def _cleanup_session_files():
    """Remove stale SQLite WAL/lock files left by a previous unclean shutdown."""
    for pattern in ("*.session-shm", "*.session-wal", "*.session.lock"):
        for f in _glob(pattern):
            try:
                _remove(f)
                LOGGER.info(f"Removed stale session file: {f}")
            except OSError:
                pass


class Health(BaseHTTPRequestHandler):
    def _head(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()

    def do_HEAD(self):
        self._head()

    def do_GET(self):
        self._head()
        self.wfile.write(b"FZ Bypass Bot is alive")

    def log_message(self, *args):
        pass


def serve_health():
    port = int(conf("PORT", 8080))
    LOGGER.info(f"Health server listening on port {port}")
    ThreadingHTTPServer(("0.0.0.0", port), Health).serve_forever()


@Bypass.on_message(command(BotCommands.RestartCommand) & user(Config.OWNER_ID))
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
        finally:
            try:
                from os import remove as _rm
                _rm(".restartmsg")
            except OSError:
                pass


async def main():
    _cleanup_session_files()
    Thread(target=serve_health, daemon=True).start()
    await Bypass.start()
    LOGGER.info("FZ Bot Started!")
    await notify_restart()
    await idle()
    await Bypass.stop()


Bypass.loop.run_until_complete(main())
