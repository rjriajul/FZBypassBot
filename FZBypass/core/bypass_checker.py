from re import match
from urllib.parse import urlparse
from functools import partial
from typing import Callable

from FZBypass.core.bypass_dlinks import *
from FZBypass.core.bypass_ddl import *
from FZBypass.core.bypass_scrape import *
from FZBypass.core.bot_utils import get_dl
from FZBypass.core.exceptions import DDLException

fmed_list = [
    "fembed.net",
    "fembed.com",
    "femax20.com",
    "fcdn.stream",
    "feurl.com",
    "layarkacaxxi.icu",
    "naniplay.nanime.in",
    "naniplay.nanime.biz",
    "naniplay.com",
    "mm9842.com",
]


def is_share_link(url):
    return bool(
        match(
            r"https?:\/\/.+\.(gdtot|filepress|pressbee|gdflix)\.\S+|https?:\/\/(gdflix|filepress|pressbee|onlystream|filebee|appdrive)\.\S+",
            url,
        )
    )


def is_excep_link(url):
    return bool(
        match(
            r"https?:\/\/.+\.(1tamilmv|gdtot|filepress|pressbee|gdflix|sharespark)\.\S+|https?:\/\/(sharer|onlystream|hubdrive|katdrive|drivefire|skymovieshd|toonworld4all|kayoanime|cinevood|gdflix|filepress|pressbee|filebee|appdrive)\.\S+",
            url,
        )
    )


def _t(domain: str, ref: str, sltime) -> Callable:
    """Shorthand: return a partial transcript coroutine for the registry."""
    return partial(transcript, DOMAIN=domain, ref=ref, sltime=sltime)


# ---------------------------------------------------------------------------
# Registry: list of (regex_pattern, handler_or_partial)
#
# Entries that return final results (file hosters, DL sites, DL links) use
# a sentinel marker "_DIRECT" = True by convention — they are stored as
# 3-tuples: (pattern, handler, True).  DDL shorteners that need chaining are
# 2-tuples: (pattern, handler).
#
# Entries are checked top-to-bottom; first match wins.
# ---------------------------------------------------------------------------

# 3-tuple = direct return, 2-tuple = chainable DDL shortener
_REGISTRY: list[tuple] = [
    # ── File Hosters (direct) ───────────────────────────────────────────────
    (r"https?://(yadi|disk\.yandex)\.\S+",                  yandex_disk,        True),
    (r"https?://.+\.mediafire\.\S+",                         mediafire,          True),
    (r"https?://shrdsk\.\S+",                                shrdsk,             True),
    # terabox handled separately via domain check (see direct_link_checker)

    # ── DDL Shorteners (chainable) ──────────────────────────────────────────
    (r"https?://try2link\.\S+",                              try2link),
    (r"https?://(gyanilinks|gtlinks)\.\S+",                  gyanilinks),
    (r"https?://adrinolinks\.\S+",                           _t("https://adrinolinks.in",                    "https://bhojpuritop.in/",                  8)),
    (r"https?://adsfly\.\S+",                                _t("https://go.adsfly.in/",                    "https://letest25.co/",                     3)),
    (r"https?://(.+\.)?anlinks\.\S+",                        _t("https://anlinks.in/",                      "https://dsblogs.fun/",                     8)),
    (r"https?://ronylink\.\S+",                              _t("https://go.ronylink.com/",                 "https://livejankari.com/",                 3)),
    (r"https?://.+\.evolinks\.\S+",                          None),   # special: uses link as ref — handled inline
    (r"https?://.+\.tnshort\.\S+",                           _t("https://news.sagenews.in/",                "https://movies.djnonstopmusic.in/",         5)),
    (r"https?://(xpshort|push\.bdnewsx|techymozo)\.\S+",    _t("https://xpshort.com/",                     "https://www.comptegratuite.com/",           4.9)),
    (r"https?://go\.lolshort\.\S+",                          _t("https://get.lolshort.tech/",               "https://tech.animezia.com/",               8)),
    (r"https?://onepagelink\.\S+",                           _t("https://go.onepagelink.in/",               "https://gorating.in/",                     3.1)),
    (r"https?://earn\.moneykamalo\.\S+",                     _t("https://go.moneykamalo.com/",              "https://bloging.techkeshri.com/",           4)),
    (r"https?://droplink\.\S+",                              _t("https://droplink.co/",                     "https://yoshare.net/",                     3.1)),
    (r"https?://tinyfy\.\S+",                                _t("https://tinyfy.in",                        "https://www.yotrickslog.tech/",             0)),
    (r"https?://krownlinks\.\S+",                            _t("https://go.hostadviser.net/",              "blog.hostadviser.net/",                    8)),
    (r"https?://(du-link|dulink)\.\S+",                      _t("https://du-link.in",                       "https://profitshort.com/",                 0)),
    (r"https?://indianshortner\.\S+",                        _t("https://indianshortner.com/",              "https://moddingzone.in/",                  5)),
    (r"https?://m\.easysky\.\S+",                            _t("https://vip.linkbnao.com",                 "https://ffworld.xyz/",                     2)),
    (r"https?://.+\.tnlink\.\S+",                            _t("https://news.sagenews.in/",                "https://knowstuff.in/",                    5)),
    (r"https?://link4earn\.\S+",                             _t("https://link4earn.com",                    "https://studyis.xyz/",                     6)),
    (r"https?://shortingly\.\S+",                            _t("https://go.blogytube.com/",                "https://blogytube.com/",                   5)),
    (r"https?://short2url\.\S+",                             _t("https://techyuth.xyz/blog",                "https://blog.coin2pay.xyz/",               10)),
    (r"https?://urlsopen\.\S+",                              _t("https://s.humanssurvival.com/",            "https://1topjob.xyz/",                     5)),
    (r"https?://mdisk\.\S+",                                 _t("https://mdisk.pro",                        "https://www.meclipstudy.in/",              5)),
    (r"https?://(pkin|go\.paisakamalo)\.\S+",                _t("https://go.paisakamalo.in",                "https://healthtips.techkeshri.com/",       5)),
    (r"https?://linkpays\.\S+",                              _t("https://tech.smallinfo.in/Gadget/",        "https://finance.filmypoints.in/",           6)),
    (r"https?://sklinks\.\S+",                               _t("https://sklinks.in",                       "https://dailynew.online/",                 5)),
    (r"https?://link1s\.\S+",                                _t("https://link1s.com",                       "https://anhdep24.com/",                    9)),
    (r"https?://tulinks\.\S+",                               _t("https://tulinks.one",                      "https://www.blogger.com/",                 8)),
    (r"https?://.+\.tulinks\.\S+",                           _t("https://go.tulinks.online",                "https://tutelugu.co/",                     8)),
    (r"https?://(.+\.)?vipurl\.\S+",                         _t("https://count.vipurl.in/",                 "https://kiss6kartu.in/",                   5)),
    (r"https?://indyshare\.\S+",                             _t("https://indyshare.net",                    "https://insurancewolrd.in/",               3.1)),
    (r"https?://linkyearn\.\S+",                             _t("https://linkyearn.com",                    "https://gktech.uk/",                       5)),
    (r"https?://earn4link\.\S+",                             _t("https://m.open2get.in/",                   "https://ezeviral.com/",                    8)),
    (r"https?://linksly\.\S+",                               _t("https://go.linksly.co/",                   "https://en.themezon.net/",                 5)),
    (r"https?://(.+\.)?mdiskshortner\.\S+",                  _t("https://mdiskshortner.link",               "https://yosite.net/",                      0)),
    (r"https?://(?:\w+\.)?rocklinks\.\S+",                   _t("https://land.povathemes.com/",             "https://blog.disheye.com/",                4.9)),
    (r"https?://mplaylink\.\S+",                             _t("https://tera-box.cloud/",                  "https://mvplaylink.in.net/",               5)),
    (r"https?://shrinke\.\S+",                               _t("https://en.shrinke.me/",                   "https://themezon.net/",                    15)),
    (r"https?://urlspay\.\S+",                               _t("https://finance.smallinfo.in/",            "https://tech.filmypoints.in/",             5)),
    (r"https?://.+\.tnvalue\.\S+",                           _t("https://page.finclub.in/",                 "https://finclub.in/",                      8)),
    (r"https?://sxslink\.\S+",                               _t("https://getlink.sxslink.com/",             "https://cinemapettai.in/",                 5)),
    (r"https?://moneycase\.\S+",                             _t("https://last.moneycase.link/",             "https://www.infokeeda.xyz/",               3.1)),
    (r"https?://urllinkshort\.\S+",                          _t("https://web.urllinkshort.in",              "https://suntechu.in/",                     5)),
    (r"https?://.+\.dtglinks\.\S+",                          _t("https://happyfiles.dtglinks.in/",          "https://tech.filohappy.in/",               5)),
    (r"https?://v2links\.\S+",                               _t("https://vzu.us/",                          "https://newsbawa.com/",                    5)),
    (r"https?://(.+\.)?kpslink\.\S+",                        _t("https://kpslink.in/",                      "https://infotamizhan.xyz/",                3.1)),
    (r"https?://v2\.kpslink\.\S+",                           _t("https://v2.kpslink.in/",                   "https://infotamizhan.xyz/",                5)),
    (r"https?://tamizhmasters\.\S+",                         _t("https://tamizhmasters.com/",               "https://pokgames.com/",                    5)),
    (r"https?://tglink\.\S+",                                _t("https://tglink.in/",                       "https://www.proappapk.com/",               5)),
    (r"https?://pandaznetwork\.\S+",                         _t("https://pandaznetwork.com/",               "https://panda.freemodsapp.xyz/",           5)),
    (r"https?://url4earn\.\S+",                              _t("https://go.url4earn.in/",                  "https://techminde.com/",                   8)),
    (r"https?://ez4short\.\S+",                              _t("https://ez4short.com/",                    "https://ez4mods.com/",                     5)),
    (r"https?://dalink\.\S+",                                _t("https://get.tamilhit.tech/MR-X/tamil/",   "https://www.tamilhit.tech/",               8)),
    (r"https?://.+\.omnifly\.\S+",                           _t("https://f.omnifly.in.net/",                "https://ignitesmm.com/",                   5)),
    (r"https?://sheralinks\.\S+",                            _t("https://sheralinks.com/",                  "https://blogyindia.com/",                  0.8)),
    (r"https?://bindaaslinks\.\S+",                          _t("https://appsinsta.com/blog",               "https://pracagov.com/",                    3)),
    (r"https?://viplinks\.\S+",                              _t("https://m.vip-link.net/",                  "https://m.leadcricket.com/",               5)),
    (r"https?://.+\.short2url\.\S+",                         _t("https://techyuth.xyz/blog/",               "https://blog.mphealth.online/",            10)),
    (r"https?://shrinkforearn\.\S+",                         _t("https://shrinkforearn.in/",                "https://wp.uploadfiles.in/",               8)),
    (r"https?://bringlifes\.\S+",                            _t("https://bringlifes.com/",                  "https://loanoffering.in/",                 5)),
    (r"https?://.+\.linkfly\.\S+",                           _t("https://insurance.yosite.net/",            "https://yosite.net/",                      10)),
    (r"https?://.+\.earn2me\.\S+",                           _t("https://blog.filepresident.com/",          "https://easyworldbusiness.com/",           5)),
    (r"https?://(.+\.)?vplink(s)?\.\S+",                        vplink),
    (r"https?://.+\.hittracks\.\S+",                            hittracks),
    (r"https?://.+\.entiredust\.\S+",                           hittracks),
    (r"https?://vcloud\.\S+",                                   vcloud,             True),
    (r"https?://dotflix\.\S+",                                  dotflix,            True),
    (r"https?://.+\.narzolinks\.\S+",                        _t("https://go.narzolinks.click/",             "https://hydtech.in/",                      5)),
    (r"https?://earn2short\.\S+",                            _t("https://go.earn2short.in/",                "https://tech.insuranceinfos.in/",          0.8)),
    (r"https?://instantearn\.\S+",                           _t("https://get.instantearn.in/",              "https://love.petrainer.in/",               5)),
    (r"https?://linkjust\.\S+",                              _t("https://linkjust.com/",                    "https://forexrw7.com/",                    3.1)),
    (r"https?://pdiskshortener\.\S+",                        _t("https://pdiskshortener.com/",              "",                                         10)),
    (r"https?://publicearn\.\S+",                            _t("https://publicearn.com/",                  "https://careersides.com/",                 4.9)),
    (r"https?://modijiurl\.\S+",                             _t("https://modijiurl.com/",                   "https://loanoffering.in/",                 8)),
    (r"https?://linkshortx\.\S+",                            _t("https://linkshortx.in/",                   "https://nanotech.org.in/",                 4.9)),
    (r"https?://.+\.shorito\.\S+",                           _t("https://go.shorito.com/",                  "https://healthgo.gorating.in/",            8)),
    (r"https?://pdisk\.\S+",                                 _t("https://last.moneycase.link/",             "https://www.webzeni.com/",                 4.9)),
    (r"https?://ziplinker\.\S+",                             _t("https://ziplinker.net",                    "https://fintech.techweeky.com/",           1)),
    (r"https?://ouo\.\S+",                                   ouo),
    (r"https?://(shareus|shrs)\.\S+",                        shareus),
    (r"https?://(.+\.)?dropbox\.\S+",                        dropbox),
    (r"https?://linkvertise\.\S+",                           linkvertise),
    (r"https?://rslinks\.\S+",                               rslinks),
    (r"https?://(bit|tinyurl|(.+\.)short|shorturl|t)\.\S+", shorter),
    (r"https?://appurl\.\S+",                                appurl),
    (r"https?://surl\.\S+",                                  surl),
    (r"https?://thinfi\.\S+",                                thinfi),
    (r"https?://justpaste\.\S+",                             justpaste),
    (r"https?://linksxyz\.\S+",                              linksxyz),

    # ── DL Sites (direct) ───────────────────────────────────────────────────
    (r"https?://cinevood\.\S+",                              cinevood,           True),
    (r"https?://kayoanime\.\S+",                             kayoanime,          True),
    (r"https?://toonworld4all\.\S+",                         toonworld4all,      True),
    (r"https?://skymovieshd\.\S+",                           skymovieshd,        True),
    (r"https?://.+\.sharespark\.\S+",                        sharespark,         True),
    (r"https?://.+\.1tamilmv\.\S+",                         tamilmv,            True),
]

# DL link patterns that need extra args — checked after the registry
_TERABOX_DOMAINS = {"1024tera", "terabox", "nephobox", "4funbox", "mirrobox", "momerybox", "teraboxapp"}


async def direct_link_checker(link, onlylink=False):
    domain = urlparse(link).hostname or ""

    # ── Special-cased handlers that can't fit the simple registry ──────────

    # Google Drive
    if "drive.google.com" in link:
        return get_dl(link, True)

    # Terabox (domain-based match)
    if any(x in domain for x in _TERABOX_DOMAINS):
        return await terabox(link)

    # Blocked
    if match(r"https?://.+\.technicalatg\.\S+", link):
        raise DDLException("Bypass Not Allowed!")

    # evolinks uses the original link as its own referer
    if match(r"https?://.+\.evolinks\.\S+", link):
        blink = await transcript(link, "https://ads.evolinks.in/", link, 3)
        return _chain(blink, link, onlylink)

    # DL links that need Config args
    if match(r"https?://hubdrive\.\S+", link):
        return await drivescript(link, Config.HUBDRIVE_CRYPT, "HubDrive")
    if match(r"https?://katdrive\.\S+", link):
        return await drivescript(link, Config.KATDRIVE_CRYPT, "KatDrive")
    if match(r"https?://drivefire\.\S+", link):
        return await drivescript(link, Config.DRIVEFIRE_CRYPT, "DriveFire")
    if match(r"https?://sharer\.\S+", link):
        return await sharerpw(link)

    # Share links (gdtot / filepress / appdrive etc.)
    if is_share_link(link):
        if "gdtot" in domain:
            return await gdtot(link)
        elif "filepress" in domain or "pressbee" in domain:
            return await filepress(link)
        elif "appdrive" in domain or "gdflix" in domain:
            return await appflix(link)
        else:
            return await sharer_scraper(link)

    # ── Registry scan ───────────────────────────────────────────────────────
    for entry in _REGISTRY:
        pattern = entry[0]
        handler = entry[1]
        is_direct = len(entry) == 3 and entry[2] is True

        if not match(pattern, link):
            continue

        if is_direct:
            return await handler(link)

        # Chainable DDL shortener
        blink = await handler(link)
        return await _chain(blink, link, onlylink)

    raise DDLException(
        f"<i>No Bypass Function Found for your Link :</i> <code>{link}</code>"
    )


async def _chain(blink, original_link, onlylink):
    """Follow the bypass chain, collecting intermediate links."""
    if onlylink:
        return blink

    links = []
    while True:
        try:
            links.append(blink)
            blink = await direct_link_checker(blink, onlylink=True)
            if is_excep_link(links[-1]):
                links.append("\n\n" + blink)
                break
        except Exception:
            break
    return links
