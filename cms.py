import asyncio
import aiofiles
import aiohttp
import json
import re
import logging
from pathlib import Path
from aiohttp import ClientResponse
from logging import Logger
from typing import Callable, Optional
from bs4 import BeautifulSoup, NavigableString
from functools import partial

from db_structs import Circle, is_to_add, Medium, Source, ReliabilityTypes, OriginTypes
from cms_lib import KahLogger, try_find_all_else_empty, try_find_else_none, decode_if_possible, callback_image_save
from kahscrape.kahscrape import KahRatelimitedFetcher, FetcherABC

# =========== General setup ===========
FOLDER_PATH = Path(__file__).parent
with open(FOLDER_PATH / "cookies.json", "r", encoding='utf-8') as f:
    cookies = json.load(f)
COOKIES = cookies # cookies for the session

async def get_fetcher() -> KahRatelimitedFetcher:
    session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10.0))
    session.cookie_jar.update_cookies(cookies)

    return KahRatelimitedFetcher(session=session)

def get_onerr(event: str, logger: Optional[Logger]) -> Callable:
    async def _onerr(fetcher: FetcherABC, url: str, e: Exception, resp: ClientResponse | None, data: bytes | None, event_key: str = event, logger_: Optional[Logger] = logger):
        if logger_:
            logger_.warning(f"Error occurred while fetching {url}\ndata={decode_if_possible(data)[:40] if data else None}:\n\t{e}")
    return _onerr
# def base_onerr(url: str, e: Exception, resp: ClientResponse | None, data: bytes | None):
#     print(ARED(f"Error occurred while fetching {url}") + f", {resp=}: \n\t{e}")

# =========== ===========
if True:
    OUT_83_FOLDER = FOLDER_PATH / "output" / "c83"
    logger = KahLogger("c83", OUT_83_FOLDER / "logger.log", logging.DEBUG, logging.INFO)
    onerr = get_onerr("c83", logger)

    async def c83_main():
        fetcher = await get_fetcher()

        async def onreq_xmlcircle(fetcher: FetcherABC, resp: ClientResponse, data: bytes):
            """For circle xml pages"""
            logger.info(f"Successfully fetched {resp.url}:\n\t{data[:100]}...")
            
            circle_id = re.search(r"/([^/]*)\.xml$", str(resp.url))        
            if circle_id is None:
                await onerr(str(resp.url), Exception("Invalid URL format"), resp, data)
                return
            circle_id = circle_id.group(1)
            
            content = BeautifulSoup(data, "xml")
            circle_tag = content.find("Circle")
            if circle_tag is None or isinstance(circle_tag, NavigableString):
                await onerr(str(resp.url), Exception("No Circle found, invalid circle xml!"), resp, data)
                return
            
            circle_name_tag = circle_tag.find('サークル名')
            if circle_name_tag is None or isinstance(circle_name_tag, int):
                await onerr(str(resp.url), Exception("No Circle name found, invalid circle xml!"), resp, data)
                return
            circle_name = circle_name_tag.get_text(strip=True) if circle_name_tag else None
            circle_pen_names = try_find_all_else_empty(circle_tag, '執筆者名')
            circle_space = try_find_else_none(circle_tag, '配置スペース')

            curls = []
            for site_tag in circle_tag.find_all('Webサイト'):
                site_url = site_tag.get_text(strip=True) if site_tag else None
                if site_url:
                    curls.append(site_url)
            for shop_tag in circle_tag.find_all('通販サイト'):
                shop_url = shop_tag.get_text(strip=True) if shop_tag else None
                if shop_url:
                    curls.append(shop_url)
            circle_twitter = try_find_else_none(circle_tag, 'TwitterId')
            if circle_twitter:
                curls.append(circle_twitter)
            circle_pixiv = try_find_else_none(circle_tag, 'pixivId')
            if circle_pixiv:
                curls.append(circle_pixiv)
            circle_niconico = try_find_else_none(circle_tag, 'niconicoId')
            if circle_niconico:
                curls.append(circle_niconico)

            circle_tags = try_find_all_else_empty(circle_tag, 'タグ')
            circle_genre = try_find_else_none(circle_tag, 'ジャンル')
            circle_cut = try_find_else_none(circle_tag, '申込用画像')
            circle_cut_web = try_find_else_none(circle_tag, 'Webカタログ用画像')
            circle_promotional_video = try_find_all_else_empty(circle_tag, '宣伝用動画')
            circle_goods = try_find_all_else_empty(circle_tag, '頒布物') + try_find_all_else_empty(circle_tag, 'その他頒布物')
            circle_images = circle_tag.find_all('新着画像') # TODO: fetch images
            
            
            # 宣伝用Url[サービス名*="ニコニコ"] TODO ?

            circle_description = try_find_else_none(circle_tag, '補足説明')

            comments_args = []
            if is_to_add(circle_tags):
                comments_args.append(f"Tags: {', '.join(circle_tags)}")
            if is_to_add(circle_genre):
                comments_args.append(f"Genre: {circle_genre}")
            # if is_to_add(circle_cut):
            #     comments += f"Cut Image: {circle_cut}\n"
            # if is_to_add(circle_cut_web):
            #     comments += f"Web Catalog Cut Image: {circle_cut_web}\n"
            if is_to_add(circle_promotional_video):
                comments_args.append(f"Promotional Video: {', '.join(circle_promotional_video)}")
            if is_to_add(circle_goods):
                comments_args.append(f"Goods: {', '.join(circle_goods)}")
            # if is_to_add(circle_images):
            #     comments += f"Images: {', '.join(circle_images)}\n"
            if is_to_add(circle_description):
                comments_args.append(f"Description: {circle_description}")

            media: list[Medium] = []
            if circle_cut:
                await fetcher.fetch(
                    f"https://webcatalog-archives.circle.ms/c83/imgthm/{circle_cut}",
                    partial(callback_image_save, logger=logger, save_file_path=OUT_83_FOLDER / f"cut_images/{circle_cut}"),
                    onerr
                )
                media.append(Medium(f"cut_images/{circle_cut}",
                                    [Source(f"https://webcatalog-archives.circle.ms/c83/view/detail.html?id={circle_id}", (ReliabilityTypes.Reliable, OriginTypes.Official))]))

            if circle_cut_web:
                await fetcher.fetch(
                    f"https://webcatalog-archives.circle.ms/c83/imgthm/{circle_cut_web}",
                    partial(callback_image_save, logger=logger, save_file_path=OUT_83_FOLDER / f"cut_web_images/{circle_cut_web}"),
                    onerr
                )
                media.append(Medium(f"cut_web_images/{circle_cut_web}",
                                    [Source(f"https://webcatalog-archives.circle.ms/c83/view/detail.html?id={circle_id}", (ReliabilityTypes.Reliable, OriginTypes.Official))]))

            if circle_images:
                logger.critical(f"Images: {circle_images}")

            circle = Circle(
                aliases=[circle_name] if circle_name else [],
                pen_names=circle_pen_names if is_to_add(circle_pen_names) else None,
                position=circle_space if is_to_add(circle_space) else None,
                links=curls if is_to_add(curls) else None,
                media=media if is_to_add(media) else None,
                comments="\n".join(comments_args) if is_to_add(comments_args) else None
            )

            out_path = OUT_83_FOLDER / f"circle_{circle_id}.json"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(out_path, "w+", encoding='utf-8') as f:
                await f.write(json.dumps(circle.get_json(), ensure_ascii=False, indent=4))

        async def onreq_xmlcutlist(fetcher: FetcherABC, resp: ClientResponse, data: bytes):
            """For cutlist xml pages"""
            logger.info(f"Successfully fetched {resp.url}:\n\t{decode_if_possible(data)[:40]}...")
            
            day_page = re.search(r"/([^/]*)\.xml$", str(resp.url))        
            if day_page is None:
                await onerr(str(resp.url), Exception("Invalid URL format"), resp, data)
                return
            day_page = day_page.group(1)

            content = BeautifulSoup(data, "xml")
            circles = content.find_all("Circle")
            logger.debug(f"Found {len(circles)} circles in {resp.url}")

            for circle in circles:
                cid = circle.get('公開サークルId')

                circle_xml_url = f"https://webcatalog-archives.circle.ms/c83/xml/{cid}.xml"
                await fetcher.fetch(
                    circle_xml_url,
                    onreq_xmlcircle,
                    onerr
                )
                if i > 1:  # @@@@@@@@@@@@@@@@@@@@@@@@
                    break

            out_path = OUT_83_FOLDER / f"{day_page}.xml"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(out_path, "wb+") as f:
                await f.write(data)

        xmlcutlist_urls = (
            f"https://webcatalog-archives.circle.ms/c83/xmlcutlist/day1page{i:04d}.xml" 
            for i in range(1, 185 + 1)
        )
        for i, url in enumerate(xmlcutlist_urls):
            await fetcher.fetch(
                url,
                onreq_xmlcutlist,
                onerr
            )
            break
            if i > 1:  # @@@@@@@@@@@@@@@@@@@@@@@@
                break
        
        await fetcher.wait_and_close()

    asyncio.run(c83_main())