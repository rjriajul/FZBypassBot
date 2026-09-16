from asyncio import gather, create_task
from re import search, match, sub
from requests import get as rget
from cloudscraper import create_scraper
from urllib.parse import urlparse
from bs4 import BeautifulSoup, NavigableString, Tag

from FZBypass.core.bypass_ddl import transcript, _TIMEOUT


async def sharespark(url: str) -> str:
    gd_txt = ""
    cget = create_scraper().request
    res = cget("GET", "?action=printpage;".join(url.split("?")), timeout=_TIMEOUT)
    soup = BeautifulSoup(res.text, "html.parser")
    for br in soup.findAll("br"):
        next_s = br.nextSibling
        if not (next_s and isinstance(next_s, NavigableString)):
            continue
        if (
            (next2_s := next_s.nextSibling)
            and isinstance(next2_s, Tag)
            and next2_s.name == "br"
            and str(next_s).strip()
        ):
            if match(r"^(480p|720p|1080p)(.+)? Links:\Z", next_s):
                gd_txt += f'<b>{next_s.replace("Links:", "GDToT Links :")}</b>\n\n'
            for s in next_s.split():
                ns = sub(r"\(|\)", "", s)
                if match(r"https?://.+\.gdtot\.\S+", ns):
                    soup = BeautifulSoup(cget("GET", ns, timeout=_TIMEOUT).text, "html.parser")
                    parse_data = (
                        (soup.select('meta[property^="og:description"]')[0]["content"])
                        .replace("Download ", "")
                        .rsplit("-", maxsplit=1)
                    )
                    gd_txt += f"┎ <b>Name :</b> {parse_data[0]}\n┠ <b>Size :</b> {parse_data[-1]}\n┃\n┖ <b>GDTot :</b> {ns}\n\n"
                elif match(r"https?://pastetot\.\S+", ns):
                    nxt = sub(r"\(|\)|(https?://pastetot\.\S+)", "", next_s)
                    gd_txt += f"\n<b>{nxt}</b>\n┖ {ns}\n"
        if len(gd_txt) > 4000:
            return gd_txt  # Broken Function
    if gd_txt != "":
        return gd_txt


async def skymovieshd(url: str) -> str:
    soup = BeautifulSoup(rget(url, allow_redirects=False, timeout=_TIMEOUT).text, "html.parser")
    t = soup.select('div[class^="Robiul"]')
    gd_txt = f"<i>{t[-1].text.replace('Download ', '')}</i>"
    _cache = []
    for link in soup.select('a[href*="howblogs.xyz"]'):
        if link["href"] in _cache:
            continue
        _cache.append(link["href"])
        gd_txt += f"\n\n<b>{link.text} :</b> \n"
        nsoup = BeautifulSoup(
            rget(link["href"], allow_redirects=False, timeout=_TIMEOUT).text, "html.parser"
        )
        atag = nsoup.select('div[class="cotent-box"] > a[href]')
        for no, link in enumerate(atag, start=1):
            gd_txt += f"{no}. {link['href']}\n"
    return gd_txt


async def cinevood(url: str) -> str:
    soup = BeautifulSoup(rget(url, timeout=_TIMEOUT).text, "html.parser")
    titles = soup.select("h6")
    links_by_title = {}

    # Extract the post title from the webpage's title
    post_title = soup.title.string.strip()

    for title in titles:
        title_text = title.text.strip()
        gdtot_links = title.find_next("a", href=lambda href: "gdtot" in href.lower())
        multiup_links = title.find_next(
            "a", href=lambda href: "multiup" in href.lower()
        )
        filepress_links = title.find_next(
            "a", href=lambda href: "filepress" in href.lower()
        )
        gdflix_links = title.find_next("a", href=lambda href: "gdflix" in href.lower())
        kolop_links = title.find_next("a", href=lambda href: "kolop" in href.lower())
        zipylink_links = title.find_next(
            "a", href=lambda href: "zipylink" in href.lower()
        )

        links = []
        if gdtot_links:
            links.append(
                f'<a href="{gdtot_links["href"]}" style="text-decoration:none;"><b>GDToT</b></a>'
            )
        if multiup_links:
            links.append(
                f'<a href="{multiup_links["href"]}" style="text-decoration:none;"><b>MultiUp</b></a>'
            )
        if filepress_links:
            links.append(
                f'<a href="{filepress_links["href"]}" style="text-decoration:none;"><b>FilePress</b></a>'
            )
        if gdflix_links:
            links.append(
                f'<a href="{gdflix_links["href"]}" style="text-decoration:none;"><b>GDFlix</b></a>'
            )
        if kolop_links:
            links.append(
                f'<a href="{kolop_links["href"]}" style="text-decoration:none;"><b>Kolop</b></a>'
            )
        if zipylink_links:
            links.append(
                f'<a href="{zipylink_links["href"]}" style="text-decoration:none;"><b>ZipyLink</b></a>'
            )

        if links:
            links_by_title[title_text] = links

    prsd = f"<b>🔖 Title:</b> {post_title}\n"
    for title, links in links_by_title.items():
        prsd += f"\n┏<b>🏷️ Name:</b> <code>{title}</code>\n"
        prsd += "┗<b>🔗 Links:</b> " + " | ".join(links) + "\n"

    return prsd


async def kayoanime(url: str) -> str:
    soup = BeautifulSoup(rget(url, timeout=_TIMEOUT).text, "html.parser")
    titles = soup.select("h6")
    gdlinks = soup.select('a[href*="drive.google.com"], a[href*="tinyurl"]')
    prsd = f"<b>{soup.title.string}</b>"
    gd_txt, link = "GDrive", ""
    for n, gd in enumerate(gdlinks, start=1):
        if (link := gd["href"]) and "tinyurl" in link:
            link = rget(link, timeout=_TIMEOUT).url
            domain = urlparse(link).hostname
            gd_txt = (
                "Mega"
                if "mega" in domain
                else "G Group"
                if "groups" in domain
                else "Direct Link"
            )
        prsd += f"""

{n}. <i><b>{gd.string}</b></i>
┗ <b>Links :</b> <a href='{link}'><b>{gd_txt}</b></a>"""
    return prsd


async def toonworld4all(url: str):
    if "/redirect/main.php?url=" in url:
        return f"┎ <b>Source Link:</b> {url}\n┃\n┖ <b>Bypass Link:</b> {rget(url, timeout=_TIMEOUT).url}"
    xml = rget(url, timeout=_TIMEOUT).text
    soup = BeautifulSoup(xml, "html.parser")
    if "/episode/" not in url:
        epl = soup.select('a[href*="/episode/"]')
        tls = soup.select('div[class*="mks_accordion_heading"]')
        stitle = search(r"\"name\":\"(.+)\"", xml).group(1).split('"')[0]
        prsd = f"<b><i>{stitle}</i></b>"
        for n, (t, l) in enumerate(zip(tls, epl), start=1):
            prsd += f"""
        
{n}. <i><b>{t.strong.string}</b></i>
┖ <b>Link :</b> {l["href"]}"""
        return prsd
    links = soup.select('a[href*="/redirect/main.php?url="]')
    titles = soup.select("h5")
    prsd = f"<b><i>{titles[0].string}</i></b>"
    titles.pop(0)
    slicer, _ = divmod(len(links), len(titles))
    atasks = []
    for sl in links:
        nsl = ""
        while all(x not in nsl for x in ["rocklinks", "link1s"]):
            nsl = rget(sl["href"], allow_redirects=False, timeout=_TIMEOUT).headers["location"]
        if "rocklinks" in nsl:
            atasks.append(
                create_task(
                    transcript(
                        nsl,
                        "https://insurance.techymedies.com/",
                        "https://highkeyfinance.com/",
                        5,
                    )
                )
            )
        elif "link1s" in nsl:
            atasks.append(
                create_task(
                    transcript(nsl, "https://link1s.com", "https://anhdep24.com/", 9)
                )
            )

    com_tasks = await gather(*atasks, return_exceptions=True)
    lstd = [com_tasks[i : i + slicer] for i in range(0, len(com_tasks), slicer)]

    for no, tl in enumerate(titles):
        prsd += f"\n\n<b>{tl.string}</b>\n┃\n┖ <b>Links :</b> "
        for tl, sl in zip(links, lstd[no]):
            if isinstance(sl, Exception):
                prsd += str(sl)
            else:
                prsd += f"<a href='{sl}'>{tl.string}</a>, "
        prsd = prsd[:-2]
    return prsd


async def tamilmv(url):
    cget = create_scraper().request
    resp = cget("GET", url, timeout=_TIMEOUT)
    soup = BeautifulSoup(resp.text, "html.parser")
    mag = soup.select('a[href^="magnet:?xt=urn:btih:"]')
    tor = soup.select('a[data-fileext="torrent"]')
    parse_data = f"<b><u>{soup.title.string}</u></b>"
    for no, (t, m) in enumerate(zip(tor, mag), start=1):
        filename = sub(r"www\S+|\- |\.torrent", "", t.string)
        parse_data += f"""
        
{no}. <code>{filename}</code>
┖ <b>Links :</b> <a href="https://t.me/share/url?url={m['href'].split('&')[0]}"><b>Magnet </b>🧲</a>  | <a href="{t['href']}"><b>Torrent 🌐</b></a>"""
    return parse_data
