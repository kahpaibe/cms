"""
Common utils
"""
import logging
import aiofiles
from pathlib import Path
from bs4 import Tag
from kahscrape.kahscrape import FetcherABC
from aiohttp import ClientResponse

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

def decode_if_possible(data: bytes) -> str:
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError:
        try:
            return data.decode('shift-jis')
        except UnicodeDecodeError:
            try:
                return data.decode('big5')
            except UnicodeDecodeError:
                try:
                    return data.decode('gbk')
                except UnicodeDecodeError:
                    pass
    return str(data)

class KahLogger(logging.Logger):
    """Logger to log to given file and to console. Will add color to console logs."""
    COLORS = {
        'INFO': '\033[92m',    # Green
        'WARNING': '\033[93m', # Yellow
        'ERROR': '\033[91m',   # Red
        'CRITICAL': '\033[95m', # Violet
        'DEBUG': '\033[94m',   # Blue
        'RESET': '\033[0m'     # Reset to default color
    }  

    class ConsoleColorFormatter(logging.Formatter):
        def format(self, record):
            # Set the color based on the log level
            col = KahLogger.COLORS.get(record.levelname, KahLogger.COLORS['RESET'])
            rst = KahLogger.COLORS.get('RESET')
            log_message = super().format(record)
            msg_args = log_message.split("\n")
            # Apply color to "CONSOLE:" prefix
            return f"{col}{msg_args[0]}{rst}\n{msg_args[1:]}" if len(msg_args) > 1 else f"{col}{log_message}{rst}"
        
    def __init__(self, name: str, path: Path, level_file: int = logging.INFO, level_console: int = logging.INFO) -> None:
        super().__init__(name, max(level_console, level_file))

        # Create a file handler and set the log level
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(path)
        file_handler.setLevel(level_file)
        
        # Create a console handler and set the log level
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level_console)

        # Create a formatter for the file handler
        file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)

        # Create a custom formatter for the console handler
        console_formatter = KahLogger.ConsoleColorFormatter('%(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)

        # Add the handlers to the logger
        self.addHandler(file_handler)
        self.addHandler(console_handler)

async def callback_image_save(fetcher: FetcherABC, resp: ClientResponse, data: bytes, logger: KahLogger, save_file_path: Path):
    """For cutlist xml pages"""
    logger.info(f"Successfully fetched image {resp.url}: {len(data)=}")
    
    save_file_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(save_file_path, "wb+") as f:
        await f.write(data)
    
    logger.debug(f"Saved image to {save_file_path}")