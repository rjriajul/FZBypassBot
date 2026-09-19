from re import match
from urllib.parse import urlparse

from FZBypass.bypass.dlinks import *
from FZBypass.bypass.ddl import *
from FZBypass.bypass.scrape import *
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
            r"https?:\/\/.+\.(1tamilmv|gdtot|filepress|pressbee|gdflix|sharespark)\.\S+|https?:\/\/(sharer|onlystream|hubdrive|hubcloud|katdrive|drivefire|skymovieshd|toonworld4all|kayoanime|cinevood|gdflix|filepress|pressbee|filebee|appdrive)\.\S+",
            url,
        )
    )


async def direct_link_checker(link, onlylink=False):
    domain = urlparse(link).hostname

    # File Hoster Links
    if bool(match(r"https?:\/\/(yadi|disk.yandex)\.\S+", link)):
        return await yandex_disk(link)
    elif bool(match(r"https?:\/\/.+\.mediafire\.\S+", link)):
        return await mediafire(link)
    elif bool(match(r"https?:\/\/shrdsk\.\S+", link)):
        return await shrdsk(link)
    elif any(
        x in domain
        for x in [
            "1024tera",
            "terabox",
            "nephobox",
            "4funbox",
            "mirrobox",
            "momerybox",
            "teraboxapp",
            "terasharefile",
            "freeterabox",
            "teraboxlink",
            "terafileshare",
            "teraboxshare",
        ]
    ):
        dlinks = await terabox(link)
        # Single file → return plain string; multi-file → return list for numbered display
        return dlinks[0] if len(dlinks) == 1 else dlinks
    elif "drive.google.com" in link:
        return get_dl(link, True)

    # DDL Links
    elif bool(match(r"https?:\/\/try2link\.\S+", link)):
        blink = await try2link(link)
    elif bool(match(r"https?:\/\/(gyanilinks|gtlinks)\.\S+", link)):
        blink = await gyanilinks(link)
        
    elif bool(match(r"https?:\/\/adrinolinks\.\S+", link)):
        blink = await transcript(
            link, "https://adrinolinks.in", "https://bhojpuritop.in/", 8
        )
    elif bool(match(r"https?:\/\/adsfly\.\S+", link)):
        blink = await transcript(
            link, "https://go.adsfly.in/", "https://letest25.co/", 3
        )
    elif bool(match(r"https?:\/\/(.+\.)?anlinks\.\S+", link)):
        blink = await transcript(
            link, "https://anlinks.in/", "https://dsblogs.fun/", 8
        )
    
    elif bool(match(r"https?:\/\/ronylink\.\S+", link)):
        blink = await transcript(
            link, "https://go.ronylink.com/", "https://livejankari.com/", 3
        )
    
    elif bool(match(r"https?:\/\/.+\.evolinks\.\S+", link)):
        blink = await transcript(
            link, "https://ads.evolinks.in/" , link, 3
        )
    elif bool(match(r"https?:\/\/.+\.tnshort\.\S+", link)):
        blink = await transcript(
            link, "https://news.sagenews.in/", "https://movies.djnonstopmusic.in/", 5
        )
    elif bool(match(r"https?:\/\/(xpshort|push.bdnewsx|techymozo)\.\S+", link)):
        blink = await transcript(
            link, "https://xpshort.com/", "https://www.comptegratuite.com/", 4.9
        )
    elif bool(match(r"https?:\/\/go.lolshort\.\S+", link)):
        blink = await transcript(
            link, "https://get.lolshort.tech/", "https://tech.animezia.com/", 8
        )
    elif bool(match(r"https?:\/\/onepagelink\.\S+", link)):
        blink = await transcript(
            link, "https://go.onepagelink.in/", "https://gorating.in/", 3.1
        )
    elif bool(match(r"https?:\/\/earn.moneykamalo\.\S+", link)):
        blink = await transcript(
            link, "https://go.moneykamalo.com/", "https://bloging.techkeshri.com/", 4
        )
    elif bool(match(r"https?:\/\/droplink\.\S+", link)):
        blink = await transcript(
            link, "https://droplink.co/", "https://yoshare.net/", 3.1
        )
    elif bool(match(r"https?:\/\/tinyfy\.\S+", link)):
        blink = await transcript(
            link, "https://tinyfy.in", "https://www.yotrickslog.tech/", 0
        )
    elif bool(match(r"https?:\/\/krownlinks\.\S+", link)):
        blink = await transcript(
            link, "https://go.hostadviser.net/", "blog.hostadviser.net/", 8
        )
    elif bool(match(r"https?:\/\/(du-link|dulink)\.\S+", link)):
        blink = await transcript(
            link, "https://du-link.in", "https://profitshort.com/", 0
        )
    elif bool(match(r"https?:\/\/indianshortner\.\S+", link)):
        blink = await transcript(
            link, "https://indianshortner.com/", "https://moddingzone.in/", 5
        )
    elif bool(match(r"https?:\/\/m.easysky\.\S+", link)):
        blink = await transcript(
            link, "https://techy.veganab.co/", "https://camdigest.com/", 5
        )
        blink = await transcript(
            link, "https://vip.linkbnao.com", "https://ffworld.xyz/", 2
        )
    elif bool(match(r"https?:\/\/.+\.tnlink\.\S+", link)):
        blink = await transcript(
            link, "https://news.sagenews.in/", "https://knowstuff.in/", 5
        )
    elif bool(match(r"https?:\/\/link4earn\.\S+", link)):
        blink = await transcript(
            link, "https://link4earn.com", "https://studyis.xyz/", 6
        )
    elif bool(match(r"https?:\/\/shortingly\.\S+", link)):
        blink = await transcript(
            link, "https://go.blogytube.com/", "https://blogytube.com/", 5
        )
    elif bool(match(r"https?:\/\/short2url\.\S+", link)):
        blink = await transcript(
            link, "https://techyuth.xyz/blog", "https://blog.coin2pay.xyz/", 10
        )
    elif bool(match(r"https?:\/\/urlsopen\.\S+", link)):
        blink = await transcript(
            link, "https://s.humanssurvival.com/", "https://1topjob.xyz/", 5
        )
    elif bool(match(r"https?:\/\/mdisk\.\S+", link)):
        blink = await transcript(
            link, "https://mdisk.pro", "https://www.meclipstudy.in/", 5
        )
    elif bool(match(r"https?:\/\/(pkin|go.paisakamalo)\.\S+", link)):
        blink = await transcript(
            link, "https://go.paisakamalo.in", "https://healthtips.techkeshri.com/", 5
        )
    elif bool(match(r"https?:\/\/linkpays\.\S+", link)):
        blink = await transcript(
            link, "https://tech.smallinfo.in/Gadget/", "https://finance.filmypoints.in/", 6
        )
    elif bool(match(r"https?:\/\/sklinks\.\S+", link)):
        blink = await transcript(
            link, "https://sklinks.in", "https://dailynew.online/", 5
        )
    elif bool(match(r"https?:\/\/link1s\.\S+", link)):
        blink = await transcript(
            link, "https://link1s.com", "https://anhdep24.com/", 9
        )
    elif bool(match(r"https?:\/\/tulinks\.(one|net|com|online)\S*", link)):
        blink = await transcript(
            link, "https://tulinks.one", "https://www.blogger.com/", 8
        )
    elif bool(match(r"https?:\/\/.+\.tulinks\.\S+", link)):
        blink = await transcript(
            link, "https://go.tulinks.online", "https://tutelugu.co/", 8
        )
    elif bool(match(r"https?:\/\/(.+\.)?vipurl\.\S+", link)):
        blink = await transcript(
            link, "https://count.vipurl.in/", "https://kiss6kartu.in/", 5
        )
    elif bool(match(r"https?:\/\/indyshare\.\S+", link)):
        blink = await transcript(
            link, "https://indyshare.net", "https://insurancewolrd.in/", 3.1
        )
    elif bool(match(r"https?:\/\/linkyearn\.\S+", link)):
        blink = await transcript(
            link, "https://linkyearn.com", "https://gktech.uk/", 5
        )
    elif bool(match(r"https?:\/\/earn4link\.\S+", link)):
        blink = await transcript(
            link, "https://m.open2get.in/", "https://ezeviral.com/", 8
        )
    elif bool(match(r"https?:\/\/linksly\.\S+", link)):
        blink = await transcript(
            link, "https://go.linksly.co/", "https://en.themezon.net/", 5
        )
    elif bool(match(r"https?:\/\/(.+\.)?mdiskshortner\.\S+", link)):
        blink = await transcript(
            link, "https://mdiskshortner.link", "https://yosite.net/", 0
        )
    elif bool(match(r"https?://(?:\w+\.)?rocklinks\.\S+", link)):
        blink = await transcript(
            link, "https://land.povathemes.com/", "https://blog.disheye.com/", 4.9
        )
    elif bool(match(r"https?:\/\/mplaylink\.\S+", link)):
        blink = await transcript(
            link, "https://tera-box.cloud/", "https://mvplaylink.in.net/", 5
        )
    elif bool(match(r"https?:\/\/shrinke\.\S+", link)):
        blink = await transcript(
            link, "https://en.shrinke.me/", "https://themezon.net/", 15
        )
    elif bool(match(r"https?:\/\/urlspay\.\S+", link)):
        blink = await transcript(
            link, "https://finance.smallinfo.in/", "https://tech.filmypoints.in/", 5
        )
    elif bool(match(r"https?:\/\/.+\.tnvalue\.\S+", link)):
        blink = await transcript(
            link, "https://page.finclub.in/", "https://finclub.in/", 8
        )
    elif bool(match(r"https?:\/\/sxslink\.\S+", link)):
        blink = await transcript(
            link, "https://getlink.sxslink.com/", "https://cinemapettai.in/", 5
        )
    
    elif bool(match(r"https?:\/\/moneycase\.\S+", link)):
        blink = await transcript(
            link, "https://last.moneycase.link/", "https://www.infokeeda.xyz/", 3.1
        )
    elif bool(match(r"https?:\/\/urllinkshort\.\S+", link)):
        blink = await transcript(
            link, "https://web.urllinkshort.in", "https://suntechu.in/", 5
        )
    elif bool(match(r"https?:\/\/.+\.dtglinks\.\S+", link)):
        blink = await transcript(
            link, "https://happyfiles.dtglinks.in/", "https://tech.filohappy.in/", 5
        )
    elif bool(match(r"https?:\/\/v2links\.\S+", link)):
        blink = await transcript(
            link, "https://vzu.us/", "https://newsbawa.com/", 5
        )
    elif bool(match(r"https?:\/\/v2\.kpslink\.\S+", link)):
        blink = await transcript(
            link, "https://v2.kpslink.in/", "https://infotamizhan.xyz/", 5
        )
    elif bool(match(r"https?:\/\/(.+\.)?kpslink\.\S+", link)):
        blink = await transcript(
            link, "https://kpslink.in/", "https://infotamizhan.xyz/", 3.1
        )
    elif bool(match(r"https?:\/\/tamizhmasters\.\S+", link)):
        blink = await transcript(
            link, "https://tamizhmasters.com/", "https://pokgames.com/", 5
        )
    elif bool(match(r"https?:\/\/tglink\.\S+", link)):
        blink = await transcript(
            link, "https://tglink.in/", "https://www.proappapk.com/", 5
        )
    elif bool(match(r"https?:\/\/pandaznetwork\.\S+", link)):
        blink = await transcript(
            link, "https://pandaznetwork.com/", "https://panda.freemodsapp.xyz/", 5
        )
    elif bool(match(r"https?:\/\/url4earn\.\S+", link)):
        blink = await transcript(
            link, "https://go.url4earn.in/", "https://techminde.com/", 8
        )
    elif bool(match(r"https?:\/\/ez4short\.\S+", link)):
        blink = await transcript(
            link, "https://ez4short.com/", "https://ez4mods.com/", 5
        )
    elif bool(match(r"https?:\/\/dalink\.\S+", link)):
        blink = await transcript(
            link, "https://get.tamilhit.tech/MR-X/tamil/", "https://www.tamilhit.tech/", 8
        )
    elif bool(match(r"https?:\/\/.+\.omnifly\.\S+", link)):
        blink = await transcript(
            link, "https://f.omnifly.in.net/", "https://ignitesmm.com/", 5
        )
    elif bool(match(r"https?:\/\/sheralinks\.\S+", link)):
        blink = await transcript(
            link, "https://sheralinks.com/", "https://blogyindia.com/", 0.8
        )
    elif bool(match(r"https?:\/\/bindaaslinks\.\S+", link)):
        blink = await transcript(
            link, "https://appsinsta.com/blog", "https://pracagov.com/", 3
        )
    elif bool(match(r"https?:\/\/viplinks\.\S+", link)):
        blink = await transcript(
            link, "https://m.vip-link.net/", "https://m.leadcricket.com/", 5
        )
    elif bool(match(r"https?:\/\/.+\.short2url\.\S+", link)):
        blink = await transcript(
            link, "https://techyuth.xyz/blog/", "https://blog.mphealth.online/", 10
        )
    elif bool(match(r"https?:\/\/shrinkforearn\.\S+", link)):
        blink = await transcript(
            link, "https://shrinkforearn.in/", "https://wp.uploadfiles.in/", 8
        )
    elif bool(match(r"https?:\/\/bringlifes\.\S+", link)):
        blink = await transcript(
            link, "https://bringlifes.com/", "https://loanoffering.in/", 5
        )
    elif bool(match(r"https?:\/\/.+\.linkfly\.\S+", link)):
        blink = await transcript(
            link, "https://insurance.yosite.net/", "https://yosite.net/", 10
        )
    elif bool(match(r"https?:\/\/.+\.earn2me\.\S+", link)):
        blink = await transcript(
            link, "https://blog.filepresident.com/", "https://easyworldbusiness.com/", 5
        )
    elif bool(match(r"https?:\/\/.+\.vplinks\.\S+", link)):
        blink = await transcript(
            link, "https://vplink.in", "https://insurance.findgptprompts.com/", 5
        )
    elif bool(match(r"https?:\/\/.+\.narzolinks\.\S+", link)):
        blink = await transcript(
            link, "https://go.narzolinks.click/", "https://hydtech.in/", 5
        )
    elif bool(match(r"https?:\/\/earn2short\.\S+", link)):
        blink = await transcript(
            link, "https://go.earn2short.in/", "https://tech.insuranceinfos.in/", 0.8
        )
    elif bool(match(r"https?:\/\/instantearn\.\S+", link)):
        blink = await transcript(
            link, "https://get.instantearn.in/", "https://love.petrainer.in/", 5
        )
    elif bool(match(r"https?:\/\/linkjust\.\S+", link)):
        blink = await transcript(
            link, "https://linkjust.com/", "https://forexrw7.com/", 3.1
        )
    elif bool(match(r"https?:\/\/pdiskshortener\.\S+", link)):
        blink = await transcript(
            link, "https://pdiskshortener.com/", "", 10
        )
    elif bool(match(r"https?:\/\/publicearn\.\S+", link)):
        blink = await transcript(
            link, "https://publicearn.com/", "https://careersides.com/", 4.9
        )
    elif bool(match(r"https?:\/\/modijiurl\.\S+", link)):
        blink = await transcript(
            link, "https://modijiurl.com/", "https://loanoffering.in/", 8
        )
    elif bool(match(r"https?:\/\/linkshortx\.\S+", link)):
        blink = await transcript(
            link, "https://linkshortx.in/", "https://nanotech.org.in/", 4.9
        )
    elif bool(match(r"https?:\/\/.+\.shorito\.\S+", link)):
        blink = await transcript(
            link, "https://go.shorito.com/", "https://healthgo.gorating.in/", 8
        )
    elif bool(match(r"https?:\/\/pdisk\.\S+", link)):
        blink = await transcript(
            link, "https://last.moneycase.link/", "https://www.webzeni.com/", 4.9
        )
    elif bool(match(r"https?:\/\/ziplinker\.\S+", link)):
        blink = await transcript(
            link, "https://ziplinker.net", "https://fintech.techweeky.com/", 1
        )
    elif bool(match(r"https?:\/\/ouo\.\S+", link)):
        blink = await ouo(link)
    elif bool(match(r"https?:\/\/(shareus|shrs)\.\S+", link)):
        blink = await shareus(link)
    elif bool(match(r"https?:\/\/(.+\.)?dropbox\.\S+", link)):
        blink = await dropbox(link)
    elif bool(match(r"https?:\/\/linkvertise\.\S+", link)):
        blink = await linkvertise(link)
    elif bool(match(r"https?:\/\/rslinks\.\S+", link)):
        blink = await rslinks(link)
    elif bool(match(r"https?:\/\/(bit\.ly|tinyurl\.com|(.+\.)short\.\S+|shorturl\.at|t\.ly)\S*", link)):
        blink = await shorter(link)
    elif bool(match(r"https?:\/\/appurl\.\S+", link)):
        blink = await appurl(link)
    elif bool(match(r"https?:\/\/surl\.\S+", link)):
        blink = await surl(link)
    elif bool(match(r"https?:\/\/thinfi\.\S+", link)):
        blink = await thinfi(link)
    elif bool(match(r"https?:\/\/justpaste\.\S+", link)):
        blink = await justpaste(link)
    elif bool(match(r"https?:\/\/linksxyz\.\S+", link)):
        blink = await linksxyz(link)

    # DL Sites
    elif bool(match(r"https?:\/\/cinevood\.\S+", link)):
        return await cinevood(link)
    elif bool(match(r"https?:\/\/kayoanime\.\S+", link)):
        return await kayoanime(link)
    elif bool(match(r"https?:\/\/toonworld4all\.\S+", link)):
        return await toonworld4all(link)
    elif bool(match(r"https?:\/\/skymovieshd\.\S+", link)):
        return await skymovieshd(link)
    elif bool(match(r"https?:\/\/.+\.sharespark\.\S+", link)):
        return await sharespark(link)
    elif bool(match(r"https?:\/\/.+\.1tamilmv\.\S+", link)):
        return await tamilmv(link)

    # DL Links
    elif bool(match(r"https?:\/\/hubcloud\.\S+", link)):
        return await hubcloud(link)
    elif bool(match(r"https?:\/\/hubdrive\.\S+", link)):
        return await drivescript(link, Config.HUBDRIVE_CRYPT, "HubDrive")
    elif bool(match(r"https?:\/\/katdrive\.\S+", link)):
        return await drivescript(link, Config.KATDRIVE_CRYPT, "KatDrive")
    elif bool(match(r"https?:\/\/drivefire\.\S+", link)):
        return await drivescript(link, Config.DRIVEFIRE_CRYPT, "DriveFire")
    elif bool(match(r"https?:\/\/sharer\.\S+", link)):
        return await sharerpw(link)
    elif is_share_link(link):
        if "gdtot" in domain:
            return await gdtot(link)
        elif "filepress" in domain or "pressbee" in domain:
            return await filepress(link)
        elif "gdflix" in domain:
            return await gdflix(link)
        elif "appdrive" in domain:
            return await appflix(link)
        else:
            return await sharer_scraper(link)

    # Exceptions
    elif bool(match(r"https?:\/\/.+\.technicalatg\.\S+", link)):
        raise DDLException("Bypass Not Allowed !")
    else:
        raise DDLException(
            f"<i>No Bypass Function Found for your Link :</i> <code>{link}</code>"
        )

    if onlylink:
        return blink

    links = []
    depth = 0
    MAX_DEPTH = 10
    seen_links = set()
    while depth < MAX_DEPTH:
        if blink in seen_links:
            break  # redirect loop detected
        seen_links.add(blink)
        try:
            links.append(blink)
            blink = await direct_link_checker(blink, onlylink=True)
            if is_excep_link(links[-1]):
                links.append("\n\n" + blink)
                break
        except Exception:
            break
        depth += 1
    return links
