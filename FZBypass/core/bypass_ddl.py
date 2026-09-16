from re import findall, compile
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
    sess = Session()

    def retryme(url, retries=5):
        last_exc = None
        for _ in range(retries):
            try:
                return sess.get(url, timeout=_TIMEOUT)
            except Exception as e:
                last_exc = e
        raise DDLException(f"Terabox: failed to connect after {retries} retries: {last_exc}")

    url = retryme(url).url
    key = url.split("?surl=")[-1]
    url = f"http://www.terabox.com/wap/share/filelist?surl={key}"
    sess.cookies.update({"ndus": Config.TERA_COOKIE})

    res = retryme(url)
    key = res.url.split("?surl=")[-1]
    soup = BeautifulSoup(res.content, "lxml")
    jsToken = None

    for fs in soup.find_all("script"):
        fstring = fs.string
        if fstring and fstring.startswith("try {eval(decodeURIComponent"):
            jsToken = fstring.split("%22")[1]

    res = retryme(
        f"https://www.terabox.com/share/list?app_id=250528&jsToken={jsToken}&shorturl={key}&root=1"
    )
    result = res.json()
    if result["errno"] != 0:
        raise DDLException(f"{result['errmsg']} — Check cookies")
    result = result["list"]
    if len(result) > 1:
        raise DDLException("Can't download multiple files")
    result = result[0]

    if result["isdir"] != "0":
        raise DDLException("Can't download folder")
    try:
        return result["dlink"]
    except Exception:
        raise DDLException("Link Extraction Failed")


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


async def vplink(url: str) -> str:
    """
    vplink.in — try a direct API call first using the short code,
    then fall back to scraping the <a href> from the page.
    """
    code = url.rstrip("/").split("/")[-1]
    useragent = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
    domain = "https://vplink.in"

    client = cSession()

    # First try: direct POST to /links/go using the short code
    # (same pattern as transcript-style shorteners, but with curl_cffi for TLS)
    try:
        res = client.get(
            f"{domain}/{code}",
            headers={"Referer": "https://insurance.findgptprompts.com/", "User-Agent": useragent},
            impersonate="chrome120",
            timeout=_TIMEOUT,
        )
        soup = BeautifulSoup(res.content, "html.parser")

        # Check for Cloudflare
        title = soup.find("title")
        if title and "just a moment" in title.text.lower():
            raise DDLException("vplink: Cloudflare protected")

        # Try form-based POST first (transcript-style)
        data = {
            inp.get("name"): inp.get("value")
            for inp in soup.find_all("input")
            if inp.get("name") and inp.get("value")
        }
        if data:
            await asleep(5)
            resp = client.post(
                f"{domain}/links/go",
                data=data,
                headers={
                    "Referer": f"{domain}/{code}",
                    "X-Requested-With": "XMLHttpRequest",
                    "User-Agent": useragent,
                },
                impersonate="chrome120",
                timeout=_TIMEOUT,
            )
            if "application/json" in resp.headers.get("Content-Type", ""):
                try:
                    return resp.json()["url"]
                except (KeyError, Exception):
                    pass

        # Fallback: extract <a href> direct redirect
        a = soup.find("a", href=True)
        if a and a["href"].startswith("http"):
            # The <a href> points to hittracks which is an ad page.
            # Extract the original code from the hittracks URL and call its API directly.
            href = a["href"]
            from re import search as rsearch
            # Look for the real short code in the hittracks query string
            m = rsearch(r'[?&](?:insurancessstudiiss|code|id|key)=([A-Za-z0-9]+)', href)
            if m:
                short_code = m.group(1)
                # Try calling the vplink API directly with the code
                api_resp = client.get(
                    f"{domain}/api/{short_code}",
                    headers={"User-Agent": useragent},
                    impersonate="chrome120",
                    timeout=_TIMEOUT,
                )
                if api_resp.status_code == 200:
                    try:
                        return api_resp.json().get("url") or api_resp.json().get("destination")
                    except Exception:
                        pass
            return href

    except DDLException:
        raise
    except Exception as e:
        raise DDLException(f"vplink: {e.__class__.__name__}")


async def hittracks(url: str) -> str:
    """
    hittracks.in.net is an ad landing page for vplink.in links.
    The real destination is stored on vplink.in — extract the uiso ID
    from the hittracks URL and call the vplink API directly.
    """
    from re import search as rsearch
    useragent = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"

    # Extract the original short code and uiso from the URL
    # e.g. ?insurancessstudiiss=dOUZ&uiso=24331
    code_m = rsearch(r'[?&](?:insurancessstudiiss|code|id|key)=([A-Za-z0-9]+)', url)
    uiso_m = rsearch(r'[?&]uiso=([0-9]+)', url)

    if code_m and uiso_m:
        short_code = code_m.group(1)
        uiso = uiso_m.group(1)
        client = cSession()

        # Try known vplink API patterns with the code and uiso
        for api_url in [
            f"https://vplink.in/api/get?code={short_code}&id={uiso}",
            f"https://vplink.in/api?code={short_code}&uiso={uiso}",
            f"https://vplink.in/go?code={short_code}&uiso={uiso}",
            f"https://vplink.in/links/get?code={short_code}&id={uiso}",
        ]:
            try:
                resp = client.get(api_url, headers={"User-Agent": useragent}, impersonate="chrome120", timeout=_TIMEOUT)
                if resp.status_code == 200 and "application/json" in resp.headers.get("Content-Type", ""):
                    data = resp.json()
                    dest = data.get("url") or data.get("destination") or data.get("link")
                    if dest and dest.startswith("http"):
                        return dest
            except Exception:
                continue

    # Fallback: fetch the hittracks page and extract window.location.href
    async with ClientSession(timeout=_AIOHTTP_TIMEOUT) as session:
        async with session.get(
            url,
            headers={"Referer": "https://insurance.findgptprompts.com/", "User-Agent": useragent},
        ) as res:
            html = await res.text()

    match = rsearch(r'window\.location\.href\s*=\s*"(https?://[^"]+)"', html)
    if match:
        redirect = match.group(1)
        # Skip the fake study article pages — they are dead ends
        if "studyeducations" not in redirect:
            return redirect

    soup = BeautifulSoup(html, "html.parser")
    a = soup.find("a", href=True)
    if a and a["href"].startswith("http") and "studyeducations" not in a["href"]:
        return a["href"]

    raise DDLException("hittracks: could not extract final destination")


async def vcloud(url: str) -> str:
    """
    vcloud.fit — direct file host. Scrape the download link.
    """
    from re import search as rsearch
    from FZBypass import LOGGER
    useragent = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"

    client = cSession()
    res = client.get(url, headers={"User-Agent": useragent}, impersonate="chrome120", timeout=_TIMEOUT)
    LOGGER.warning("vcloud DEBUG html: %s", res.text[:2000])

    soup = BeautifulSoup(res.content, "html.parser")
    for selector in ['a[href*="download"]', 'a[id*="download"]', 'a[class*="download"]', 'a[href*="/d/"]', 'a[href*="/file/"]']:
        tag = soup.select_one(selector)
        if tag and tag.get("href", "").startswith("http"):
            return tag["href"]

    match = rsearch(r'window\.location(?:\.href)?\s*=\s*["\x27](https?://[^"\']+)["\x27]', res.text)
    if match:
        return match.group(1)

    raise DDLException("vcloud: no download link found")


async def dotflix(url: str) -> str:
    """
    dotflix.store/share/ — JS-rendered GDrive wrapper.
    """
    from re import search as rsearch
    from FZBypass import LOGGER
    useragent = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"

    client = cSession()
    res = client.get(url, headers={"User-Agent": useragent}, impersonate="chrome120", timeout=_TIMEOUT)
    LOGGER.warning("dotflix DEBUG html: %s", res.text[:2000])

    soup = BeautifulSoup(res.content, "html.parser")
    for selector in ['a[href*="drive.google.com"]', 'a[href*="download"]', 'a[id*="download"]', 'a[class*="download"]', 'a[href*="/d/"]']:
        tag = soup.select_one(selector)
        if tag and tag.get("href", "").startswith("http"):
            return tag["href"]

    match = rsearch(r'window\.location(?:\.href)?\s*=\s*["\x27](https?://[^"\']+)["\x27]', res.text)
    if match:
        return match.group(1)

    raise DDLException("dotflix: no download link found")
