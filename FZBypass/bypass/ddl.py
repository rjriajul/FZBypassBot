"""
Bypass resolver functions — shortener / direct-link extraction.

HTTP architecture
-----------------
  http  (httpx)       — primary async client for all normal requests
  cf    (cfscrape)    — Cloudflare-compatible client; used only where
                        cloudscraper/JS-challenge behaviour is genuinely
                        needed, always called via asyncio.to_thread
  curl_cffi cSession  — retained for ouo.press (Chrome TLS fingerprint
                        required; neither httpx nor cfscrape replicates it)

Every network call has a bounded timeout.
No aiohttp ClientSession is created here any more.
"""
from __future__ import annotations

import json as _json
import re as _re
from asyncio import sleep as asleep
from urllib.parse import quote, urlparse

import httpx
from bs4 import BeautifulSoup
from curl_cffi.requests import Session as cSession
from requests import Session  # synchronous — only used inside terabox WAP path

from FZBypass import Config
from FZBypass.core.exceptions import DDLException
from FZBypass.core.networking import cf, http
from FZBypass.core.networking.client import DEFAULT_TIMEOUT
from FZBypass.core.networking.exceptions import NetworkError
from FZBypass.bypass.recaptcha import recaptchaV3

# ── Shared httpx timeout override for short-lived shortener pages ─────────────
_SHORT_TIMEOUT = httpx.Timeout(connect=10.0, read=20.0, write=15.0, pool=10.0)

# ── Mobile User-Agent used by most shortener bypass attempts ─────────────────
_MOBILE_UA = (
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)


# ═══════════════════════════════════════════════════════════════════════════════
# FILE HOSTER RESOLVERS
# ═══════════════════════════════════════════════════════════════════════════════

async def yandex_disk(url: str) -> str:
    """
    Uses cfscrape (via adapter) — Yandex Cloud API requires
    browser-like headers which cfscrape provides reliably.
    """
    api = f"https://cloud-api.yandex.net/v1/disk/public/resources/download?public_key={url}"
    try:
        resp = await cf.get(api)
        resp.raise_for_status()
        data = _json.loads(resp.content)
        return data["href"]
    except KeyError:
        raise DDLException("Yandex: File not Found / Download Limit Exceeded")
    except NetworkError as e:
        raise DDLException(f"Yandex: {e}") from e


async def mediafire(url: str) -> str:
    """
    Uses cfscrape — Mediafire applies bot-detection headers checks.
    """
    # Fast path: direct download URL already in the input
    if m := _re.findall(r"https?://download\d+\.mediafire\.com/\S+/\S+/\S+", url):
        return m[0]
    try:
        r1 = await cf.get(url)
        url = r1.url
        r2 = await cf.get(url)
        page = r2.text
    except NetworkError as e:
        raise DDLException(f"Mediafire: {type(e).__name__}") from e

    if m := _re.findall(r"'(https?://download\d+\.mediafire\.com/\S+/\S+/\S+)'", page):
        return m[0]
    if m := _re.findall(r"//(www\.mediafire\.com/file/\S+/\S+/file\?\S+)", page):
        return await mediafire("https://" + m[0].strip('"'))
    raise DDLException("Mediafire: no download links found in page")


async def shrdsk(url: str) -> str:
    """
    Uses cfscrape for the initial redirect, then httpx for the API call.
    """
    try:
        r = await cf.get(url)
        short_id = r.url.split("/")[-1]
    except NetworkError as e:
        raise DDLException(f"Shrdsk: {type(e).__name__}") from e

    api = f"https://us-central1-affiliate2apk.cloudfunctions.net/get_data?shortid={short_id}"
    try:
        resp = await http.get(api, timeout=_SHORT_TIMEOUT)
        resp.raise_for_status()
    except NetworkError as e:
        raise DDLException(f"Shrdsk: {type(e).__name__}") from e

    data = _json.loads(resp.content)
    if data.get("type", "").lower() == "upload" and "video_url" in data:
        return quote(data["video_url"], safe=":/")
    raise DDLException("Shrdsk: No Direct Link Found")


async def terabox(url: str) -> list:
    """
    Resolve a Terabox share URL to a list of direct download links.

    Path 1 — TERABOX_API_URL (preferred):
        Uses httpx with 60 s timeout.  Returns proxy_url links.
    Path 2 — TERA_COOKIE WAP bypass (fallback):
        Synchronous requests.Session used inside
        asyncio.to_thread() to avoid blocking the event loop.
    """
    # ── Path 1: terabox-downloader-api ───────────────────────────────────────
    if Config.TERABOX_API_URL:
        api_timeout = httpx.Timeout(connect=10.0, read=60.0, write=15.0, pool=10.0)
        try:
            resp = await http.post(
                f"{Config.TERABOX_API_URL}/download",
                json={"url": url},
                headers={"Content-Type": "application/json"},
                timeout=api_timeout,
                retry=True,
            )
            resp.raise_for_status()
            data = _json.loads(resp.content)
        except NetworkError as e:
            if not Config.TERA_COOKIE:
                raise DDLException(
                    f"Terabox API unreachable: {type(e).__name__}: {e}"
                ) from e
            # else fall through to WAP path
        else:
            if data.get("status") == "success":
                files = data["data"].get("files", [])
                links = [
                    f.get("proxy_url") or f.get("dlink")
                    for f in files
                    if f.get("proxy_url") or f.get("dlink")
                ]
                if links:
                    return links
                raise DDLException("Terabox API: no download links in response")
            raise DDLException(
                f"Terabox API: {data.get('message', 'unknown error')}"
            )

    # ── Path 2: WAP bypass using TERA_COOKIE ─────────────────────────────────
    if not Config.TERA_COOKIE:
        raise DDLException(
            "Terabox: set TERABOX_API_URL (recommended) or TERA_COOKIE to bypass"
        )

    import asyncio
    from urllib.parse import parse_qs, urlparse as _up

    TERABOX_DOMAINS = [
        ".terabox.com", ".1024terabox.com", ".teraboxapp.com",
        ".nephobox.com", ".4funbox.co", ".mirrobox.com",
        ".momerybox.com", ".terasharefile.com", ".freeterabox.com",
    ]
    TERABOX_HOSTNAMES = [
        "www.terabox.com", "www.1024terabox.com", "www.teraboxapp.com",
        "www.terasharefile.com", "www.nephobox.com", "www.4funbox.co",
        "www.mirrobox.com", "www.momerybox.com", "www.freeterabox.com",
    ]
    MOBILE_UA_WAP = _MOBILE_UA

    def _parse_surl(share_url: str) -> str:
        parsed = _up(share_url)
        if "/s/" in parsed.path:
            surl = parsed.path.split("/s/")[-1].strip("/")
        else:
            qs = parse_qs(parsed.query)
            surl = qs.get("surl", [""])[0]
        if not surl:
            raise DDLException(f"Cannot extract surl from URL: {share_url}")
        if len(surl) > 22 and surl.startswith("1"):
            surl = surl[1:]
        if len(surl) < 8:
            raise DDLException(f"Invalid surl: '{surl}'")
        return surl

    def _build_session(ndus: str) -> Session:
        sess = Session()
        for domain in TERABOX_DOMAINS:
            sess.cookies.set("ndus", ndus, domain=domain)
        return sess

    def _fetch_wap_sync(sess: Session, surl: str, share_url: str) -> str:
        host = _up(share_url).hostname or ""
        candidates: list[str] = []
        if host:
            candidates += [
                f"http://{host}/wap/share/filelist?surl={surl}",
                f"https://{host}/wap/share/filelist?surl={surl}",
            ]
        for h in TERABOX_HOSTNAMES:
            u = f"https://{h}/wap/share/filelist?surl={surl}"
            if u not in candidates:
                candidates.append(u)
        candidates.append(f"http://www.terabox.com/wap/share/filelist?surl={surl}")
        headers = {"User-Agent": MOBILE_UA_WAP, "Accept": "text/html,*/*"}
        for wap_url in candidates:
            try:
                r = sess.get(wap_url, headers=headers, allow_redirects=True, timeout=15)
                if r.status_code == 200 and "__INITIAL_STATE__" in r.text:
                    return r.text
            except Exception:
                continue
        raise DDLException(f"Could not load Terabox WAP page for surl={surl}")

    def _extract_dlinks(html: str) -> list[str]:
        m = _re.search(
            r"window\.__INITIAL_STATE__\s*=\s*(\{.+?\})\s*(?:;|</script>)",
            html, _re.DOTALL,
        )
        if not m:
            raise DDLException("window.__INITIAL_STATE__ not found in WAP page")
        try:
            state = _json.loads(m.group(1))
        except _json.JSONDecodeError:
            fl_m = _re.search(r'"fileList"\s*:\s*(\[.+?\])\s*,\s*"', html, _re.DOTALL)
            if not fl_m:
                raise DDLException("Could not parse file list from WAP page")
            file_list = _json.loads(fl_m.group(1))
            state = {"share": {"fileList": file_list}}
        file_list = state.get("share", {}).get("fileList", [])
        if not file_list:
            raise DDLException("No files found in Terabox WAP page")
        dlinks = [
            f["dlink"] for f in file_list
            if str(f.get("isdir", "0")) != "1" and f.get("dlink")
        ]
        if not dlinks:
            raise DDLException("No direct links found (folder-only share?)")
        return dlinks

    def _wap_bypass(ndus: str, surl: str, share_url: str) -> list[str]:
        sess = _build_session(ndus)
        html = _fetch_wap_sync(sess, surl, share_url)
        return _extract_dlinks(html)

    try:
        surl = _parse_surl(url)
        return await asyncio.to_thread(_wap_bypass, Config.TERA_COOKIE, surl, url)
    except DDLException:
        raise
    except Exception as e:
        raise DDLException(f"Terabox WAP bypass error: {type(e).__name__}: {e}") from e


# ═══════════════════════════════════════════════════════════════════════════════
# SHORTENER RESOLVERS (httpx-based)
# ═══════════════════════════════════════════════════════════════════════════════

async def try2link(url: str) -> str:
    """Uses httpx — normal HTTP shortener with countdown form."""
    DOMAIN = "https://try2link.com"
    code = url.split("/")[-1]
    referers = [
        "https://hightrip.net/",
        "https://to-travel.net",
        "https://world2our.com/",
    ]
    html: str | None = None
    for referer in referers:
        try:
            resp = await http.get(
                f"{DOMAIN}/{code}",
                headers={"Referer": referer, "User-Agent": _MOBILE_UA},
                timeout=_SHORT_TIMEOUT,
            )
            if resp.status_code == 200:
                html = resp.text
                break
        except NetworkError:
            continue

    if html is None:
        raise DDLException("try2link: could not load page (all referers failed)")

    soup = BeautifulSoup(html, "html.parser")
    go_link = soup.find(id="go-link")
    if not go_link:
        raise DDLException("try2link: go-link form not found")
    inputs = go_link.find_all(name="input")
    data = {inp.get("name"): inp.get("value") for inp in inputs}
    await asleep(6)
    try:
        resp2 = await http.post(
            f"{DOMAIN}/links/go",
            data=data,
            headers={"X-Requested-With": "XMLHttpRequest", "User-Agent": _MOBILE_UA},
            timeout=_SHORT_TIMEOUT,
        )
    except NetworkError as e:
        raise DDLException(f"try2link: POST failed — {e}") from e

    ct = resp2.headers.get("content-type", "")
    if "application/json" in ct:
        result = _json.loads(resp2.content)
        if "url" in result:
            return result["url"]
    raise DDLException("try2link: no URL in response")


async def gyanilinks(url: str) -> str:
    """Uses httpx — standard countdown shortener (bloggingaro backend)."""
    code = url.split("/")[-1]
    ua = _MOBILE_UA
    DOMAIN = "https://go.bloggingaro.com"
    hdrs1 = {"Referer": "https://tech.hipsonyc.com/", "User-Agent": ua}
    hdrs2 = {"Referer": "https://hipsonyc.com/", "User-Agent": ua}
    try:
        r1 = await http.get(f"{DOMAIN}/{code}", headers=hdrs1, timeout=_SHORT_TIMEOUT)
        cookies = dict(r1.headers.get("set-cookie", "").split("=", 1))  # minimal parse
        # Re-use the httpx client but pass cookies extracted from r1
        # We need the actual cookie jar — use httpx cookie parsing
        import httpx as _httpx
        jar: dict[str, str] = {}
        for ch in r1.headers.get_list("set-cookie") if hasattr(r1.headers, "get_list") else []:
            kv = ch.split(";")[0].strip()
            if "=" in kv:
                k, v = kv.split("=", 1)
                jar[k.strip()] = v.strip()

        r2 = await http.get(
            f"{DOMAIN}/{code}",
            headers=hdrs2,
            cookies=jar,
            timeout=_SHORT_TIMEOUT,
        )
        html = r2.text
    except NetworkError as e:
        raise DDLException(f"gyanilinks: {type(e).__name__}") from e

    soup = BeautifulSoup(html, "html.parser")
    data = {inp.get("name"): inp.get("value") for inp in soup.find_all("input")}
    await asleep(5)
    try:
        resp = await http.post(
            f"{DOMAIN}/links/go",
            data=data,
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "User-Agent": ua,
                "Referer": f"{DOMAIN}/{code}",
            },
            cookies=jar,
            timeout=_SHORT_TIMEOUT,
        )
    except NetworkError as e:
        raise DDLException(f"gyanilinks: POST failed — {e}") from e

    ct = resp.headers.get("content-type", "")
    if "application/json" in ct:
        result = _json.loads(resp.content)
        if "url" in result:
            return result["url"]
    raise DDLException("gyanilinks: no URL in response")


async def ouo(url: str) -> str:
    """
    Uses curl_cffi — ouo.press requires Chrome TLS fingerprint; neither
    httpx nor cfscrape replicates it.  Kept as-is on purpose.
    """
    from re import compile as _compile
    tempurl = url.replace("ouo.io", "ouo.press")
    p = urlparse(tempurl)
    oid = tempurl.split("/")[-1]
    client = cSession(
        headers={
            "authority": "ouo.press",
            "accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
            "cache-control": "max-age=0",
            "referer": "http://www.google.com/ig/adde?moduleurl=",
            "upgrade-insecure-requests": "1",
        }
    )
    res = client.get(tempurl, impersonate="chrome110", timeout=30)
    next_url = f"{p.scheme}://{p.hostname}/go/{oid}"

    for _ in range(2):
        if res.headers.get("Location"):
            break
        bs4 = BeautifulSoup(res.content, "lxml")
        inputs = bs4.form.findAll("input", {"name": _compile(r"token$")})
        data = {inp.get("name"): inp.get("value") for inp in inputs}
        data["x-token"] = await recaptchaV3()
        res = client.post(
            next_url,
            data=data,
            headers={"content-type": "application/x-www-form-urlencoded"},
            allow_redirects=False,
            impersonate="chrome110",
            timeout=30,
        )
        next_url = f"{p.scheme}://{p.hostname}/xreallcygo/{oid}"

    location = res.headers.get("Location")
    if not location:
        raise DDLException("ouo: no redirect Location header in response")
    return location


async def transcript(url: str, DOMAIN: str, ref: str, sltime: float) -> str:
    """
    Generic countdown-shortener bypass using httpx.
    Used by ~40 different shortener patterns in checker.py.
    """
    code = url.rstrip("/").split("/")[-1]
    ua = _MOBILE_UA
    try:
        r = await http.get(
            f"{DOMAIN}/{code}",
            headers={"Referer": ref, "User-Agent": ua},
            timeout=_SHORT_TIMEOUT,
        )
    except NetworkError as e:
        raise DDLException(f"transcript: GET failed — {type(e).__name__}") from e

    soup = BeautifulSoup(r.text, "html.parser")
    title_tag = soup.find("title")
    if title_tag and title_tag.text == "Just a moment...":
        return "Unable To Bypass Due To Cloudflare Protected"

    data = {
        inp.get("name"): inp.get("value")
        for inp in soup.find_all("input")
        if inp.get("name") and inp.get("value")
    }
    # Preserve cookies from the GET for the POST
    jar: dict[str, str] = {}
    for ch in (r.headers.get("set-cookie") or "").split("\n"):
        kv = ch.split(";")[0].strip()
        if "=" in kv:
            k, v = kv.split("=", 1)
            jar[k.strip()] = v.strip()

    await asleep(sltime)
    try:
        resp = await http.post(
            f"{DOMAIN}/links/go",
            data=data,
            headers={
                "Referer": f"{DOMAIN}/{code}",
                "X-Requested-With": "XMLHttpRequest",
                "User-Agent": ua,
            },
            cookies=jar or None,
            timeout=_SHORT_TIMEOUT,
        )
    except NetworkError as e:
        raise DDLException(f"transcript: POST failed — {type(e).__name__}") from e

    ct = resp.headers.get("content-type", "")
    if "application/json" in ct:
        result = _json.loads(resp.content)
        if "url" in result:
            return result["url"]
    raise DDLException("transcript: no URL in response")


# ═══════════════════════════════════════════════════════════════════════════════
# REMAINING RESOLVERS (cfscrape or requests — documented reasons)
# ═══════════════════════════════════════════════════════════════════════════════

async def justpaste(url: str) -> str:
    """Uses cfscrape — justpaste.it actively blocks curl/httpx user-agents."""
    try:
        resp = await cf.get(url)
    except NetworkError as e:
        raise DDLException(f"justpaste: {type(e).__name__}") from e
    soup = BeautifulSoup(resp.text, "html.parser")
    inps = soup.select('div[id="articleContent"] > p')
    parts = [p.get_text() for p in inps if p.get_text()]
    if not parts:
        raise DDLException("justpaste: no content paragraphs found")
    return ", ".join(parts)


async def linksxyz(url: str) -> str:
    """Uses httpx — plain redirect page."""
    try:
        resp = await http.get(url, timeout=_SHORT_TIMEOUT)
    except NetworkError as e:
        raise DDLException(f"linksxyz: {type(e).__name__}") from e
    soup = BeautifulSoup(resp.text, "html.parser")
    inps = soup.select('div[id="redirect-info"] > a')
    if not inps:
        raise DDLException("linksxyz: no redirect link found")
    return inps[0]["href"]


async def shareus(url: str) -> str:
    """Uses httpx — JSON API, no Cloudflare."""
    DOMAIN = "https://api.shrslink.xyz"
    code = url.split("/")[-1]
    ua = _MOBILE_UA
    try:
        r1 = await http.get(
            f"{DOMAIN}/v?shortid={code}&initial=true&referrer=",
            headers={"User-Agent": ua, "Origin": "https://shareus.io"},
            timeout=_SHORT_TIMEOUT,
        )
        r1.raise_for_status()
        sid = _json.loads(r1.content).get("sid")
    except (NetworkError, KeyError, _json.JSONDecodeError) as e:
        raise DDLException(f"shareus: {type(e).__name__}") from e
    if not sid:
        raise DDLException("shareus: ID Error")
    try:
        r2 = await http.get(
            f"{DOMAIN}/get_link?sid={sid}",
            headers={"User-Agent": ua, "Origin": "https://shareus.io"},
            timeout=_SHORT_TIMEOUT,
        )
        r2.raise_for_status()
        return _json.loads(r2.content)["link_info"]["destination"]
    except (NetworkError, KeyError, _json.JSONDecodeError) as e:
        raise DDLException(f"shareus: Link Extraction Failed — {e}") from e


async def dropbox(url: str) -> str:
    """Pure string transformation — no network call."""
    return (
        url.replace("www.", "")
        .replace("dropbox.com", "dl.dropboxusercontent.com")
        .replace("?dl=0", "")
    )


async def linkvertise(url: str) -> str:
    """Uses httpx — bypass.pm API."""
    try:
        resp = await http.get(
            "https://bypass.pm/bypass2",
            headers={"User-Agent": _MOBILE_UA},
            timeout=_SHORT_TIMEOUT,
        )
        resp.raise_for_status()
        data = _json.loads(resp.content)
    except (NetworkError, _json.JSONDecodeError) as e:
        raise DDLException(f"linkvertise: {type(e).__name__}") from e
    if data.get("success"):
        return data["destination"]
    raise DDLException(data.get("msg", "linkvertise: unknown error"))


async def rslinks(url: str) -> str:
    """Uses httpx with allow_redirects=False to read Location header."""
    try:
        resp = await http.get(
            url,
            follow_redirects=False,
            timeout=_SHORT_TIMEOUT,
        )
    except NetworkError as e:
        raise DDLException(f"rslinks: {type(e).__name__}") from e
    location = resp.headers.get("location", "")
    if not location:
        raise DDLException("rslinks: no Location header in response")
    code = location.split("ms9")[-1]
    return f"http://techyproio.blogspot.com/p/short.html?{code}=="


async def shorter(url: str) -> str:
    """
    Uses cfscrape — generic redirect follower; target sites vary wildly
    and often need browser-like headers that cfscrape provides.
    """
    try:
        resp = await cf.get(url, allow_redirects=False)
    except NetworkError as e:
        raise DDLException(f"shorter: {type(e).__name__}") from e
    location = resp.headers.get("Location") or resp.headers.get("location")
    if not location:
        raise DDLException("shorter: no Location header in response")
    return location


async def appurl(url: str) -> str:
    """Uses cfscrape — appurl sites have Cloudflare protection."""
    try:
        resp = await cf.get(url, allow_redirects=False)
    except NetworkError as e:
        raise DDLException(f"appurl: {type(e).__name__}") from e
    soup = BeautifulSoup(resp.text, "html.parser")
    items = soup.select('meta[property="og:url"]')
    if not items:
        raise DDLException("appurl: og:url meta tag not found")
    return items[0]["content"]


async def surl(url: str) -> str:
    """Uses cfscrape — surl.li uses Cloudflare."""
    try:
        resp = await cf.get(f"{url}+")
    except NetworkError as e:
        raise DDLException(f"surl: {type(e).__name__}") from e
    soup = BeautifulSoup(resp.text, "html.parser")
    items = soup.select('p[class="long-url"]')
    if not items or not items[0].string:
        raise DDLException("surl: long-url element not found")
    parts = items[0].string.split()
    if len(parts) < 2:
        raise DDLException("surl: could not parse long-url text")
    return parts[1]


async def thinfi(url: str) -> str:
    """Uses httpx — plain HTML redirect page."""
    try:
        resp = await http.get(url, timeout=_SHORT_TIMEOUT)
        resp.raise_for_status()
    except NetworkError as e:
        raise DDLException(f"thinfi: {type(e).__name__}") from e
    soup = BeautifulSoup(resp.content, "html.parser")
    try:
        return soup.p.a.get("href")
    except (AttributeError, TypeError):
        raise DDLException("thinfi: link element not found")


async def vplink(url: str) -> str:
    """
    vplink.in bypass — two-step JS-redirect extraction using httpx.

    Step 1: GET the shortener page → extract window.location.href target.
    Step 2: GET the article page → extract canonical URL (best achievable
            without a full browser session completing the task chain).

    NOTE: The canonical URL returned is the intermediate SEO article page,
    not the final Telegram/download destination.  The full destination
    requires server-side task completion which cannot be replicated via
    plain HTTP.  This is the furthest the resolver can reach without a
    browser.
    """
    ua = _MOBILE_UA
    try:
        r1 = await http.get(
            url,
            headers={"User-Agent": ua},
            timeout=_SHORT_TIMEOUT,
        )
    except NetworkError as e:
        raise DDLException(f"vplink: GET failed — {type(e).__name__}") from e

    m = _re.search(r"window\.location\.href\s*=\s*[\"']([^\"']+)[\"']", r1.text)
    if not m:
        raise DDLException("vplink: could not find redirect URL in page")
    mid_url = m.group(1)

    try:
        r2 = await http.get(
            mid_url,
            headers={"User-Agent": ua, "Referer": url},
            timeout=_SHORT_TIMEOUT,
        )
    except NetworkError as e:
        raise DDLException(f"vplink: article GET failed — {type(e).__name__}") from e

    canon = _re.search(
        r'<link\s+rel=["\']canonical["\']\s+href=["\']([^"\']+)["\']', r2.text
    )
    if canon:
        return canon.group(1)
    raise DDLException("vplink: could not find canonical URL in article page")
