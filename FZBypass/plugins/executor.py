from os import path as ospath, getcwd, chdir
from traceback import format_exc
from textwrap import indent
from io import StringIO, BytesIO
from re import match
from contextlib import redirect_stdout, suppress
from asyncio.subprocess import PIPE
from asyncio import create_subprocess_shell
from wzgram.filters import command, user
from FZBypass import Config, Bypass, LOGGER


@Bypass.on_message(command("bash") & user(Config.OWNER_ID))
async def bash(_, message):
    msg = await get_result(eval, message)
    if len(str(msg)) > 2000:
        with BytesIO(str.encode(msg)) as out_file:
            out_file.name = "output.txt"
            await message.reply_document(out_file)
    else:
        LOGGER.info(f"OUTPUT: '{msg}'")
        if not msg or msg == "\n":
            msg = "MessageEmpty"
        elif not bool(match(r"<(blockquote|spoiler|b|i|code|s|u|/a)>", msg)):
            msg = f"<blockquote>{msg}</blockquote>"
        await message.reply(msg)


async def get_result(func, message):
    content = message.text.split(maxsplit=1)[-1]
    if not content:
        return ""
    body = (
        "\n".join(content.split("\n")[1:-1])
        if content.startswith("```") and content.endswith("```")
        else content.strip("` \n")
    )
    env = {
        "__builtins__": {
            k: __builtins__[k]
            for k in (
                "print", "len", "range", "str", "int", "float", "list", "dict",
                "set", "tuple", "bool", "type", "repr", "enumerate", "zip",
                "map", "filter", "sorted", "reversed", "any", "all", "sum",
                "min", "max", "abs", "round", "isinstance", "hasattr",
                "getattr", "setattr", "vars", "dir", "hex", "bin", "oct",
                "chr", "ord", "hash", "id", "callable", "iter", "next",
                "open", "Exception", "ValueError", "TypeError", "KeyError",
                "IndexError", "AttributeError", "StopIteration",
            )
            if k in __builtins__
        },
        "bot": Bypass,
        "message": message,
    }

    chdir(getcwd())
    with open(ospath.join(getcwd(), "FZBypass/temp.txt"), "w") as temp:
        temp.write(body)

    stdout = StringIO()
    to_compile = f'async def func():\n{indent(body, "  ")}'

    try:
        exec(to_compile, env)
    except Exception as e:
        return f"{e.__class__.__name__}: {e}"

    func = env["func"]
    try:
        with redirect_stdout(stdout):
            func_return = await func()
    except Exception:
        value = stdout.getvalue()
        return f"{value}{format_exc()}"
    else:
        value = stdout.getvalue()
        result = None
        if func_return is None:
            if value:
                result = f"{value}"
            else:
                with suppress(Exception):
                    result = f"{repr(eval(body, env))}"
        else:
            result = f"{value}{func_return}"
        if result:
            return result


@Bypass.on_message(command("shell") & user(Config.OWNER_ID))
async def shell(_, message):
    cmd = message.text.split(maxsplit=1)
    if len(cmd) == 1:
        await message.reply("No command to execute was given.")
        return
    cmd = cmd[1]
    proc = await create_subprocess_shell(cmd, stdout=PIPE, stderr=PIPE)
    stdout, stderr = await proc.communicate()
    stdout = stdout.decode().strip()
    stderr = stderr.decode().strip()
    reply = ""
    if len(stdout) != 0:
        reply += f"<b>Stdout</b>\n<blockquote>{stdout}</blockquote>\n"
        LOGGER.info(f"Shell - {cmd} - {stdout}")
    if len(stderr) != 0:
        reply += f"<b>Stderr</b>\n<blockquote>{stderr}</blockquote>"
        LOGGER.error(f"Shell - {cmd} - {stderr}")
    if len(reply) > 3000:
        with BytesIO(str.encode(reply)) as out_file:
            out_file.name = "shell_output.txt"
            await message.reply_document(out_file)
    elif len(reply) != 0:
        await message.reply(reply)
    else:
        await message.reply("No Reply")
