# Instalacja zależności: pip install trafilatura beautifulsoup4 httpx python-dotenv

from __future__ import annotations

import csv
import asyncio
import json
import logging
import os
import random
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpx
import trafilatura
from bs4 import BeautifulSoup
from dotenv import load_dotenv


load_dotenv()


def parse_keywords(raw_keywords: str) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in raw_keywords.split(",") if value.strip()))


def _load_domains(file_path: Path) -> list[str]:
    if not file_path.is_absolute():
        file_path = Path(__file__).resolve().parent / file_path
    try:
        domains: list[str] = []
        seen: set[str] = set()
        with file_path.open(encoding="utf-8-sig", newline="") as csv_file:
            for row in csv.reader(csv_file):
                for value in row:
                    value = value.strip()
                    if not value or value.startswith("#"):
                        continue
                    if value.lower() in {"domain", "url", "site", "website"}:
                        continue

                    parsed = urlsplit(value if "://" in value else f"//{value}")
                    host = parsed.hostname
                    if not host:
                        continue
                    host = host.lower()
                    path = parsed.path.rstrip("/")
                    site = f"{host}{path}"
                    canonical_site = f"{host.removeprefix('www.')}{path}"
                    if canonical_site not in seen:
                        seen.add(canonical_site)
                        domains.append(site)
        return domains
    except OSError:
        return []


# Konfiguracja pipeline'u z pliku .env; limit 0 oznacza brak limitu.
DOMAINS_FILE = Path(os.getenv("DOMAINS_FILE", "sites.csv"))
MAX_SITES_TO_SEARCH = int(os.getenv("MAX_SITES_TO_SEARCH", "5"))
MAX_ARTICLES_TO_PROCESS = int(os.getenv("MAX_ARTICLES_TO_PROCESS", "5"))
_ALL_DOMAINS = _load_domains(DOMAINS_FILE)
DOMAINS = _ALL_DOMAINS[:MAX_SITES_TO_SEARCH] if MAX_SITES_TO_SEARCH > 0 else _ALL_DOMAINS

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "SpeakLeash/bielik-11b-v2.3-instruct:Q4_K_M")
MAX_ARTICLE_CHARS = int(os.getenv("MAX_ARTICLE_CHARS", "6000"))
REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "25"))
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "180"))
CRAWL_CONCURRENCY = int(os.getenv("CRAWL_CONCURRENCY", "4"))
ARTICLE_CONCURRENCY = int(os.getenv("ARTICLE_CONCURRENCY", "3"))
MAX_PAGES_PER_SITE = int(os.getenv("MAX_PAGES_PER_SITE", "20"))
CRAWL_DELAY_SECONDS = (
    float(os.getenv("CRAWL_DELAY_MIN_SECONDS", "0.2")),
    float(os.getenv("CRAWL_DELAY_MAX_SECONDS", "0.6")),
)
OUTPUT_JSON = Path("raport_wyniki.json")
OUTPUT_MARKDOWN = Path("raport.md")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
LOGGER = logging.getLogger("news_pipeline")

ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "relevant": {"type": "boolean"},
        "project_type": {
            "type": "string",
            "enum": ["pomysł", "patent", "inwestycja", "projekt badawczy", "wdrożenie", "inne"],
        },
        "project_title": {"type": "string"},
        "institution": {"type": "string"},
        "people": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "role": {"type": "string"}},
                "required": ["name", "role"],
                "additionalProperties": False,
            },
        },
        "contact": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"},
                "phone": {"type": "string"},
                "url": {"type": "string"},
            },
            "required": ["name", "email", "phone", "url"],
            "additionalProperties": False,
        },
        "stage": {
            "type": "string",
            "enum": ["pomysł", "badania", "prototyp", "testy", "wdrożenie", "komercjalizacja", "zakończony", "nieustalony"],
        },
        "investment": {"type": "string"},
        "facts": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
        "summary": {"type": "string"},
        "missing_information": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
        "evidence": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
    },
    "required": [
        "relevant", "project_type", "project_title", "institution", "people", "contact",
        "stage", "investment", "facts", "summary", "missing_information", "evidence",
    ],
    "additionalProperties": False,
}


@dataclass
class ArticleResult:
    url: str
    title: str
    domain: str
    keyword: str
    fetched_at: str
    matched_keywords: list[str] = field(default_factory=list)
    published_at: str = ""
    relevant: bool | None = None
    project_type: str = "inne"
    project_title: str = ""
    institution: str = ""
    people: list[dict[str, str]] = field(default_factory=list)
    contact: dict[str, str] = field(
        default_factory=lambda: {"name": "", "email": "", "phone": "", "url": ""}
    )
    stage: str = "nieustalony"
    investment: str = ""
    facts: list[str] = field(default_factory=list)
    summary: str = ""
    missing_information: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    scrape_error: str | None = None
    analysis_error: str | None = None


def normalize_url(url: str) -> str:
    """Normalize URL enough to deduplicate fragments and trailing slashes."""
    parts = urlsplit(url.strip())
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


def _is_in_scope(url: str, site: str) -> bool:
    result = urlsplit(url)
    scope = urlsplit(f"//{site}")
    if result.scheme not in {"http", "https"} or not _is_same_site_host(url, site):
        return False

    scope_path = scope.path.rstrip("/")
    result_path = result.path.rstrip("/") or "/"
    return not scope_path or result_path == scope_path or result_path.startswith(f"{scope_path}/")


def _is_same_site_host(url: str, site: str) -> bool:
    result_host = urlsplit(url).hostname
    scope_host = urlsplit(f"//{site}").hostname
    if not result_host or not scope_host:
        return False
    result_host = result_host.lower().removeprefix("www.")
    scope_host = scope_host.lower().removeprefix("www.")
    return result_host == scope_host or result_host.endswith(f".{scope_host}")


async def _get_response(
    client: httpx.AsyncClient,
    url: str,
    semaphore: asyncio.Semaphore,
    site: str,
) -> httpx.Response | None:
    parts = urlsplit(url)
    candidates = [url]
    if parts.scheme == "https":
        candidates.append(urlunsplit(("http", parts.netloc, parts.path, parts.query, "")))

    for candidate in candidates:
        current_url = candidate
        for _ in range(6):
            await asyncio.sleep(random.uniform(*CRAWL_DELAY_SECONDS))
            try:
                async with semaphore:
                    response = await client.get(current_url)
            except httpx.HTTPError as exc:
                LOGGER.debug("Nie udało się pobrać %s: %s", current_url, exc)
                break

            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                redirect_url = urljoin(str(response.url), location) if location else ""
                if not redirect_url or not _is_same_site_host(redirect_url, site):
                    LOGGER.warning("Blokuję przekierowanie poza dozwoloną witrynę: %s", redirect_url)
                    return None
                current_url = redirect_url
                continue
            if response.status_code < 400:
                return response
            return None
    return None


def _extract_links(html: str, page_url: str, site: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    for element in soup.select("script, style, nav, footer, header, aside, form, noscript"):
        element.decompose()

    links: list[str] = []
    seen: set[str] = set()
    for anchor in soup.select("a[href]"):
        target = urljoin(page_url, anchor["href"].strip())
        parts = urlsplit(target)
        if parts.scheme not in {"http", "https"} or not _is_in_scope(target, site):
            continue
        normalized = urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", "", ""))
        if normalized not in seen:
            seen.add(normalized)
            links.append(normalized)
    return links


def _keyword_matches(keywords: list[str], title: str, text: str) -> list[str]:
    content = f"{title}\n{text}".casefold()
    matches = []
    for keyword in keywords:
        normalized = keyword.casefold().strip()
        tokens = re.findall(r"[^\W_]+", normalized, flags=re.UNICODE)
        if normalized and (
            normalized in content
            or any(len(token) >= 4 and token in content for token in tokens)
        ):
            matches.append(keyword)
    return matches


async def _get_sitemap_urls(
    client: httpx.AsyncClient,
    origin: str,
    site: str,
    semaphore: asyncio.Semaphore,
    robots_text: str,
) -> list[str]:
    sitemap_urls = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", robots_text)
    if not sitemap_urls:
        sitemap_urls = [
            f"{origin}/sitemap.xml",
            f"{origin}/sitemap_index.xml",
            f"{origin}/wp-sitemap.xml",
        ]

    page_urls: list[str] = []
    sitemap_queue = sitemap_urls[:4]
    fetched_sitemaps: set[str] = set()
    while sitemap_queue and len(fetched_sitemaps) < 8 and len(page_urls) < MAX_PAGES_PER_SITE * 5:
        sitemap_url = sitemap_queue.pop(0)
        if sitemap_url in fetched_sitemaps:
            continue
        fetched_sitemaps.add(sitemap_url)
        response = await _get_response(client, sitemap_url, semaphore, site)
        if not response:
            continue
        try:
            root = ET.fromstring(response.content)
        except ET.ParseError:
            continue

        root_name = root.tag.rsplit("}", 1)[-1].lower()
        for element in root.iter():
            if element.tag.rsplit("}", 1)[-1].lower() != "loc" or not element.text:
                continue
            location = element.text.strip()
            if root_name == "sitemapindex" and len(fetched_sitemaps) < 8:
                sitemap_queue.append(location)
            elif _is_in_scope(location, site):
                page_urls.append(location)
                if len(page_urls) >= MAX_PAGES_PER_SITE * 5:
                    break
    return page_urls


async def _crawl_site(
    site: str,
    keywords: list[str],
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
) -> list[dict[str, Any]]:
    parsed_site = urlsplit(f"//{site}")
    if not parsed_site.hostname:
        return []
    host = parsed_site.netloc
    path = parsed_site.path.rstrip("/")
    origin = f"https://{host}"

    robots_response = await _get_response(client, f"{origin}/robots.txt", semaphore, site)
    robots_text = robots_response.text if robots_response else ""
    if robots_response:
        origin = f"{robots_response.url.scheme}://{robots_response.url.netloc}"

    robots = None
    if robots_text:
        robots = RobotFileParser()
        robots.set_url(f"{origin}/robots.txt")
        robots.parse(robots_text.splitlines())

    start_url = f"{origin}{path or '/'}"
    sitemap_urls = await _get_sitemap_urls(client, origin, site, semaphore, robots_text)
    pending = list(dict.fromkeys([start_url, *sitemap_urls]))
    queued = {normalize_url(url) for url in pending}
    visited: set[str] = set()
    articles: list[dict[str, Any]] = []

    while pending and len(visited) < MAX_PAGES_PER_SITE:
        page_batch = []
        while pending and len(page_batch) < CRAWL_CONCURRENCY and len(visited) + len(page_batch) < MAX_PAGES_PER_SITE:
            page_url = pending.pop(0)
            normalized = normalize_url(page_url)
            if normalized in visited:
                continue
            visited.add(normalized)
            if robots and not robots.can_fetch("ArticleResearchBot", page_url):
                LOGGER.debug("Pomijam adres zablokowany przez robots.txt: %s", page_url)
                continue
            page_batch.append(page_url)

        responses = await asyncio.gather(
            *(_get_response(client, page_url, semaphore, site) for page_url in page_batch)
        )
        discovered: list[str] = []
        for page_url, response in zip(page_batch, responses):
            if not response or response.status_code >= 400:
                continue
            if not _is_in_scope(str(response.url), site):
                LOGGER.debug("Pomijam przekierowanie poza dozwoloną witrynę: %s", response.url)
                continue
            content_type = response.headers.get("content-type", "").lower()
            if content_type and "html" not in content_type:
                continue

            html = response.text
            try:
                title, published_at, text = await asyncio.to_thread(_extract_article, html, str(response.url))
            except Exception as exc:
                LOGGER.debug("Nie udało się wyodrębnić %s: %s", page_url, exc)
                title, published_at, text = "", "", ""
            discovered.extend(await asyncio.to_thread(_extract_links, html, str(response.url), site))

            matched_keywords = _keyword_matches(keywords, title, text)
            if matched_keywords:
                articles.append(
                    {
                        "url": str(response.url),
                        "title": title or page_url,
                        "domain": site,
                        "keyword": ", ".join(matched_keywords),
                        "matched_keywords": matched_keywords,
                        "published_at": published_at,
                        "content": text,
                    }
                )

        for discovered_url in discovered:
            normalized = normalize_url(discovered_url)
            if normalized not in queued and normalized not in visited:
                queued.add(normalized)
                pending.append(discovered_url)

    LOGGER.info("%s: odwiedzono %d stron, znaleziono %d kandydatów", site, len(visited), len(articles))
    return articles


async def crawl_sites_for_articles(
    keywords: list[str],
    client: httpx.AsyncClient,
) -> list[dict[str, Any]]:
    """Visit site pages and sitemaps directly; never use a search engine."""
    semaphore = asyncio.Semaphore(CRAWL_CONCURRENCY)
    batches = await asyncio.gather(
        *(_crawl_site(site, keywords, client, semaphore) for site in DOMAINS)
    )
    found: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for site_articles in batches:
        for article in site_articles:
            normalized = normalize_url(article["url"])
            if normalized in seen_urls:
                continue
            seen_urls.add(normalized)
            found.append(article)
            if MAX_ARTICLES_TO_PROCESS > 0 and len(found) >= MAX_ARTICLES_TO_PROCESS:
                LOGGER.info("Osiągnięto limit testowy %d artykułów", MAX_ARTICLES_TO_PROCESS)
                return found
    LOGGER.info("Zebrano %d pasujących stron z witryn źródłowych", len(found))
    return found


def _fallback_extract(html: str) -> tuple[str, str]:
    """Extract a title and main content when Trafilatura returns no text."""
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    main = soup.find("article") or soup.find("main") or soup.body or soup
    for element in main.select("script, style, nav, footer, header, aside, form, noscript"):
        element.decompose()
    text = main.get_text("\n", strip=True)
    return title, text


def _extract_article(html: str, url: str) -> tuple[str, str, str]:
    title = ""
    published_at = ""
    try:
        metadata = trafilatura.extract_metadata(html, default_url=url)
        if metadata:
            title = (metadata.title or "").strip()
            published_at = (metadata.date or "").strip()
    except Exception as exc:
        LOGGER.debug("Nie udało się odczytać metadanych Trafilatura dla %s: %s", url, exc)

    text = trafilatura.extract(
        html,
        url=url,
        include_comments=False,
        include_tables=False,
        favor_precision=True,
    )
    if not text or not text.strip():
        fallback_title, text = _fallback_extract(html)
        title = title or fallback_title

    text = (text or "").strip()
    if not text:
        raise ValueError("Nie udało się wyodrębnić treści artykułu")
    return title, published_at, text[:MAX_ARTICLE_CHARS]


async def analyze_article(
    client: httpx.AsyncClient,
    keyword: str,
    title: str,
    text: str,
) -> dict[str, Any]:
    """Request structured, text-grounded project data from local Ollama."""
    system_prompt = (
        "Jesteś analitykiem publicznych projektów, wynalazków, patentów i inwestycji "
        "opisywanych przez szkoły, uczelnie i inne instytucje z listy źródeł. Za trafny "
        "uznaj tylko tekst opisujący konkretny projekt, pomysł, badanie, patent, "
        "wdrożenie lub inwestycję związaną z szukaną frazą; samo przypadkowe wspomnienie "
        "frazy nie wystarcza. Opieraj wszystkie pola wyłącznie na podanym tekście. "
        "Nie zgaduj nazwisk, danych kontaktowych, etapów ani kwot. Dla niepodanych pól "
        "użyj pustego tekstu, pustej listy albo etapu 'nieustalony'. Dane kontaktowe "
        "mają być jawnie opublikowane w tekście. Cytaty w evidence muszą być krótkimi, "
        "dosłownymi fragmentami tekstu. Zwróć wyłącznie JSON zgodny ze schematem."
    )
    user_prompt = (
        f"Poszukiwana fraza: {keyword}\nTytuł źródła: {title}\n\n"
        "Wyodrębnij: relevant; project_type (pomysł, patent, inwestycja, projekt badawczy, "
        "wdrożenie lub inne); project_title; institution; people (osoby i jawnie podane role); "
        "contact (jawnie opublikowane imię, email, telefon i URL); stage (najbardziej zaawansowany "
        "potwierdzony etap); investment (kwota i waluta, jeśli podano); facts; summary; "
        "missing_information (ważne pola, których tekst nie podaje); evidence (do 3 krótkich "
        "cytatów potwierdzających ocenę).\n\n"
        f"Treść źródła:\n{text}"
    )
    response = await client.post(
        f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat",
        json={
            "model": OLLAMA_MODEL,
            "stream": False,
            "format": ANALYSIS_SCHEMA,
            "options": {"temperature": 0},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        },
        timeout=OLLAMA_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    content = payload.get("message", {}).get("content", "")
    analysis = json.loads(content)

    if not isinstance(analysis, dict) or not isinstance(analysis.get("relevant"), bool):
        raise ValueError("Ollama zwróciła nieprawidłowe pole 'relevant'")
    if not isinstance(analysis.get("facts"), list) or not isinstance(analysis.get("people"), list):
        raise ValueError("Ollama zwróciła nieprawidłowe listy facts/people")
    if not isinstance(analysis.get("contact"), dict):
        raise ValueError("Ollama zwróciła nieprawidłowe pole contact")

    def text_value(key: str, default: str = "") -> str:
        value = analysis.get(key, default)
        return value.strip() if isinstance(value, str) else default

    contact = analysis["contact"]
    people = [
        {"name": person.get("name", "").strip(), "role": person.get("role", "").strip()}
        for person in analysis["people"]
        if isinstance(person, dict)
        and isinstance(person.get("name"), str)
        and isinstance(person.get("role"), str)
    ]
    return {
        "relevant": analysis["relevant"],
        "project_type": text_value("project_type", "inne"),
        "project_title": text_value("project_title"),
        "institution": text_value("institution"),
        "people": people,
        "contact": {
            key: contact.get(key, "").strip() if isinstance(contact.get(key, ""), str) else ""
            for key in ("name", "email", "phone", "url")
        },
        "stage": text_value("stage", "nieustalony"),
        "investment": text_value("investment"),
        "facts": [fact.strip() for fact in analysis["facts"][:5] if isinstance(fact, str) and fact.strip()],
        "summary": text_value("summary"),
        "missing_information": [
            value.strip()
            for value in analysis.get("missing_information", [])[:8]
            if isinstance(value, str) and value.strip()
        ],
        "evidence": [
            value.strip()
            for value in analysis.get("evidence", [])[:3]
            if isinstance(value, str) and value.strip()
        ],
    }


async def _process_one_article(
    result: dict[str, Any],
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    index: int,
    total: int,
) -> ArticleResult:
    article = ArticleResult(
        url=result["url"],
        title=result["title"],
        domain=result["domain"],
        keyword=result["keyword"],
        fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        matched_keywords=result.get("matched_keywords", []),
        published_at=result.get("published_at", ""),
    )
    async with semaphore:
        LOGGER.info("[%d/%d] Analizuję stronę z %s", index, total, article.url)
        text = result.get("content", "")
        if not text:
            article.scrape_error = "Crawler nie wyodrębnił treści strony"
            return article
        try:
            analysis = await analyze_article(client, article.keyword, article.title, text)
            for key, value in analysis.items():
                setattr(article, key, value)
        except Exception as exc:
            article.analysis_error = str(exc)
            LOGGER.warning("Analiza Ollama nie powiodła się dla %s: %s", article.url, exc)
    return article


async def process_articles(
    search_results: list[dict[str, Any]],
    client: httpx.AsyncClient,
) -> list[ArticleResult]:
    """Analyze pages already fetched by the crawler, within a set limit."""
    semaphore = asyncio.Semaphore(ARTICLE_CONCURRENCY)
    return await asyncio.gather(
        *(
            _process_one_article(result, client, semaphore, index, len(search_results))
            for index, result in enumerate(search_results, start=1)
        )
    )


PROJECT_TYPE_ORDER = {
    "patent": 0,
    "pomysł": 1,
    "inwestycja": 2,
    "projekt badawczy": 3,
    "wdrożenie": 4,
    "inne": 5,
}
STAGE_ORDER = {
    "pomysł": 0,
    "badania": 1,
    "prototyp": 2,
    "testy": 3,
    "wdrożenie": 4,
    "komercjalizacja": 5,
    "zakończony": 6,
    "nieustalony": 7,
}


def write_reports(results: list[ArticleResult]) -> None:
    """Write structured JSON and a report sorted by relevance, type, and stage."""
    results = sorted(
        results,
        key=lambda result: (
            result.relevant is not True,
            PROJECT_TYPE_ORDER.get(result.project_type, 99),
            STAGE_ORDER.get(result.stage, 99),
            (result.institution or result.domain).casefold(),
            (result.project_title or result.title).casefold(),
        ),
    )
    OUTPUT_JSON.write_text(
        json.dumps([asdict(result) for result in results], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Raport projektów i innowacji",
        "",
        f"Liczba znalezionych źródeł: {len(results)}",
        "Sortowanie: trafność, typ projektu, etap zaawansowania.",
        "",
    ]
    for index, result in enumerate(results, start=1):
        display_title = result.project_title or result.title
        people = "; ".join(
            f"{person['name']} ({person['role']})" if person["role"] else person["name"]
            for person in result.people
        )
        contact = ", ".join(
            f"{label}: {result.contact[key]}"
            for key, label in (("name", "osoba"), ("email", "email"), ("phone", "telefon"), ("url", "strona"))
            if result.contact.get(key)
        )
        lines.extend(
            [
                f"## {index}. {display_title}",
                "",
                f"- **Trafność:** {'tak' if result.relevant is True else 'nie' if result.relevant is False else 'brak oceny'}",
                f"- **Typ:** {result.project_type}",
                f"- **Instytucja:** {result.institution or result.domain}",
                f"- **Pomysłodawcy / zespół:** {people or 'nie podano'}",
                f"- **Kontakt publiczny:** {contact or 'nie podano w artykule'}",
                f"- **Etap:** {result.stage}",
                f"- **Inwestycja / kwota:** {result.investment or 'nie podano'}",
                f"- **Data publikacji:** {result.published_at or 'nieustalona'}",
                f"- **Szukany temat:** {result.keyword}",
                f"- **Źródło:** {result.url}",
                f"- **Pobrano (UTC):** {result.fetched_at}",
                "",
            ]
        )
        if result.summary:
            lines.extend([f"**Podsumowanie:** {result.summary}", ""])
        if result.facts:
            lines.append("**Najważniejsze fakty:**")
            lines.extend(f"- {fact}" for fact in result.facts)
            lines.append("")
        if result.evidence:
            lines.append("**Fragmenty źródłowe:**")
            lines.extend(f"> {quote}" for quote in result.evidence)
            lines.append("")
        if result.missing_information:
            lines.append("**Brakujące informacje:**")
            lines.extend(f"- {item}" for item in result.missing_information)
            lines.append("")
        if result.scrape_error:
            lines.extend([f"**Błąd pobierania/ekstrakcji:** {result.scrape_error}", ""])
        if result.analysis_error:
            lines.extend([f"**Błąd analizy:** {result.analysis_error}", ""])

    OUTPUT_MARKDOWN.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    LOGGER.info("Zapisano raporty: %s oraz %s", OUTPUT_JSON, OUTPUT_MARKDOWN)


async def main() -> None:
    if not DOMAINS:
        LOGGER.error("Lista domen jest pusta lub nie udało się odczytać pliku %s", DOMAINS_FILE)
        return
    if MAX_SITES_TO_SEARCH < 0 or MAX_ARTICLES_TO_PROCESS < 0:
        LOGGER.error("Limity witryn i artykułów nie mogą być ujemne (0 oznacza bez limitu)")
        return
    if CRAWL_CONCURRENCY < 1 or ARTICLE_CONCURRENCY < 1 or MAX_PAGES_PER_SITE < 1:
        LOGGER.error("Limity współbieżności muszą wynosić co najmniej 1")
        return

    raw_keywords = await asyncio.to_thread(input, "Podaj słowa kluczowe oddzielone przecinkami: ")
    keywords = parse_keywords(raw_keywords)
    if not keywords:
        LOGGER.error("Nie podano żadnych słów kluczowych")
        return

    LOGGER.info(
        "Zakres: %d z %d witryn; limit artykułów: %s",
        len(DOMAINS),
        len(_ALL_DOMAINS),
        MAX_ARTICLES_TO_PROCESS or "brak",
    )
    limits = httpx.Limits(max_connections=max(CRAWL_CONCURRENCY, ARTICLE_CONCURRENCY))
    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT_SECONDS,
        limits=limits,
        follow_redirects=False,
    ) as client:
        articles = await crawl_sites_for_articles(keywords, client)
        results = await process_articles(articles, client)
    write_reports(results)
    LOGGER.info("Pipeline zakończony. Przetworzono %d artykułów.", len(results))


if __name__ == "__main__":
    asyncio.run(main())