import asyncio
import csv
import gzip
import json
import logging
import os
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qsl, urldefrag, urlencode, urljoin, urlsplit, urlunsplit

import httpx
import trafilatura
from dotenv import load_dotenv
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

from agents.content_utils import extract_main_html
from .crawler_agent import CrawlerAgent


PROJECT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_DIR / ".env")
MAX_VISITED_PAGES = int(os.getenv("MAX_VISITED_PAGES", "50"))
CRAWL_CONCURRENCY = int(os.getenv("CRAWL_CONCURRENCY", "8"))
CRAWLER_TIMEOUT_SECONDS = int(os.getenv("CRAWLER_TIMEOUT_SECONDS", "15"))
JS_RENDER_FALLBACK = os.getenv("JS_RENDER_FALLBACK", "1").strip().lower() in {"1", "true", "yes", "on"}
JS_RENDER_TIMEOUT_SECONDS = int(os.getenv("JS_RENDER_TIMEOUT_SECONDS", "20"))
JS_RENDER_MIN_ARTICLE_CHARS = int(os.getenv("JS_RENDER_MIN_ARTICLE_CHARS", "200"))
LISTING_MIN_ARTICLE_LINKS = int(os.getenv("LISTING_MIN_ARTICLE_LINKS", "3"))
UI_QUERY_KEYS = {"mini", "blindfriendly", "contrast", "fontsize", "width"}
LOG_FILE = Path(os.getenv("LOG_FILE", "logs/logs.txt"))
if not LOG_FILE.is_absolute():
    LOG_FILE = PROJECT_DIR / LOG_FILE
LOGGER = logging.getLogger("crawler")
LOGGER.setLevel(logging.INFO)
LOGGER.propagate = False
if not LOGGER.handlers:
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    LOGGER.addHandler(file_handler)
    LOGGER.addHandler(console_handler)


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)


class Crawler:
    def __init__(self, sites_file: str | Path) -> None:
        self.sites_file = Path(sites_file)
        project_dir = PROJECT_DIR
        output_dir = Path(os.getenv("SCRAPPED_DIR", "data/scrapped"))
        self.output_dir = output_dir if output_dir.is_absolute() else project_dir / output_dir
        self.concurrency = CRAWL_CONCURRENCY
        self.timeout = CRAWLER_TIMEOUT_SECONDS
        self._article_locks: dict[str, asyncio.Lock] = {}
        self._browser_lock = asyncio.Lock()
        self._playwright = None
        self._browser = None
        model_path = Path(os.getenv("CRAWLER_AGENT_MODEL_PATH", "models/crawler_agent.pt"))
        if not model_path.is_absolute():
            model_path = project_dir / model_path
        self.crawler_agent = CrawlerAgent.load(model_path) if model_path.is_file() else CrawlerAgent()
        LOGGER.info(
            "CrawlerAgent: %s",
            f"załadowano {model_path}" if model_path.is_file() else "używam wag domyślnych",
        )
        if MAX_VISITED_PAGES < 1:
            raise ValueError("MAX_VISITED_PAGES musi wynosić co najmniej 1")
        if self.concurrency < 1 or self.timeout < 1 or JS_RENDER_TIMEOUT_SECONDS < 1:
            raise ValueError("Limity równoległości i timeoutów muszą wynosić co najmniej 1")

    def _load_sites(self) -> list[str]:
        with self.sites_file.open(encoding="utf-8-sig", newline="") as file:
            sites = [
                value.strip()
                for row in csv.reader(file)
                for value in row
                if value.strip() and value.strip().lower() not in {"domain", "url", "site", "website"}
            ]
        return list(dict.fromkeys(sites))

    @staticmethod
    def _normalize_url(url: str) -> str:
        parts = urlsplit(urldefrag(url.strip())[0])
        path = parts.path.rstrip("/") or "/"
        query = [
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if key.casefold() not in UI_QUERY_KEYS and not key.casefold().startswith("qt-")
        ]
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query, doseq=True), ""))

    @staticmethod
    def _is_ignored_url(url: str) -> bool:
        path = urlsplit(url).path.casefold()
        return "/calendar-node-field-data-wydarzenia/" in path

    @staticmethod
    def _in_scope(url: str, site: str) -> bool:
        target = urlsplit(url)
        root = urlsplit(site)
        root_path = root.path.rstrip("/")
        return (
            target.scheme in {"http", "https"}
            and Crawler._same_host(url, site)
            and (not root_path or target.path == root_path or target.path.startswith(f"{root_path}/"))
        )

    @staticmethod
    def _same_host(url: str, site: str) -> bool:
        target_host = (urlsplit(url).hostname or "").lower().removeprefix("www.")
        root_host = (urlsplit(site).hostname or "").lower().removeprefix("www.")
        return bool(target_host and target_host == root_host)

    async def _get(self, client: httpx.AsyncClient, url: str) -> httpx.Response | None:
        try:
            response = await client.get(url)
            if 300 <= response.status_code < 400:
                LOGGER.warning("Pominięto przekierowanie: %s", url)
                return None
            if response.status_code >= 400:
                LOGGER.warning("%s: HTTP %s", url, response.status_code)
                return None
            return response
        except httpx.HTTPError as error:
            LOGGER.error("Błąd pobierania %s: %s", url, error)
            return None

    async def _render_page(self, url: str) -> str | None:
        if not JS_RENDER_FALLBACK:
            return None
        try:
            async with self._browser_lock:
                if self._browser is None:
                    self._playwright = await async_playwright().start()
                    self._browser = await self._playwright.chromium.launch(headless=True)
            page = await self._browser.new_page()

            async def block_redirects(route) -> None:
                if route.request.redirected_from is not None:
                    await route.abort()
                else:
                    await route.continue_()

            await page.route("**/*", block_redirects)
            try:
                response = await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=JS_RENDER_TIMEOUT_SECONDS * 1000,
                )
                if response and 300 <= response.status < 400:
                    LOGGER.warning("Pominięto przekierowanie JS: %s", url)
                    return None
                if self._normalize_url(page.url) != self._normalize_url(url):
                    LOGGER.warning("Pominięto stronę po przekierowaniu JS: %s -> %s", url, page.url)
                    return None
                try:
                    await page.wait_for_load_state(
                        "networkidle",
                        timeout=min(JS_RENDER_TIMEOUT_SECONDS * 1000, 3000),
                    )
                except PlaywrightTimeoutError:
                    pass
                return await page.content()
            finally:
                await page.close()
        except Exception as error:
            LOGGER.warning("Nie udało się wyrenderować strony JS %s: %s", url, error)
            return None

    async def _close_browser(self) -> None:
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None

    @staticmethod
    def _extract_article(url: str, html: str) -> tuple[str, str]:
        metadata = trafilatura.extract_metadata(html, default_url=url)
        title = (metadata.title or "").strip() if metadata else ""
        content = trafilatura.extract(
            extract_main_html(html),
            url=url,
            include_comments=False,
            include_tables=False,
        )
        return title or url, (content or "").strip()

    def _append_article(
        self,
        domain: str,
        url: str,
        title: str,
        content: str,
    ) -> bool:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        file_path = self.output_dir / f"{domain}.json"
        if file_path.exists():
            data = json.loads(file_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not isinstance(data.get("articles"), list):
                raise ValueError(f"Nieprawidłowy format pliku: {file_path}")
        else:
            data = {"domain": domain, "articles": []}

        existing = next(
            (article for article in data["articles"] if article.get("url") == url),
            None,
        )
        if existing:
            if existing.get("crawler_category") == "article":
                return False
            existing["crawler_category"] = "article"
        else:
            data["articles"].append({
                "url": url,
                "title": title,
                "content": content,
                "crawler_category": "article",
            })

        temporary_path = file_path.with_suffix(".json.tmp")
        try:
            temporary_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary_path, file_path)
        finally:
            temporary_path.unlink(missing_ok=True)
        return True

    def _remove_saved_page(self, domain: str, url: str) -> bool:
        file_path = self.output_dir / f"{domain}.json"
        if not file_path.is_file():
            return False
        data = json.loads(file_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("articles"), list):
            raise ValueError(f"Nieprawidłowy format pliku: {file_path}")
        filtered = [article for article in data["articles"] if article.get("url") != url]
        if len(filtered) == len(data["articles"]):
            return False
        data["articles"] = filtered
        temporary_path = file_path.with_suffix(".json.tmp")
        try:
            temporary_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary_path, file_path)
        finally:
            temporary_path.unlink(missing_ok=True)
        return True

    async def _save_article(
        self,
        site: str,
        url: str,
        title: str,
        content: str,
    ) -> None:
        domain = (urlsplit(site).hostname or "").lower().removeprefix("www.")
        if not domain:
            return
        lock = self._article_locks.get(domain)
        if lock is None:
            lock = self._article_locks[domain] = asyncio.Lock()
        async with lock:
            saved = await asyncio.to_thread(
                self._append_article,
                domain,
                url,
                title,
                content,
            )
        if saved:
            LOGGER.info("Zapisano artykuł: %s", url)

    async def _remove_article(self, site: str, url: str) -> None:
        domain = (urlsplit(site).hostname or "").lower().removeprefix("www.")
        if not domain:
            return
        lock = self._article_locks.get(domain)
        if lock is None:
            lock = self._article_locks[domain] = asyncio.Lock()
        async with lock:
            removed = await asyncio.to_thread(self._remove_saved_page, domain, url)
        if removed:
            LOGGER.info("Usunięto z archiwum stronę niebędącą artykułem: %s", url)

    async def _sitemap_candidates(self, client: httpx.AsyncClient, site: str) -> list[str]:
        parts = urlsplit(site)
        origin = f"{parts.scheme}://{parts.netloc}"
        robots = await self._get(client, f"{origin}/robots.txt")
        sitemap_queue = []
        if robots:
            sitemap_queue = [
                line.split(":", 1)[1].strip()
                for line in robots.text.splitlines()
                if line.lower().startswith("sitemap:")
            ]
        if not sitemap_queue:
            sitemap_queue = [
                f"{origin}/sitemap.xml",
                f"{origin}/sitemap_index.xml",
                f"{origin}/wp-sitemap.xml",
            ]

        return list(dict.fromkeys(
            self._normalize_url(url)
            for url in sitemap_queue
            if self._same_host(url, site)
        ))

    async def _render_page(self, url: str) -> str | None:
        if not JS_RENDER_FALLBACK:
            return None
        try:
            async with self._browser_lock:
                if self._browser is None:
                    self._playwright = await async_playwright().start()
                    self._browser = await self._playwright.chromium.launch(headless=True)
            page = await self._browser.new_page()

            async def block_redirects(route) -> None:
                if route.request.redirected_from is not None:
                    await route.abort()
                else:
                    await route.continue_()

            await page.route("**/*", block_redirects)
            try:
                response = await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=JS_RENDER_TIMEOUT_SECONDS * 1000,
                )
                if response and 300 <= response.status < 400:
                    LOGGER.warning("Pominięto przekierowanie JS: %s", url)
                    return None
                if self._normalize_url(page.url) != self._normalize_url(url):
                    LOGGER.warning("Pominięto stronę po przekierowaniu JS: %s -> %s", url, page.url)
                    return None
                try:
                    await page.wait_for_load_state(
                        "networkidle",
                        timeout=min(JS_RENDER_TIMEOUT_SECONDS * 1000, 3000),
                    )
                except PlaywrightTimeoutError:
                    pass
                return await page.content()
            finally:
                await page.close()
        except Exception as error:
            LOGGER.warning("Nie udało się wyrenderować strony JS %s: %s", url, error)
            return None

    async def _close_browser(self) -> None:
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None

    async def _crawl_site(self, client: httpx.AsyncClient, site: str) -> list[str]:
        site = site if "://" in site else f"https://{site}"
        site = self._normalize_url(site)
        if self._is_ignored_url(site):
            LOGGER.info("Pominięto widok kalendarza: %s", site)
            return []
        agent = self.crawler_agent
        open_list = [site]
        closed_list: list[str] = []
        open_keys = {self._normalize_url(site)}
        closed_keys: set[str] = set()

        def enqueue(link: str, is_sitemap: bool = False) -> None:
            key = self._normalize_url(link)
            if self._is_ignored_url(key):
                return
            in_scope = self._same_host(link, site) if is_sitemap else self._in_scope(link, site)
            if in_scope and key not in open_keys and key not in closed_keys:
                open_list.append(key)
                open_keys.add(key)

        def page_links(html: str, page_url: str) -> tuple[list[str], int, int]:
            parser = _LinkParser()
            parser.feed(html)
            links: list[str] = []
            nested_links: set[str] = set()
            article_links: set[str] = set()
            page_path = urlsplit(page_url).path.rstrip("/")
            for href in parser.links:
                link = self._normalize_url(urljoin(page_url, href))
                if self._is_ignored_url(link) or not self._in_scope(link, site):
                    continue
                links.append(link)
                link_path = urlsplit(link).path
                if page_path and link_path.startswith(f"{page_path}/"):
                    nested_links.add(link)
                if agent.classify(link) == "article":
                    article_links.add(link)
            return list(dict.fromkeys(links)), len(nested_links), len(article_links)

        def reclassify_hub(
            page_url: str,
            category: str,
            nested_count: int,
        ) -> str:
            if category == "article" and nested_count >= LISTING_MIN_ARTICLE_LINKS:
                LOGGER.info(
                    "Zmiana article -> listing na podstawie %d zagnieżdżonych linków: %s",
                    nested_count,
                    page_url,
                )
                return "listing"
            return category

        for sitemap_url in await self._sitemap_candidates(client, site):
            enqueue(sitemap_url, is_sitemap=True)

        while open_list and len(closed_list) < MAX_VISITED_PAGES:
            page = open_list.pop(0)
            page_key = self._normalize_url(page)
            open_keys.discard(page_key)
            if page_key in closed_keys:
                continue
            closed_list.append(page)
            closed_keys.add(page_key)
            category = agent.classify(page)
            if category == "other":
                LOGGER.info("Pominięto bez pobierania [other]: %s", page)
                await self._remove_article(site, page)
                continue
            LOGGER.info("Odwiedzam [%s]: %s", category, page)

            response = await self._get(client, page)
            if not response:
                continue
            if category == "sitemap":
                content = response.content
                try:
                    if page.lower().endswith(".gz"):
                        content = gzip.decompress(content)
                    root = ET.fromstring(content)
                except (ET.ParseError, OSError, EOFError):
                    LOGGER.warning("Niepoprawna sitemap: %s", page)
                    continue

                is_index = root.tag.rsplit("}", 1)[-1].lower() == "sitemapindex"
                for element in root.iter():
                    if element.tag.rsplit("}", 1)[-1].lower() == "loc" and element.text:
                        link = urljoin(page, element.text.strip())
                        enqueue(link, is_sitemap=is_index)
                continue

            if "html" not in response.headers.get("content-type", "text/html").lower():
                continue
            html = response.text
            extracted_title = page
            extracted_content = ""
            if category == "article":
                try:
                    extracted_title, extracted_content = await asyncio.to_thread(
                        self._extract_article,
                        page,
                        html,
                    )
                except Exception:
                    LOGGER.exception("Nie udało się wyodrębnić artykułu: %s", page)
                    extracted_title, extracted_content = page, ""

            links, nested_count, article_link_count = page_links(html, page)
            category = reclassify_hub(page, category, nested_count)
            needs_render = (
                category == "article"
                and len(extracted_content) < JS_RENDER_MIN_ARTICLE_CHARS
            ) or (category == "listing" and article_link_count == 0)
            if needs_render:
                rendered_html = await self._render_page(page)
                if rendered_html:
                    html = rendered_html
                    links, nested_count, article_link_count = page_links(html, page)
                    category = reclassify_hub(page, category, nested_count)
                    if category == "article":
                        extracted_title, extracted_content = await asyncio.to_thread(
                            self._extract_article,
                            page,
                            html,
                        )
                        LOGGER.info("Użyto renderowania JS dla artykułu: %s", page)
                    else:
                        LOGGER.info("Użyto renderowania JS dla listingu: %s", page)

            if category != "article":
                await self._remove_article(site, page)

            if (
                category == "article"
                and nested_count >= LISTING_MIN_ARTICLE_LINKS
                and article_link_count >= LISTING_MIN_ARTICLE_LINKS
            ):
                category = "listing"
                LOGGER.info(
                    "Zmiana article -> listing: %s (linki zagnieżdżone: %d)",
                    page,
                    nested_count,
                )

            if category == "article":
                if extracted_content:
                    await self._save_article(site, page, extracted_title, extracted_content)
                else:
                    LOGGER.warning("Nie udało się wyodrębnić treści artykułu: %s", page)

            for link in links:
                enqueue(link)

        LOGGER.info("%s: odwiedzono %d stron", site, len(closed_list))
        return closed_list

    async def _run(self) -> None:
        sites = self._load_sites()
        LOGGER.info(
            "Start crawlera: %d domen, równoległość=%d, timeout=%d s, limit=%d stron/domenę",
            len(sites),
            self.concurrency,
            self.timeout,
            MAX_VISITED_PAGES,
        )
        semaphore = asyncio.Semaphore(self.concurrency)

        async def crawl_site(site: str) -> None:
            async with semaphore:
                await self._crawl_site(client, site)

        limits = httpx.Limits(max_connections=self.concurrency)
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                limits=limits,
                follow_redirects=False,
            ) as client:
                await asyncio.gather(*(crawl_site(site) for site in sites))
        finally:
            await self._close_browser()
        LOGGER.info("Crawler zakończył pracę")

    def run(self) -> None:
        try:
            asyncio.run(self._run())
        except Exception:
            LOGGER.exception("Crawler zakończył pracę błędem")
            raise
