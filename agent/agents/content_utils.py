from bs4 import BeautifulSoup, Tag


_BOILERPLATE_SELECTORS = (
    "script",
    "style",
    "nav",
    "header",
    "footer",
    "aside",
    "noscript",
    "form",
    "[role='navigation']",
    ".menu",
    ".sidebar",
    ".breadcrumbs",
    ".breadcrumb",
    ".social-share",
    ".cookie-banner",
)
_MAIN_SELECTORS = (
    "article",
    "main",
    "#main-content",
    "#content",
    ".field-name-body",
    ".entry-content",
    ".post-content",
    ".article-content",
)


def _main_node(source: str) -> Tag | BeautifulSoup:
    soup = BeautifulSoup(source, "html.parser")
    for element in soup.select(",".join(_BOILERPLATE_SELECTORS)):
        element.decompose()
    for selector in _MAIN_SELECTORS:
        candidate = soup.select_one(selector)
        if candidate and candidate.get_text(" ", strip=True):
            return candidate
    return soup.body or soup


def extract_main_html(source: str) -> str:
    return str(_main_node(source))


def extract_main_text(source: str) -> str:
    return _main_node(source).get_text("\n", strip=True)
