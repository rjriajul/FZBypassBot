"""
DDL-site resolver functions.

HTTP architecture
-----------------
  http   (httpx)       — primary async client; used for hubcloud, filepress,
                         gdflix (Cloudflare bypass via curl_cffi), gdtot,
                         appflix, sharerpw, sharer_scraper
  cf     (cfscrape)    — Cloudflare-compatible client; used for gdtot (which
                         requires JS-challenge bypass), sharerpw / sharer_scraper
                         (which use the same challenge path)
  curl_cffi cSession   — retained for gdflix (Chrome TLS fingerprint required)
  requests.Session     — retained synchronously for drivescript (KatDrive /
                         DriveFire only; these sites require session-level
                         cookie management with no async equivalent)

Every network call has a bounded timeout.
aiohttp is no longer used in this module.
"""
from __future__ import annotations

import asyncio
import json as _json
import re as _re
from asyncio import create_task, gather
from re import findall, DOTALL
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from bs4 import BeautifulSoup
from curl_cffi.requests import Session as cSession
from lxml import etree
from requests import Session

from FZBypass import LOGGER, Config
from FZBypass.core.bot_utils import get_dl
from FZBypass.core.exceptions import DDLException
from FZBypass.core.networking import cf, http
from FZBypass.core.networking.client import _MOBILE_UA, _SHORT_TIMEOUT
from FZBypass.core.networking.exceptions import NetworkError

# ── Desktop UA for sites that reject mobile UAs ──────────────────────────────
_DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# ── Longer timeout for multi-step resolvers ───────────────────────────────────
_LONG_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=15.0, pool=10.0)


# ═══════════════════════════════════════════════════════════════════════════════
# GDFlix — curl_cffi (Chrome TLS fingerprint required for Cloudflare bypass)
# ═══════════════════════════════════════════════════════════════════════════════

async def gdflix(url: str) -> str | list:
    """
    GDFlix bypass — uses curl_cffi Chrome impersonation to bypass Cloudflare.
    - /file/ pages: extracts all download buttons directly
    - /pack/ pages: iterates each file in batches to avoid 429, returns list of results
    curl_cffi is retained here because Cloudflare's TLS/JA3 fingerprint check
    rejects both httpx and cfscrape on this domain.
    """
    _up = urlparse

    c = cSession()

    # ── Pack handler ──────────────────────────────────────────────────────────
    if "/pack/" in url:
        raw = _up(url)
        base = f"{raw.scheme}://{raw.hostname}"

        def _sync_get_pack() -> tuple[str, str]:
            r = c.get(url, impersonate="chrome110", timeout=30)
            return r.text, str(r.url)

        try:
            html_text, _ = await asyncio.to_thread(_sync_get_pack)
        except Exception as e:
            raise DDLException(f"GDFlix: pack fetch failed — {e}") from e

        if "Just a moment" in html_text:
            raise DDLException("GDFlix: Cloudflare challenge not bypassed")
        soup = BeautifulSoup(html_text, "html.parser")
        title_tag = soup.find("title")
        pack_name = title_tag.text.replace("GDFlix | ", "").strip() if title_tag else "Pack"

        file_links = [base + a["href"] for a in soup.select("a[href^='/file/']")]
        if not file_links:
            raise DDLException("GDFlix: no files found in pack")

        BATCH = 3
        results: list = []
        for i in range(0, len(file_links), BATCH):
            batch = file_links[i: i + BATCH]
            tasks = [create_task(gdflix(fl)) for fl in batch]
            batch_results = await gather(*tasks, return_exceptions=True)
            results.extend(batch_results)
            if i + BATCH < len(file_links):
                await asyncio.sleep(1.5)

        output = [
            f"┏<b>Pack:</b> <code>{pack_name}</code>\n"
            f"┠<b>GDFlix:</b> <a href=\"{url}\">Source</a>\n"
            f"┠<b>Files:</b> {len(file_links)}"
        ]
        for i, (fl, result) in enumerate(zip(file_links, results), start=1):
            if isinstance(result, Exception):
                output.append(f"┎ <b>File {i} Error:</b> {result}")
            else:
                output.append(result)
        return output

    # ── Single file handler ───────────────────────────────────────────────────
    EXCLUDED_HOSTS = {
        "new4.gdflix.io", "gdflix.dev", "gdflix.sbs", "goflix.sbs",
        "t.me", "telegram.me", "telegram.dog",
        "cdn2.iconfinder.com", "challenges.cloudflare.com",
    }

    def _sync_get_file() -> str:
        r = c.get(url, impersonate="chrome110", timeout=30)
        if r.status_code != 200:
            raise DDLException(f"GDFlix: HTTP {r.status_code}")
        return r.text

    try:
        text = await asyncio.to_thread(_sync_get_file)
    except DDLException:
        raise
    except Exception as e:
        raise DDLException(f"GDFlix: fetch failed — {e}") from e

    if "Just a moment" in text:
        raise DDLException("GDFlix: Cloudflare challenge not bypassed")

    soup = BeautifulSoup(text, "html.parser")
    title_tag = soup.find("title")
    filename = title_tag.text.replace("GDFlix | ", "").strip() if title_tag else "Unknown"
    desc = soup.find("meta", property="og:description")
    size = "Unknown"
    if desc and " - " in (desc.get("content") or ""):
        size = desc["content"].rsplit(" - ", 1)[-1]

    seen: set[str] = set()
    links: list[tuple[str, str]] = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href.startswith("http"):
            continue
        host = urlparse(href).hostname or ""
        if not host or host in EXCLUDED_HOSTS:
            continue
        cls = " ".join(a.get("class", []))
        if "btn" not in cls:
            continue
        if href in seen:
            continue
        seen.add(href)
        label = " ".join(a.text.strip().split()) or host.split(".")[0].capitalize() + " Server"
        links.append((label, href))

    if not links:
        raise DDLException("GDFlix: no download links found")

    lines = [
        f"┏<b>Name:</b> <code>{filename}</code>",
        f"┠<b>Size:</b> <code>{size}</code>",
        f"┠<b>GDFlix:</b> <a href=\"{url}\">Source</a>",
    ]
    for i, (label, link) in enumerate(links):
        prefix = "┗" if i == len(links) - 1 else "┠"
        lines.append(f"{prefix}<b>{label}:</b> <a href=\"{link}\">Click Here</a>")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# FilePress — httpx (migrated from aiohttp)
# ═══════════════════════════════════════════════════════════════════════════════

async def filepress(url: str) -> str:
    """
    FilePress bypass — httpx for all HTTP calls.
    cfscrape is used only for the initial redirect-follow to get the
    canonical URL (FilePress sites sometimes have CF protection on the
    landing page), then httpx takes over for the API calls.
    """
    # Step 1: resolve the landing URL via cfscrape (handles CF on some instances)
    try:
        r0 = await cf.get(url)
        url = r0.url
    except NetworkError as e:
        raise DDLException(f"FilePress: {type(e).__name__}") from e

    raw = urlparse(url)
    file_id = raw.path.split("/")[-1]
    base = f"{raw.scheme}://{raw.hostname}"

    # Step 2: POST to telegram download API using httpx
    try:
        resp = await http.post(
            f"{base}/api/file/telegram/downlaod/",
            json={"id": file_id},
            headers={"Referer": base, "Content-Type": "application/json"},
            timeout=_LONG_TIMEOUT,
        )
        resp.raise_for_status()
        tg_id = _json.loads(resp.content)
    except (NetworkError, _json.JSONDecodeError) as e:
        raise DDLException(f"FilePress: API call failed — {type(e).__name__}") from e

    tg_url = tg_id.get("data", "") if tg_id.get("data") else ""
    if not tg_url:
        raise DDLException(
            tg_id.get("statusText", "FilePress: no download link returned")
        )

    # Step 3: resolve bot name from JS bundle to build a t.me link
    tg_link = tg_url  # fallback
    try:
        token = tg_url.split("start=")[-1] if "start=" in tg_url else ""
        if token:
            idx_resp = await http.get(base, headers={"Referer": base}, timeout=_SHORT_TIMEOUT)
            js_m = _re.search(r'src="(/assets/index-[^"]+\.js)"', idx_resp.text)
            if js_m:
                js_resp = await http.get(
                    f"{base}{js_m.group(1)}", headers={"Referer": base}, timeout=_SHORT_TIMEOUT
                )
                bot_m = _re.search(r"filepress_[a-zA-Z0-9]+_bot", js_resp.text)
                if bot_m:
                    tg_link = f"https://t.me/{bot_m.group()}/?start={token}"
    except Exception:
        pass  # fallback to tgfiles URL

    return (
        f"┏<b>FilePress:</b> <a href=\"{url}\">Source</a>\n"
        f"┗<b>Telegram:</b> <a href=\"{tg_link}\">Click Here</a>"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# GDToT — cfscrape (JS-challenge bypass genuinely required)
# ═══════════════════════════════════════════════════════════════════════════════

async def gdtot(url: str) -> str:
    """
    Uses cfscrape — GDToT pages have Cloudflare JS challenges.
    All calls are routed through cf adapter (asyncio.to_thread).
    """
    try:
        r0 = await cf.get(url)
        url = r0.url
        p_url = urlparse(url)
        res = await cf.post(
            f"{p_url.scheme}://{p_url.hostname}/ddl",
            data={"dl": url.split("/")[-1]},
        )
    except NetworkError as e:
        raise DDLException(f"GDToT: {type(e).__name__}") from e

    if (
        drive_link := findall(r"myDl\('(.*?)'\)", res.text)
    ) and "drive.google.com" in drive_link[0]:
        d_link = drive_link[0]
    elif Config.GDTOT_CRYPT:
        try:
            await cf.get(url, cookies={"crypt": Config.GDTOT_CRYPT})
            p_url = urlparse(url)
            js_script = await cf.post(
                f"{p_url.scheme}://{p_url.hostname}/dld",
                data={"dwnld": url.split("/")[-1]},
            )
        except NetworkError as e:
            raise DDLException(f"GDToT: {type(e).__name__}") from e
        g_id = findall("gd=(.*?)&", js_script.text)
        try:
            from base64 import b64decode
            decoded_id = b64decode(str(g_id[0])).decode("utf-8")
        except Exception:
            raise DDLException(
                "GDToT: Try in your browser — file not found or user limit exceeded!"
            )
        d_link = f"https://drive.google.com/open?id={decoded_id}"
    else:
        raise DDLException(
            "GDToT: Drive Link not found. GDTOT_CRYPT not provided!"
        )

    try:
        page_r = await cf.get(url)
    except NetworkError as e:
        raise DDLException(f"GDToT: {type(e).__name__}") from e

    soup = BeautifulSoup(page_r.text, "html.parser")
    items = soup.select('meta[property^="og:description"]')
    if not items:
        raise DDLException("GDToT: og:description meta not found")
    parse_data = items[0]["content"].replace("Download ", "").rsplit("-", maxsplit=1)
    parse_txt = (
        f"┏<b>Name:</b> <code>{parse_data[0]}</code>\n"
        f"┠<b>Size:</b> <code>{parse_data[-1]}</code>\n"
        f"┠<b>GDToT:</b> <a href=\"{url}\">Click Here</a>\n"
    )
    if Config.DIRECT_INDEX:
        parse_txt += f"┠<b>Temp Index:</b> <a href='{get_dl(d_link)}'>Click Here</a>\n"
    parse_txt += f"┗<b>GDrive:</b> <a href='{d_link}'>Click Here</a>"
    return parse_txt


# ═══════════════════════════════════════════════════════════════════════════════
# DriveScript (HubDrive / KatDrive / DriveFire)
# ═══════════════════════════════════════════════════════════════════════════════

async def drivescript(url: str, crypt: str, dtype: str) -> str:
    """
    HubDrive: now chains directly to hubcloud() — no crypt needed.
    KatDrive / DriveFire: uses synchronous requests.Session in
    asyncio.to_thread() — these sites require cookie-jar session
    management that aiohttp/httpx don't neatly replicate for this flow.
    """
    # ── HubDrive ──────────────────────────────────────────────────────────────
    if dtype == "HubDrive":
        def _sync_hubdrive() -> tuple[str, str, str | None]:
            rs = Session()
            rs.headers["User-Agent"] = _DESKTOP_UA
            resp = rs.get(url, timeout=20)
            soup = BeautifulSoup(resp.text, "html.parser")
            h6 = soup.find("h6", class_="font-weight-bold")
            title = h6.text.strip() if h6 else (
                soup.title.string.replace("HubDrive | ", "").strip()
                if soup.title else "Unknown"
            )
            tds = soup.select("td")
            size = tds[1].text.strip() if len(tds) > 1 else "Unknown"
            hc_tag = soup.find("a", href=lambda h: h and "hubcloud" in h)
            hc_href = hc_tag["href"] if hc_tag else None
            return title, size, hc_href

        try:
            title, size, hc_href = await asyncio.to_thread(_sync_hubdrive)
        except Exception as e:
            raise DDLException(f"HubDrive: fetch failed — {type(e).__name__}") from e

        if hc_href:
            try:
                return await hubcloud(hc_href)
            except DDLException:
                pass  # fall through to plain output
        parse_txt = (
            f"┏<b>Name:</b> <code>{title}</code>\n"
            f"┠<b>Size:</b> <code>{size}</code>\n"
            f"┠<b>HubDrive:</b> <a href=\"{url}\">Click Here</a>"
        )
        if hc_href:
            parse_txt += f"\n┗<b>HubCloud:</b> <a href=\"{hc_href}\">Click Here</a>"
        else:
            parse_txt += "\n┗<b>Note:</b> Login required for GDrive link"
        return parse_txt

    # ── KatDrive / DriveFire ──────────────────────────────────────────────────
    def _sync_drivescript() -> str:
        rs = Session()
        rs.headers["User-Agent"] = _DESKTOP_UA
        resp = rs.get(url, timeout=20)
        p_url = urlparse(url)

        titles = findall(r">(.*?)<\/h4>", resp.text)
        sizes = findall(r">(.*?)<\/td>", resp.text)
        title = titles[0] if titles else "Unknown"
        size = sizes[1] if len(sizes) > 1 else (sizes[0] if sizes else "Unknown")

        dlink = ""
        if dtype != "DriveFire":
            try:
                js_q = rs.post(
                    f"{p_url.scheme}://{p_url.hostname}/ajax.php?ajax=direct-download",
                    data={"id": url.split("/")[-1]},
                    headers={"x-requested-with": "XMLHttpRequest"},
                    timeout=15,
                ).json()
                if str(js_q.get("code")) == "200":
                    dlink = f"{p_url.scheme}://{p_url.hostname}{js_q['file']}"
            except Exception as e:
                LOGGER.error(f"drivescript direct-download: {e}")

        if not dlink and crypt:
            rs.get(url, cookies={"crypt": crypt}, timeout=15)
            try:
                js_q = rs.post(
                    f"{p_url.scheme}://{p_url.hostname}/ajax.php?ajax=download",
                    data={"id": url.split("/")[-1]},
                    headers={"x-requested-with": "XMLHttpRequest"},
                    timeout=15,
                ).json()
            except Exception as e:
                raise DDLException(f"{type(e).__name__}") from e
            if str(js_q.get("code")) == "200":
                dlink = f"{p_url.scheme}://{p_url.hostname}{js_q['file']}"

        if not dlink and not crypt:
            raise DDLException(f"{dtype} Crypt Not Provided and Direct Link Generate Failed")
        if not dlink:
            raise DDLException(js_q.get("file", f"{dtype}: failed to generate link"))

        res = rs.get(dlink, timeout=20)
        soup = BeautifulSoup(res.text, "html.parser")
        gd_data = soup.select('a[class="btn btn-primary btn-user"]')
        d_link = gd_data[0]["href"] if gd_data else None

        parse_txt = (
            f"┏<b>Name:</b> <code>{title}</code>\n"
            f"┠<b>Size:</b> <code>{size}</code>\n"
            f"┠<b>{dtype}:</b> <a href=\"{url}\">Click Here</a>"
        )
        if d_link and Config.DIRECT_INDEX:
            parse_txt += f"\n┠<b>Temp Index:</b> <a href='{get_dl(d_link)}'>Click Here</a>"
        if d_link:
            parse_txt += f"\n┗<b>GDrive:</b> <a href='{d_link}'>Click Here</a>"
        else:
            parse_txt += "\n┗<b>Note:</b> GDrive link not found on page"
        return parse_txt

    try:
        return await asyncio.to_thread(_sync_drivescript)
    except DDLException:
        raise
    except Exception as e:
        raise DDLException(f"{dtype}: {type(e).__name__}: {e}") from e


# ═══════════════════════════════════════════════════════════════════════════════
# HubCloud — httpx (migrated from aiohttp)
# ═══════════════════════════════════════════════════════════════════════════════

async def hubcloud(url: str) -> str:
    """
    Two-step HubCloud bypass — httpx for both steps.
    Step 1: GET hubcloud drive page → extract gamerxyt.com URL.
    Step 2: GET gamerxyt endpoint → parse all download buttons.
    """
    ua = _DESKTOP_UA
    try:
        r1 = await http.get(url, headers={"User-Agent": ua}, timeout=_LONG_TIMEOUT)
    except NetworkError as e:
        raise DDLException(f"HubCloud: step 1 failed — {type(e).__name__}") from e

    m = _re.search(r"var url = '(https://gamerxyt\.com/hubcloud\.php[^']+)'", r1.text)
    if m:
        ajax_url = m.group(1)
    else:
        soup1 = BeautifulSoup(r1.text, "html.parser")
        dl = soup1.find("a", id="download")
        if not dl or not dl.get("href"):
            raise DDLException("HubCloud: could not find download URL in page")
        ajax_url = dl["href"]

    try:
        r2 = await http.get(
            ajax_url,
            headers={"User-Agent": ua, "Referer": "https://hubcloud.ist/"},
            timeout=_LONG_TIMEOUT,
        )
    except NetworkError as e:
        raise DDLException(f"HubCloud: step 2 failed — {type(e).__name__}") from e

    soup2 = BeautifulSoup(r2.text, "html.parser")
    size_el = soup2.find(id="size")
    if size_el and size_el.text.strip() in ("NAN", "NAN "):
        raise DDLException("HubCloud: token expired — retry")

    title = soup2.find("title")
    filename = title.text.strip() if title else "Unknown"
    size_text = size_el.text.strip() if size_el else "Unknown"

    EXCLUDED_HOSTS = {
        "hubcloud.ist", "hubcloud.cx", "hubcloud.club", "hubcloud.fans",
        "hubcloud.lat", "gamerxyt.com", "tinyurl.com", "t.me",
        "snvhost.com", "one.one.one.one", "hdhub4u.ms", "www.google.com",
    }

    def _label(href: str) -> str:
        host = urlparse(href).hostname or ""
        if "pongala" in host or "lenin.buzz" in host:
            return "FSLv2 Server"
        if "r2.cloudflarestorage.com" in host:
            return "FSL Server"
        if "storage.googleapis.com" in host:
            return "ZipDisk Server"
        if "pixeldrain" in host:
            return "Pixeldrain"
        if "fuckingfast.net" in host:
            return "Buzz Server"
        return host.replace("www.", "").split(".")[0].capitalize() + " Server"

    seen: set[str] = set()
    links: list[tuple[str, str]] = []
    for a in soup2.find_all("a", href=True):
        href = a["href"].strip()
        if not href.startswith("https://"):
            continue
        host = urlparse(href).hostname or ""
        if not host or host in EXCLUDED_HOSTS:
            continue
        cls = " ".join(a.get("class", []))
        if "btn" not in cls:
            continue
        if href in seen:
            continue
        seen.add(href)
        links.append((_label(href), href))

    if not links:
        raise DDLException("HubCloud: no download links found")

    lines = [
        f"┏<b>Name:</b> <code>{filename}</code>",
        f"┠<b>Size:</b> <code>{size_text}</code>",
        f"┠<b>HubCloud:</b> <a href=\"{url}\">Source</a>",
    ]
    for i, (label, link) in enumerate(links):
        prefix = "┗" if i == len(links) - 1 else "┠"
        lines.append(f"{prefix}<b>{label}:</b> <a href=\"{link}\">Click Here</a>")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# AppFlix — cfscrape (Cloudflare on appdrive/gdflix landing pages)
# ═══════════════════════════════════════════════════════════════════════════════

async def appflix(url: str) -> str:
    """Uses cfscrape for page fetches (Cloudflare on landing pages)."""

    async def appflix_single(file_url: str) -> str:
        try:
            r0 = await cf.get(file_url)
            file_url = r0.url
            r1 = await cf.get(file_url, allow_redirects=False)
        except NetworkError as e:
            raise DDLException(f"appflix: {type(e).__name__}") from e

        soup = BeautifulSoup(r1.text, "html.parser")
        ss = soup.select("li[class^='list-group-item']")
        if len(ss) < 3:
            raise DDLException("appflix: unexpected page structure (< 3 list items)")
        dbotv2 = (
            dbot[0]["href"]
            if "gdflix" in file_url and (dbot := soup.select("a[href*='drivebot.lol']"))
            else None
        )
        try:
            d_link = await sharer_scraper(file_url)
        except Exception as e:
            if not dbotv2:
                raise DDLException(str(e)) from e
            d_link = str(e)

        parse_txt = (
            f"┏<b>Name:</b> <code>{ss[0].string.split(':')[1]}</code>\n"
            f"┠<b>Size:</b> <code>{ss[2].string.split(':')[1]}</code>\n"
            f"┠<b>Source:</b> <code>{file_url}</code>"
        )
        if dbotv2:
            parse_txt += f"\n┠<b>DriveBot V2:</b> <a href='{dbotv2}'>Click Here</a>"
        if d_link and Config.DIRECT_INDEX:
            parse_txt += f"\n┠<b>Temp Index:</b> <a href='{get_dl(d_link)}'>Click Here</a>"
        parse_txt += f"\n┗<b>GDrive:</b> <a href='{d_link}'>Click Here</a>"
        return parse_txt

    if "/pack/" in url:
        try:
            r0 = await cf.get(url)
            url = r0.url
            r1 = await cf.get(url)
        except NetworkError as e:
            raise DDLException(f"appflix pack: {type(e).__name__}") from e

        soup = BeautifulSoup(r1.text, "html.parser")
        p_url = urlparse(url)
        body = ""
        atasks = [
            create_task(
                appflix_single(f"{p_url.scheme}://{p_url.hostname}" + a["href"])
            )
            for a in soup.select("a[href^='/file/']")
        ]
        completed_tasks = await gather(*atasks, return_exceptions=True)
        for bp_link in completed_tasks:
            body += "\n\n" + (str(bp_link) if isinstance(bp_link, Exception) else bp_link)
        title = soup.title.string if soup.title else "Pack"
        return f"┏<b>Name:</b> <code>{title}</code>\n┗<b>Source:</b> <code>{url}</code>{body}"

    return await appflix_single(url)


# ═══════════════════════════════════════════════════════════════════════════════
# SharerPW — cfscrape (Cloudflare on sharer.pw)
# ═══════════════════════════════════════════════════════════════════════════════

async def sharerpw(url: str, force: bool = False) -> str:
    """Uses cfscrape — sharer.pw has Cloudflare protection."""
    if not Config.XSRF_TOKEN and not Config.LARAVEL_SESSION:
        raise DDLException("XSRF_TOKEN or LARAVEL_SESSION not Provided!")

    cookies = {
        "XSRF-TOKEN": Config.XSRF_TOKEN,
        "laravel_session": Config.LARAVEL_SESSION,
    }
    try:
        resp = await cf.get(url, cookies=cookies, fresh=True)
    except NetworkError as e:
        raise DDLException(f"sharerpw: {type(e).__name__}") from e

    parse_txt_items = findall(r">(.*?)<\/td>", resp.text)
    try:
        ddl_btn = etree.HTML(resp.content).xpath("//button[@id='btndirect']")
        token = findall(r"_token\s=\s'(.*?)'", resp.text, DOTALL)[0]
    except (IndexError, TypeError):
        raise DDLException("sharerpw: could not extract CSRF token from page")

    data: dict = {"_token": token}
    if not force:
        data["nl"] = 1
    hdrs = {
        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        "x-requested-with": "XMLHttpRequest",
    }
    try:
        res_r = await cf.post(url + "/dl", data=data, headers=hdrs, cookies=cookies, fresh=True)
        res = _json.loads(res_r.content)
    except (NetworkError, _json.JSONDecodeError) as e:
        raise DDLException(f"sharerpw: POST failed — {e}") from e

    # Build header from parse_txt_items safely
    def _safe(idx: int) -> str:
        return parse_txt_items[idx] if len(parse_txt_items) > idx else "N/A"

    parse_data = (
        f"┏<b>Name:</b> <code>{_safe(2)}</code>\n"
        f"┠<b>Size:</b> <code>{_safe(8)}</code>\n"
        f"┠<b>Added On:</b> <code>{_safe(11)}</code>\n"
    )
    if res.get("status") == 0:
        if Config.DIRECT_INDEX:
            parse_data += f"\n┠<b>Temp Index:</b> <a href='{get_dl(res['url'])}'>Click Here</a>"
        return parse_data + f"\n┗<b>GDrive:</b> <a href='{res['url']}'>Click Here</a>"
    if res.get("status") == 2:
        msg = res.get("message", "").replace("<br/>", "\n")
        return parse_data + f"\n┗<b>Error:</b> {msg}"
    if ddl_btn and not force:
        return await sharerpw(url, force=True)
    raise DDLException(f"sharerpw: unexpected status {res.get('status')}")


# ═══════════════════════════════════════════════════════════════════════════════
# SharerScraper — cfscrape (multipart POST to a CF-protected scraper API)
# ═══════════════════════════════════════════════════════════════════════════════

async def sharer_scraper(url: str) -> str:
    """Uses cfscrape — the target scraper API is Cloudflare-protected."""
    try:
        r0 = await cf.get(url)
        url = r0.url
        raw = urlparse(url)
        r1 = await cf.get(
            url,
            headers={"useragent": "Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US) AppleWebKit/534.10 Chrome/7.0.548.0 Safari/534.10"},
        )
    except NetworkError as e:
        raise DDLException(f"sharer_scraper: {type(e).__name__}") from e

    key_matches = findall(r'"key",\s+"(.*?)"', r1.text)
    if not key_matches:
        raise DDLException("sharer_scraper: Download Link Key not found!")
    key = key_matches[0]
    if not etree.HTML(r1.content).xpath("//button[@id='drc']"):
        raise DDLException("sharer_scraper: no direct download button on page")

    boundary = uuid4()
    hdrs = {
        "Content-Type": f"multipart/form-data; boundary=----WebKitFormBoundary{boundary}",
        "x-token": raw.hostname,
        "useragent": "Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US) AppleWebKit/534.10 Chrome/7.0.548.0 Safari/534.10",
    }
    body = (
        f'------WebKitFormBoundary{boundary}\r\nContent-Disposition: form-data; name="action"\r\n\r\ndirect\r\n'
        f'------WebKitFormBoundary{boundary}\r\nContent-Disposition: form-data; name="key"\r\n\r\n{key}\r\n'
        f'------WebKitFormBoundary{boundary}\r\nContent-Disposition: form-data; name="action_token"\r\n\r\n\r\n'
        f"------WebKitFormBoundary{boundary}--\r\n"
    )
    try:
        res_r = await cf.post(url, data=body, headers=hdrs)
        res = _json.loads(res_r.content)
    except (NetworkError, _json.JSONDecodeError) as e:
        raise DDLException(f"sharer_scraper: POST failed — {type(e).__name__}") from e

    if "url" not in res:
        raise DDLException("sharer_scraper: Drive Link not found, Try in your browser")
    if "drive.google.com" in res["url"]:
        return res["url"]

    try:
        r2 = await cf.get(res["url"])
    except NetworkError as e:
        raise DDLException(f"sharer_scraper: follow-up GET failed — {type(e).__name__}") from e

    drive_links = etree.HTML(r2.content).xpath("//a[contains(@class,'btn')]/@href")
    if drive_links and "drive.google.com" in drive_links[0]:
        return drive_links[0]
    raise DDLException("sharer_scraper: Drive Link not found, Try in your browser")
