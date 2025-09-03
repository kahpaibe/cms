"""
Decides whether the url should be skipped
"""
import re
import atexit
from pathlib import Path
from logging import Logger
from typing import Optional

class KahSkipManager:
    """Skip fetching urls given some criteria"""
    # =======================
    # Skip logic
    # =======================    

    def should_skip_url(self, url: str) -> str | None:
        """If url should be skipped, return reason else None"""
        if url in self.downloaded_urls:
            return "Already downloaded."
        # Other
        if re.search(r'https://i\d\.secure\.pixiv\.net/', url, re.IGNORECASE):
            return "Blacklisted domain (known dead)."
        
        return None

    # =======================
    # Downloaded index
    # =======================

    def __init__(self, 
                 path_index: Path = Path(__file__).parent / "downloaded_index.txt", 
                 save_at_exit: bool = True,
                 logger: Optional[Logger] = None) -> None:
        """Skip fetching urls given some criteria"""
        self.path_index = path_index
        self.downloaded_urls = set()
        self.logger = logger
        if save_at_exit:
            if self.logger:
                self.logger.debug("Registering atexit save for downloaded urls.")
            atexit.register(self.save_downloaded_urls)

        # Load it if exists
        if self.path_index.exists():
            if self.logger:
                self.logger.debug(f"Loading downloaded urls from index file at path={self.path_index}.")
            with open(self.path_index, "r", encoding="utf-8") as f:
                self.downloaded_urls = set(f.read().splitlines())
        else: # create
            if self.logger:
                self.logger.debug(f"Creating new downloaded urls index file at path={self.path_index}.")
            self.path_index.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path_index, "w+", encoding="utf-8") as f:
                f.write("")

    def mark_url_as_downloaded(self, url: str) -> None:
        """Mark a URL as downloaded."""
        if self.logger:
            self.logger.debug(f"Marking URL as downloaded: url={url}")
        self.downloaded_urls.add(url)
        with open(self.path_index, "a+", encoding="utf-8") as f:
            f.write(url + "\n")

    def save_downloaded_urls(self) -> None:
        """Save the downloaded URLs to the index file."""
        if self.logger:
            self.logger.info(f"Saving downloaded URLs to index file at path={self.path_index}.")
        self.path_index.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path_index, "w", encoding="utf-8") as f:
            f.writelines(url + "\n" for url in sorted(self.downloaded_urls))

