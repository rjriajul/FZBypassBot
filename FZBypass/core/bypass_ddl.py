from re import findall, compile, search as re_search, DOTALL
from asyncio import sleep as asleep
from urllib.parse import quote, urlparse

from bs4 import BeautifulSoup
from cloudscraper import create_scraper
from curl_cffi.requests import Session as cSession
from requests import Session, get as rget, post as rpost
from aiohttp import ClientSession, ClientTimeout

from FZBypass import Config
from FZBypass.core.exceptions import DDLException
from FZBypass.core.recaptcha import recaptchaV3

# Default timeout (seconds) for all HTTP requests
_TIMEOUT = 15
_AIOHTTP_TIMEOUT = ClientTimeout(total=_TIMEOUT)


async def get_readable_time(seconds):
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes}m{seconds}s"


async def yandex_disk(url: str) -> str:
    cget = create_scraper().request
    try:
        return cget(
            "get",
            f"https://cloud-api.yandex.net/v1/disk/public/resources/download?public_key={url}",
            timeout=_TIMEOUT,
        ).json()["href"]
    except KeyError:
        raise DDLException("File not Found / Download Limit Exceeded")


async def mediafire(url: str):
    if final_link := findall(
        r"https?:\/\/download\d+\.mediafire\.com\/\S+\/\S+\/\S+", url
    ):
        return final_link[0]
    cget = create_scraper().request
    try:
        url = cget("get", url, timeout=_TIMEOUT).url
        page = cget("get", url, timeout=_TIMEOUT).text
    except Exception as e:
        raise DDLException(f"{e.__class__.__name__}")
    if final_link := findall(
        r"\'(https?:\/\/download\d+\.mediafire\.com\/\S+\/\S+\/\S+)\'", page
    ):
        return final_link[0]
    elif temp_link := findall(
        r'\/\/(www\.mediafire\.com\/file\/\S+\/\S+\/file\?\S+)', page
    ):
        return await mediafire("https://" + temp_link[0].strip('"'))
    else:
        raise DDLException("No links found in this page")


async def shrdsk(url: str) -> str:
    cget = create_scraper().request
    try:
        url = cget("GET", url, timeout=_TIMEOUT).url
        res = cget(
            "GET",
            f'https://us-central1-affiliate2apk.cloudfunctions.net/get_data?shortid={url.split("/")[-1]}',
            timeout=_TIMEOUT,
        )
    except Exception as e:
        raise DDLException(f"{e.__class__.__name__}")
    if res.status_code != 200:
        raise DDLException(f"Status Code {res.status_code}")
    res = res.json()
    if "type" in res and res["type"].lower() == "upload" and "video_url" in res:
        return quote(res["video_url"], safe=":/")
    raise DDLException("No Direct Link Found")


async def terabox(url: str) -> str:
    """
    Terabox bypass using the WAP page trick.
    The WAP share page embeds window.__INITIAL_STATE__ which contains the full
    file list including dlink — no jsToken, no CAPTCHA needed.
    Based on: github.com/rjriajul/terabox-downloader-api
    """
    import json as _json

    MOBILE_UA = (
        "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
    )

    def retryme(sess, url, retries=5):
        last_exc = None
        for _ in range(retries):
            try:
                return sess.get(url, headers={"User-Agent": MOBILE_UA}, timeout=_TIMEOUT)
            except Exception as e:
                last_exc = e
        raise DDLException(f"Terabox: failed to connect after {retries} retries: {last_exc}")

    # Parse surl from any Terabox URL format
    from urllib.parse import urlparse as _urlparse, parse_qs as _parse_qs
    parsed = _urlparse(url)
    if "/s/" in parsed.path:
        surl = parsed.path.split("/s/")[-1].strip("/")
    else:
        qs = _parse_qs(parsed.query)
        surl = qs.get("surl", [""])[0]

    if not surl:
        raise DDLException("Terabox: could not extract surl from URL")

    # Strip leading '1' if present (path-form URLs prepend it)
    if len(surl) > 22 and surl.startswith("1"):
        surl = surl[1:]

    # 1. Try custom Terabox Downloader API with streaming proxy support
    if Config.TERA_API_URL:
        try:
            api_res = rpost(
                f"{Config.TERA_API_URL}/download",
                json={"url": url},
                headers={"Content-Type": "application/json", "User-Agent": MOBILE_UA},
                timeout=25,
            )
            if api_res.status_code == 200:
                res_data = api_res.json()
                if res_data.get("status") == "success":
                    api_files = res_data.get("data", {}).get("files", [])
                    if api_files:
                        parse_txt = ""
                        for item in api_files:
                            name = item.get("filename", "Unknown")
                            size = item.get("size", "Unknown")
                            dl_url = item.get("proxy_url") or item.get("dlink")
                            if dl_url:
                                parse_txt += (
                                    f"\n┎ <b>File:</b> <code>{name}</code>\n"
                                    f"┠ <b>Size:</b> <code>{size}</code>\n"
                                    f"┗ <b>DDL:</b> <a href='{dl_url}'>Click Here</a>\n"
                                )
                        if parse_txt:
                            return parse_txt.strip()
        except Exception:
            pass

    sess = Session()
    _COOKIE_DOMAINS = [
        ".terabox.com", ".www.terabox.com",
        ".1024terabox.com", ".1024tera.com",
        ".teraboxapp.com", ".terabox.app",
        ".nephobox.com", ".4funbox.co",
        ".mirrobox.com", ".momerybox.com",
        ".teraboxlink.com", ".terafileshare.com",
        ".freeterabox.com", ".teraboxshare.com",
        ".terasharefile.com",
    ]
    tera_cookie = Config.TERA_COOKIE.replace("ndus=", "").strip()
    for _d in _COOKIE_DOMAINS:
        sess.cookies.set("ndus", tera_cookie, domain=_d)

    # Try WAP page on multiple domains
    html = None
    for wap_url in [
        f"http://www.terabox.com/wap/share/filelist?surl={surl}",
        f"https://www.1024terabox.com/wap/share/filelist?surl={surl}",
        f"https://www.teraboxapp.com/wap/share/filelist?surl={surl}",
        f"https://www.nephobox.com/wap/share/filelist?surl={surl}",
        f"https://www.4funbox.co/wap/share/filelist?surl={surl}",
        f"https://www.mirrobox.com/wap/share/filelist?surl={surl}",
        f"https://www.momerybox.com/wap/share/filelist?surl={surl}",
        f"https://www.terasharefile.com/wap/share/filelist?surl={surl}",
    ]:
        try:
            res = retryme(sess, wap_url)
            if res.status_code == 200 and "__INITIAL_STATE__" in res.text:
                html = res.text
                break
        except DDLException:
            continue

    if not html:
        raise DDLException("Terabox: could not load WAP page — check TERA_COOKIE")

    # Extract window.__INITIAL_STATE__ JSON
    m = re_search(r'window\.__INITIAL_STATE__\s*=\s*(\{.+?\})\s*(?:;|</script>)', html, DOTALL)

    file_list = []
    if m:
        try:
            state = _json.loads(m.group(1))
            file_list = state.get("share", {}).get("fileList", [])
        except Exception:
            pass

    if not file_list:
        # Fallback: parse fileList array directly
        fl_m = re_search(r'"fileList"\s*:\s*(\[.+?\])\s*,\s*"', html, DOTALL)
        if fl_m:
            try:
                file_list = _json.loads(fl_m.group(1))
            except Exception:
                pass

    if not file_list:
        raise DDLException("Terabox: no files found in WAP page — link may be expired or private")

    # Filter out folders
    files = [f for f in file_list if str(f.get("isdir", "0")) != "1"]
    if not files:
        raise DDLException("Terabox: share contains only folders")

    def _human_size(b: int) -> str:
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if b < 1024:
                return f"{b:.2f} {unit}"
            b /= 1024
        return f"{b:.2f} PB"

    # Helper to resolve redirect using the authenticated session to get public CDN URL
    def _resolve_direct_url(raw_dlink: str) -> str:
        if not raw_dlink:
            return ""
        try:
            head_res = sess.head(raw_dlink, headers={"User-Agent": MOBILE_UA}, allow_redirects=True, timeout=_TIMEOUT)
            if head_res.url and head_res.url != raw_dlink:
                return head_res.url
        except Exception:
            pass
        return raw_dlink

    # Build formatted output for all files
    parse_txt = ""
    for item in files:
        dlink = item.get("dlink", "")
        name = item.get("server_filename", "Unknown")
        size = _human_size(int(item.get("size", 0)))
        
        if not dlink:
            parse_txt += (
                f"\n┎ <b>File:</b> <code>{name}</code>\n"
                f"┠ <b>Size:</b> <code>{size}</code>\n"
                f"┗ <b>DDL:</b> Unavailable — check TERA_COOKIE\n"
            )
        else:
            final_dl = _resolve_direct_url(dlink)
            parse_txt += (
                f"\n┎ <b>File:</b> <code>{name}</code>\n"
                f"┠ <b>Size:</b> <code>{size}</code>\n"
                f"┗ <b>DDL:</b> <a href='{final_dl}'>Click Here</a>\n"
            )

    if not parse_txt:
        raise DDLException("Terabox: no dlink found — check TERA_COOKIE")

    return parse_txt.strip()


async def try2link(url: str) -> str:
    DOMAIN = 'https://try2link.com'
    code = url.split('/')[-1]

    async with ClientSession(timeout=_AIOHTTP_TIMEOUT) as session:
        html = None
        referers = ['https://hightrip.net/', 'https://to-travel.net/', 'https://world2our.com/']
        for referer in referers:
            async with session.get(f'{DOMAIN}/{code}', headers={"Referer": referer}) as res:
                if res.status == 200:
                    html = await res.text()
                    break
        if html is None:
            raise DDLException("try2link: failed to fetch page")
        soup = BeautifulSoup(html, "html.parser")
        go_link = soup.find(id="go-link")
        if not go_link:
            raise DDLException("try2link: go-link form not found")
        inputs = go_link.find_all(name="input")
        data = {inp.get('name'): inp.get('value') for inp in inputs}
        await asleep(6)
        async with session.post(
            f"{DOMAIN}/links/go", data=data,
            headers={"X-Requested-With": "XMLHttpRequest"},
        ) as resp:
            ct = resp.headers.get('Content-Type', '')
            if 'application/json' in ct:
                json_data = await resp.json()
                try:
                    return json_data['url']
                except KeyError:
                    raise DDLException("try2link: 'url' key missing in response")
            raise DDLException(f"try2link: unexpected content-type: {ct}")


async def gyanilinks(url: str) -> str:
    """
    Based on https://github.com/whitedemon938/Bypass-Scripts
    """
    code = url.split('/')[-1]
    useragent = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
    DOMAIN = "https://go.bloggingaro.com"

    async with ClientSession(timeout=_AIOHTTP_TIMEOUT) as session:
        async with session.get(
            f"{DOMAIN}/{code}",
            headers={'Referer': 'https://tech.hipsonyc.com/', 'User-Agent': useragent},
        ) as res:
            cookies = res.cookies
            html = await res.text()
        async with session.get(
            f"{DOMAIN}/{code}",
            headers={'Referer': 'https://hipsonyc.com/', 'User-Agent': useragent},
            cookies=cookies,
        ) as resp:
            html = await resp.text()
        soup = BeautifulSoup(html, 'html.parser')
        data = {inp.get('name'): inp.get('value') for inp in soup.find_all('input')}
        await asleep(5)
        async with session.post(
            f"{DOMAIN}/links/go", data=data,
            headers={'X-Requested-With': 'XMLHttpRequest', 'User-Agent': useragent, 'Referer': f"{DOMAIN}/{code}"},
            cookies=cookies,
        ) as links:
            ct = links.headers.get('Content-Type', '')
            if 'application/json' in ct:
                try:
                    return (await links.json())['url']
                except (KeyError, Exception):
                    raise DDLException("gyanilinks: link extraction failed")
            raise DDLException(f"gyanilinks: unexpected content-type: {ct}")


async def ouo(url: str):
    tempurl = url.replace("ouo.io", "ouo.press")
    p = urlparse(tempurl)
    id = tempurl.split("/")[-1]
    client = cSession(
        headers={
            "authority": "ouo.press",
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
            "cache-control": "max-age=0",
            "referer": "http://www.google.com/ig/adde?moduleurl=",
            "upgrade-insecure-requests": "1",
        }
    )
    res = client.get(tempurl, impersonate="chrome110", timeout=_TIMEOUT)
    next_url = f"{p.scheme}://{p.hostname}/go/{id}"

    for _ in range(2):
        if res.headers.get("Location"):
            break
        bs4 = BeautifulSoup(res.content, "lxml")
        inputs = bs4.form.findAll("input", {"name": compile(r"token$")})
        data = {inp.get("name"): inp.get("value") for inp in inputs}
        data["x-token"] = await recaptchaV3()
        res = client.post(
            next_url,
            data=data,
            headers={"content-type": "application/x-www-form-urlencoded"},
            allow_redirects=False,
            impersonate="chrome110",
            timeout=_TIMEOUT,
        )
        next_url = f"{p.scheme}://{p.hostname}/xreallcygo/{id}"

    return res.headers.get("Location")


async def transcript(url: str, DOMAIN: str, ref: str, sltime) -> str:
    code = url.rstrip("/").split("/")[-1]
    useragent = 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'

    async with ClientSession(timeout=_AIOHTTP_TIMEOUT) as session:
        async with session.get(
            f"{DOMAIN}/{code}",
            headers={'Referer': ref, 'User-Agent': useragent},
        ) as res:
            html = await res.text()
            cookies = res.cookies
        soup = BeautifulSoup(html, "html.parser")
        title_tag = soup.find('title')
        if title_tag and title_tag.text == 'Just a moment...':
            raise DDLException("Unable to bypass: Cloudflare protected")
        data = {
            inp.get('name'): inp.get('value')
            for inp in soup.find_all('input')
            if inp.get('name') and inp.get('value')
        }
        await asleep(sltime)
        async with session.post(
            f"{DOMAIN}/links/go", data=data,
            headers={
                'Referer': f"{DOMAIN}/{code}",
                'X-Requested-With': 'XMLHttpRequest',
                'User-Agent': useragent,
            },
            cookies=cookies,
        ) as resp:
            ct = resp.headers.get('Content-Type', '')
            if 'application/json' in ct:
                try:
                    return (await resp.json())['url']
                except (KeyError, Exception):
                    raise DDLException("transcript: link extraction failed")
            raise DDLException(f"transcript: unexpected content-type: {ct}")


async def justpaste(url: str):
    resp = rget(url, verify=False, timeout=_TIMEOUT)
    soup = BeautifulSoup(resp.text, "html.parser")
    inps = soup.select('div[id="articleContent"] > p')
    return ", ".join(elem.string for elem in inps)


async def linksxyz(url: str):
    resp = rget(url, timeout=_TIMEOUT)
    soup = BeautifulSoup(resp.text, "html.parser")
    inps = soup.select('div[id="redirect-info"] > a')
    return inps[0]["href"]


async def shareus(url: str) -> str:
    DOMAIN = "https://api.shrslink.xyz"
    code = url.split('/')[-1]
    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
        'Origin': 'https://shareus.io',
    }
    api = f"{DOMAIN}/v?shortid={code}&initial=true&referrer="
    sid = rget(api, headers=headers, timeout=_TIMEOUT).json()['sid']
    if sid:
        res = rget(f"{DOMAIN}/get_link?sid={sid}", headers=headers, timeout=_TIMEOUT)
        if res.ok:
            return res.json()['link_info']['destination']
        raise DDLException("shareus: link extraction failed")
    raise DDLException("shareus: ID error")


async def dropbox(url: str) -> str:
    return (
        url.replace("www.", "")
        .replace("dropbox.com", "dl.dropboxusercontent.com")
        .replace("?dl=0", "")
    )


async def linkvertise(url: str) -> str:
    resp = rget("https://bypass.pm/bypass2", params={"url": url}, timeout=_TIMEOUT).json()
    if resp["success"]:
        return resp["destination"]
    raise DDLException(resp["msg"])


async def rslinks(url: str) -> str:
    resp = rget(url, stream=True, allow_redirects=False, timeout=_TIMEOUT)
    try:
        code = resp.headers["location"].split("ms9")[-1]
        return f"http://techyproio.blogspot.com/p/short.html?{code}=="
    except (KeyError, IndexError):
        raise DDLException("rslinks: link extraction failed")


async def shorter(url: str) -> str:
    try:
        cget = create_scraper().request
        resp = cget("GET", url, allow_redirects=False, timeout=_TIMEOUT)
        return resp.headers["Location"]
    except Exception:
        raise DDLException("shorter: link extraction failed")


async def appurl(url: str):
    cget = create_scraper().request
    resp = cget("GET", url, allow_redirects=False, timeout=_TIMEOUT)
    soup = BeautifulSoup(resp.text, "html.parser")
    return soup.select('meta[property="og:url"]')[0]["content"]


async def surl(url: str):
    cget = create_scraper().request
    resp = cget("GET", f"{url}+", timeout=_TIMEOUT)
    soup = BeautifulSoup(resp.text, "html.parser")
    return soup.select('p[class="long-url"]')[0].string.split()[1]


async def thinfi(url: str) -> str:
    try:
        return BeautifulSoup(rget(url, timeout=_TIMEOUT).content, "html.parser").p.a.get("href")
    except Exception:
        raise DDLException("thinfi: link extraction failed")


async def _playwright_final_url(
    url: str,
    *,
    wait_until: str = "networkidle",
    timeout_ms: int = 30000,
    stop_domains: list[str] | None = None,
) -> str:
    """
    Launch a headless Chromium via playwright, navigate to `url`, wait for
    the redirect chain to settle, and return the final URL.

    Only used as a last resort — requires playwright to be installed.
    On free-tier deployments without playwright, raises DDLException gracefully.

    stop_domains: if the browser lands on any of these domains, stop early
    and return that URL immediately (avoids waiting on known dead-end ad pages).
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise DDLException("playwright not installed — cannot bypass JS-rendered page")

    stop_domains = stop_domains or []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            java_script_enabled=True,
        )
        page = await ctx.new_page()
        final = {"url": url}

        def _on_navigate(frame):
            if frame == page.main_frame:
                final["url"] = frame.url

        page.on("framenavigated", _on_navigate)

        try:
            await page.goto(url, wait_until=wait_until, timeout=timeout_ms)
        except Exception:
            pass  # timeout or navigation error — use whatever URL we landed on

        result = page.url or final["url"]

        # If we landed on a known dead-end ad domain, raise immediately
        for dead in stop_domains:
            if dead in result:
                await browser.close()
                raise DDLException(f"Landed on dead-end ad page: {result}")

        await browser.close()
        return result


async def vplink(url: str) -> str:
    """
    vplink.in — multi-hop ad chain that goes through hittracks, entiredust, etc.
    before landing on the final URL. Use playwright to follow the full chain.
    Waits up to 90 seconds for all redirects to complete.
    """
    _AD_DOMAINS = [
        "hittracks.in.net",
        "entiredust.in",
        "studyeducations",
        "studiissinsuarcness",
        "studyscholorhiipss",
        "vplink.in",
    ]

    try:
        from playwright.async_api import async_playwright
        from asyncio import sleep as asleep

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            ctx = await browser.new_context(
                user_agent="Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
                java_script_enabled=True,
            )
            page = await ctx.new_page()
            visited = []

            def _on_nav(frame):
                if frame == page.main_frame and frame.url.startswith("http"):
                    if not visited or visited[-1] != frame.url:
                        visited.append(frame.url)

            page.on("framenavigated", _on_nav)

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except Exception:
                pass

            # Wait up to 90 seconds polling every second for the chain to complete
            for _ in range(90):
                current = page.url
                if not any(d in current for d in _AD_DOMAINS):
                    break
                await asleep(1)

            final = page.url
            await browser.close()

            # Return last non-ad URL from visited history
            for u in reversed(visited):
                if not any(d in u for d in _AD_DOMAINS):
                    return u

            if final and not any(d in final for d in _AD_DOMAINS):
                return final

            raise DDLException("vplink: redirect chain did not resolve to a final URL")

    except ImportError:
        # No playwright — return the first redirect URL as a best-effort result
        code = url.rstrip("/").split("/")[-1]
        useragent = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
        client = cSession()
        res = client.get(
            f"https://vplink.in/{code}",
            headers={"Referer": "https://google.com", "User-Agent": useragent},
            impersonate="chrome120",
            timeout=_TIMEOUT,
        )
        soup = BeautifulSoup(res.content, "html.parser")
        a = soup.find("a", href=True)
        if a and a["href"].startswith("http"):
            return a["href"]
        raise DDLException("vplink: playwright not installed and no redirect found")


async def hittracks(url: str) -> str:
    """
    hittracks.in.net / entiredust.in — multi-hop ad chains.
    Use playwright to follow all redirects to the final destination.
    """
    _AD_DOMAINS = [
        "hittracks.in.net",
        "entiredust.in",
        "studyeducations",
        "studiissinsuarcness",
        "studyscholorhiipss",
    ]

    try:
        from playwright.async_api import async_playwright
        from asyncio import sleep as asleep

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            ctx = await browser.new_context(
                user_agent="Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
                java_script_enabled=True,
            )
            page = await ctx.new_page()
            visited = []

            def _on_nav(frame):
                if frame == page.main_frame and frame.url.startswith("http"):
                    if not visited or visited[-1] != frame.url:
                        visited.append(frame.url)

            page.on("framenavigated", _on_nav)

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except Exception:
                pass

            for _ in range(90):
                current = page.url
                if not any(d in current for d in _AD_DOMAINS):
                    break
                await asleep(1)

            final = page.url
            await browser.close()

            for u in reversed(visited):
                if not any(d in u for d in _AD_DOMAINS):
                    return u

            if final and not any(d in final for d in _AD_DOMAINS):
                return final

            raise DDLException("hittracks: redirect chain did not resolve to a final URL")

    except ImportError:
        raise DDLException("hittracks: playwright not installed")


async def vcloud(url: str) -> str:
    """
    vcloud.fit — use the free PBX1 public API, fall back to playwright if available.
    """
    # Try free public API first
    try:
        api_url = f"https://pbx1botapi.vercel.app/api/vcloud?url={url}"
        async with ClientSession(timeout=_AIOHTTP_TIMEOUT) as session:
            async with session.get(api_url) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    link = data.get("url") or data.get("link") or data.get("download")
                    if link and link.startswith("http"):
                        return link
    except Exception:
        pass

    # Playwright fallback
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            ctx = await browser.new_context(
                user_agent="Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
            )
            page = await ctx.new_page()
            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
            except Exception:
                pass
            for selector in ['a[href*="download"]', 'a[id*="download"]', 'a[class*="download"]', 'a[href*="/d/"]', 'a[href*="/file/"]']:
                try:
                    el = await page.query_selector(selector)
                    if el:
                        href = await el.get_attribute("href")
                        if href and href.startswith("http"):
                            await browser.close()
                            return href
                except Exception:
                    continue
            final = page.url
            await browser.close()
            if final and final != url and final.startswith("http"):
                return final
    except ImportError:
        pass

    # curl_cffi scrape fallback
    from re import search as rsearch
    useragent = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
    client = cSession()
    res = client.get(url, headers={"User-Agent": useragent}, impersonate="chrome120", timeout=_TIMEOUT)
    soup = BeautifulSoup(res.content, "html.parser")
    for selector in ['a[href*="download"]', 'a[id*="download"]', 'a[class*="download"]', 'a[href*="/d/"]', 'a[href*="/file/"]']:
        tag = soup.select_one(selector)
        if tag and tag.get("href", "").startswith("http"):
            return tag["href"]
    m = rsearch(r'window\.location(?:\.href)?\s*=\s*["\x27](https?://[^"\']+)["\x27]', res.text)
    if m:
        return m.group(1)

    raise DDLException("vcloud: no download link found")


async def dotflix(url: str) -> str:
    """
    dotflix.store/share/ — JS-rendered GDrive wrapper.
    Uses playwright if available, otherwise curl_cffi scrape.
    """
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            ctx = await browser.new_context(
                user_agent="Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
            )
            page = await ctx.new_page()
            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
            except Exception:
                pass
            for selector in ['a[href*="drive.google.com"]', 'a[href*="download"]', 'a[id*="download"]', 'a[class*="download"]', 'a[href*="/d/"]']:
                try:
                    el = await page.query_selector(selector)
                    if el:
                        href = await el.get_attribute("href")
                        if href and href.startswith("http"):
                            await browser.close()
                            return href
                except Exception:
                    continue
            final = page.url
            await browser.close()
            if final and final != url and final.startswith("http"):
                return final
    except ImportError:
        pass

    # Lightweight fallback
    from re import search as rsearch
    useragent = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
    client = cSession()
    res = client.get(url, headers={"User-Agent": useragent}, impersonate="chrome120", timeout=_TIMEOUT)
    soup = BeautifulSoup(res.content, "html.parser")
    for selector in ['a[href*="drive.google.com"]', 'a[href*="download"]', 'a[id*="download"]', 'a[class*="download"]', 'a[href*="/d/"]']:
        tag = soup.select_one(selector)
        if tag and tag.get("href", "").startswith("http"):
            return tag["href"]
    m = rsearch(r'window\.location(?:\.href)?\s*=\s*["\x27](https?://[^"\']+)["\x27]', res.text)
    if m:
        return m.group(1)

    raise DDLException("dotflix: no download link found")
