import asyncio
import aiohttp
from pathlib import Path
from aiohttp import ClientResponse
from kahscrape.kahscrape import KahRatelimitedFetcher
import json
import re
import logging
from logging import Logger
from typing import Callable, Optional, Annotated
import lxml
from bs4 import BeautifulSoup, Tag, NavigableString
from db_structs import Circle, is_to_add

# =========== General setup ===========
FOLDER_PATH = Path(__file__).parent
with open(FOLDER_PATH / "cookies.json", "r", encoding='utf-8') as f:
    cookies = json.load(f)
COOKIES = cookies # cookies for the session

def ARED(text: str) -> str:   # Make text red
    return f"\033[31m{text}\033[39m"
def AGREEN(text: str) -> str: # Make text green
    return f"\033[32m{text}\033[39m"
def AYELLOW(text: str) -> str: # Make text yellow
    return f"\033[33m{text}\033[39m"

async def get_fetcher() -> KahRatelimitedFetcher:
    session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10.0))
    session.cookie_jar.update_cookies(cookies)

    return KahRatelimitedFetcher(session=session)

def get_logger(event: str) -> Logger:
    logger = Logger(f"scraper_{event}")
    # Add console and file log
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    logger.addHandler(handler)

    log_file_path = FOLDER_PATH / "output" / event / "logger.log"
    log_file_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_file_path)
    file_handler.setLevel(logging.INFO)
    logger.addHandler(file_handler)

    return logger

def get_onerr(event: str, logger: Optional[Logger]) -> Callable:
    async def _onerr(url: str, e: Exception, resp: ClientResponse | None, data: bytes | None, event_key: str = event, logger_: Optional[Logger] = logger):
        if logger_:
            logger_.warning(ARED(f"Error occurred while fetching {url}") + f",\ndata={data.decode('utf-8')[:40] if data else None}: \n\t{e}")
    return _onerr
# def base_onerr(url: str, e: Exception, resp: ClientResponse | None, data: bytes | None):
#     print(ARED(f"Error occurred while fetching {url}") + f", {resp=}: \n\t{e}")

def try_find_else_none(content: Tag, name: str) -> str | None:
    tag = content.find(name)
    if tag is None or isinstance(tag, int):
        return None
    return tag.get_text(strip=True)

def try_find_all_else_empty(content: Tag, name: str) -> list[str]:
    tags = content.find_all(name)
    if not tags:
        return []
    return [tag.get_text(strip=True) for tag in tags if isinstance(tag, Tag)]

# =========== ===========
if True:
    OUT_83_FOLDER = FOLDER_PATH / "output" / "c83"
    logger = get_logger("c83")
    onerr = get_onerr("c83", logger)

    async def c83_main():
        fetcher = await get_fetcher()

        async def onreq_xmlcircle(resp: ClientResponse, data: bytes):
            """For circle xml pages"""
            logger.info(AYELLOW(f"Successfully fetched {resp.url}") + f": \n\t{data[:100]}...")
            
            file_name = re.search(r"/([^/]*.xml)$", str(resp.url))        
            if file_name is None:
                await onerr(str(resp.url), Exception("Invalid URL format"), resp, data)
                return
            
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
            circle_images = try_find_all_else_empty(circle_tag, '新着画像') # TODO: fetch images
            
            
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

            if circle_cut:
                logger.error(f"Cut Image: {circle_cut}")
            if circle_cut_web:
                logger.error(f"Web Cut Image: {circle_cut_web}")
            if circle_images:
                logger.error(f"Images: {circle_images}")

            circle = Circle(
                aliases=[circle_name],
                pen_names=circle_pen_names,
                position=circle_space,
                links=curls,
                comments="\n".join(comments_args) if is_to_add(comments_args) else None
            )

            out_path = OUT_83_FOLDER / f"{file_name.group(1)}.json"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w+", encoding='utf-8') as f:
                json.dump(circle.get_json(), f, ensure_ascii=False, indent=4)

        async def onreq_xmlcutlist(resp: ClientResponse, data: bytes):
            """For cutlist xml pages"""
            logger.info(AGREEN(f"Successfully fetched {resp.url}") + f": \n\t{data.decode('utf-8')[:40]}...")
            
            file_name = re.search(r"/([^/]*.xml)$", str(resp.url))        
            if file_name is None:
                await onerr(str(resp.url), Exception("Invalid URL format"), resp, data)
                return

            content = BeautifulSoup(data, "xml")
            circles = content.find_all("Circle")
            logger.warning(f"Found {len(circles)} circles in {resp.url}")

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

            out_path = OUT_83_FOLDER / file_name.group(1)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "wb+") as f:
                f.write(data)

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