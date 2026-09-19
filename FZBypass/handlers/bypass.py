from time import time
from asyncio import create_task, gather, sleep as asleep
from urllib.parse import urlparse as _urlparse
from wzgram.filters import user
from wzgram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputTextMessageContent,
)
from wzgram.enums import MessageEntityType
from wzgram.errors import QueryIdInvalid

from FZBypass import Config, Bypass, LOGGER
from FZBypass.bypass.checker import direct_link_checker, is_excep_link
from FZBypass.core.bot_utils import AuthChatsTopics, AuthChannels, convert_time, BypassFilter

# Image/poster CDN domains that appear as decorative TEXT_LINK entities — skip silently
_SKIP_DOMAINS = (
    "mzstatic.com", "media-amazon.com", "images-amazon.com",
    "is1-ssl.mzstatic.com", "m.media-amazon.com",
)


@Bypass.on_message(BypassFilter & (user(Config.OWNER_ID) | AuthChatsTopics))
async def bypass_check(client, message):
    if (reply_to := message.reply_to_message) and (
        reply_to.text is not None or reply_to.caption is not None
    ):
        txt = reply_to.text or reply_to.caption
        entities = reply_to.entities or reply_to.caption_entities
    elif Config.AUTO_BYPASS or len(message.text.split()) > 1:
        txt = message.text
        entities = message.entities
    else:
        return await message.reply("<i>No Link Provided!</i>")

    wait_msg = await message.reply("<i>Bypassing...</i>")
    start = time()

    link, tlinks, no = "", [], 0
    atasks = []
    for enty in entities:
        if enty.type == MessageEntityType.URL:
            link = txt[enty.offset : (enty.offset + enty.length)]
        elif enty.type == MessageEntityType.TEXT_LINK:
            link = enty.url

        if link:
            host = _urlparse(link).hostname or ""
            if not any(s in host for s in _SKIP_DOMAINS):
                no += 1
                tlinks.append(link)
                atasks.append(create_task(direct_link_checker(link)))
            link = ""

    completed_tasks = await gather(*atasks, return_exceptions=True)

    parse_data = []
    for result, link in zip(completed_tasks, tlinks):
        if result is None:
            no -= 1  # skipped silently by checker
            continue
        if isinstance(result, Exception):
            bp_link = f"\n┖ <b>Bypass Error:</b> {result}"
        elif is_excep_link(link):
            bp_link = result
        elif isinstance(result, list):
            bp_link, ui = "", "┖"
            for ind, lplink in reversed(list(enumerate(result, start=1))):
                bp_link = f"\n{ui} <b>{ind}x Bypass Link:</b> {lplink}" + bp_link
                ui = "┠"
        else:
            bp_link = f"\n┖ <b>Bypass Link:</b> {result}"

        if is_excep_link(link):
            parse_data.append(f"{bp_link}\n\n━━━━━━━✦✗✦━━━━━━━\n\n")
        else:
            parse_data.append(
                f"┎ <b>Source Link:</b> {link}{bp_link}\n\n━━━━━━━✦✗✦━━━━━━━\n\n"
            )

    end = time()

    if len(parse_data) != 0:
        parse_data[-1] = (
            parse_data[-1]
            + f"┎ <b>Total Links : {no}</b>\n┠ <b>Results In <code>{convert_time(end - start)}</code></b> !\n┖ <b>By </b>{message.from_user.mention} ( #ID{message.from_user.id} )"
        )
    tg_txt = "━━━━━━━✦✗✦━━━━━━━\n\n"
    for tg_data in parse_data:
        tg_txt += tg_data
        if len(tg_txt) > 4000:
            await wait_msg.edit(tg_txt, disable_web_page_preview=True)
            wait_msg = await message.reply(
                "<i>Fetching...</i>", reply_to_message_id=wait_msg.id
            )
            tg_txt = ""
            await asleep(2.5)

    if tg_txt != "":
        await wait_msg.edit(tg_txt, disable_web_page_preview=True)
    else:
        await wait_msg.delete()


@Bypass.on_message(AuthChannels, group=10)
async def channel_bypass(client, message):
    """
    Auto-bypass links in channel posts.
    The bot must be an admin with 'Edit Messages' permission in the channel.

    Only plain-URL bypass results are substituted inline (shortener → direct URL).
    Pre-formatted HTML results from DDL scrapers (hubcloud, gdflix, filepress, etc.)
    are skipped for in-place replacement — they would break the message structure.
    """
    txt = message.text or message.caption
    entities = message.entities or message.caption_entities
    LOGGER.info(
        f"Channel bypass triggered: chat={message.chat.id} "
        f"has_text={bool(txt)} has_entities={bool(entities)}"
    )
    if not txt or not entities:
        return

    links, atasks = [], []
    for enty in entities:
        if enty.type == MessageEntityType.URL:
            link = txt[enty.offset: enty.offset + enty.length]
        elif enty.type == MessageEntityType.TEXT_LINK:
            link = enty.url
        else:
            continue
        host = _urlparse(link).hostname or ""
        if any(s in host for s in _SKIP_DOMAINS):
            continue
        links.append(link)
        atasks.append(create_task(direct_link_checker(link)))

    if not atasks:
        return

    results = await gather(*atasks, return_exceptions=True)

    # Build replacement map: original_link → bypassed plain URL only.
    # Skip None, exceptions, and multi-line HTML scraper output (DDL sites).
    replacements = {}
    for link, result in zip(links, results):
        if result is None or isinstance(result, Exception):
            continue
        if isinstance(result, list):
            # Use only the first plain-URL entry; skip HTML-formatted list items
            plain = [r for r in result if isinstance(r, str) and not r.startswith("┏")]
            if plain:
                replacements[link] = plain[0]
        elif isinstance(result, str) and not result.startswith("┏"):
            # Only substitute plain URLs — skip pre-formatted HTML scraper output
            replacements[link] = result

    if not replacements:
        return

    new_txt = txt
    for orig, bypassed in replacements.items():
        new_txt = new_txt.replace(orig, bypassed)

    if new_txt == txt:
        return

    try:
        if message.text:
            await message.edit_text(new_txt, disable_web_page_preview=True)
        else:
            await message.edit_caption(new_txt)
    except Exception as e:
        LOGGER.warning(f"channel_bypass: failed to edit message {message.id} in {message.chat.id}: {e}")


@Bypass.on_inline_query()
async def inline_query(client, query):
    answers = []
    string = query.query.lower()
    if string.startswith("!bp "):
        link = string.strip("!bp ")
        start = time()
        try:
            bp_link = await direct_link_checker(link, True)
            end = time()

            if not is_excep_link(link):
                bp_link = (
                    f"┎ <b>Source Link:</b> {link}\n┃\n┖ <b>Bypass Link:</b> {bp_link}"
                )
            answers.append(
                InlineQueryResultArticle(
                    title="✅️ Bypass Link Success !",
                    input_message_content=InputTextMessageContent(
                        f"{bp_link}\n\n✎﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏\n\n🧭 <b>Took Only <code>{convert_time(end - start)}</code></b>",
                        disable_web_page_preview=True,
                    ),
                    description=f"Bypass via !bp {link}",
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "Bypass Again",
                                    switch_inline_query_current_chat="!bp ",
                                )
                            ]
                        ]
                    ),
                )
            )
        except Exception as e:
            bp_link = f"<b>Bypass Error:</b> {e}"
            end = time()

            answers.append(
                InlineQueryResultArticle(
                    title="❌️ Bypass Link Error !",
                    input_message_content=InputTextMessageContent(
                        f"┎ <b>Source Link:</b> {link}\n┃\n┖ {bp_link}\n\n✎﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏\n\n🧭 <b>Took Only <code>{convert_time(end - start)}</code></b>",
                        disable_web_page_preview=True,
                    ),
                    description=f"Bypass via !bp {link}",
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "Bypass Again",
                                    switch_inline_query_current_chat="!bp ",
                                )
                            ]
                        ]
                    ),
                )
            )

    else:
        answers.append(
            InlineQueryResultArticle(
                title="♻️ Bypass Usage: In Line",
                input_message_content=InputTextMessageContent(
                    """<b><i>FZ Bypass Bot!</i></b>
    
    <i>A Powerful Elegant Multi Threaded Bot written in Python... which can Bypass Various Shortener Links, Scrape links, and More ... </i>
    
🎛 <b>Inline Use :</b> !bp [Single Link]""",
                ),
                description="Bypass via !bp [link]",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "FZ Channel", url="https://t.me/FXTorrentz"
                            ),
                            InlineKeyboardButton(
                                "Try Bypass", switch_inline_query_current_chat="!bp "
                            ),
                        ]
                    ]
                ),
            )
        )
    try:
        await query.answer(results=answers, cache_time=0)
    except QueryIdInvalid:
        pass
