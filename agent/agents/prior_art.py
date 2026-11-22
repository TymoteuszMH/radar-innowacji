import io
import os
import re
import time
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import urljoin
from zipfile import BadZipFile

import httpx
from bs4 import BeautifulSoup
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException


INTERREG_URL = "https://interreg.gov.pl/lista-projektow/"
EPO_URL = "https://ops.epo.org/3.2/rest-services"
STOP_WORDS = set("oraz jest przez dla które który nowa nowe nowy projekt projektu projekty system aplikacja urządzenie opracowali opracowała opracował zespół uczniowie umożliwia wykorzystanie ramach the and for with from using based project system application device".split())


def meaningful_words(text: str) -> list[str]:
    return [word for word in re.findall(r"[^\W_]+", text.casefold())
            if len(word) >= 4 and word not in STOP_WORDS and not word.isdigit()]


def search_query(project: dict[str, Any]) -> str:
    title = meaningful_words(str(project.get("project_title") or ""))
    summary = meaningful_words(str(project.get("summary") or ""))
    return " ".join(list(dict.fromkeys(title + summary))[:8])


def similarity(project: dict[str, Any], title: str, description: str = "") -> tuple[float, list[str]]:
    project_words = set(meaningful_words(str(project.get("project_title") or "") + " " +
                                         str(project.get("summary") or "")))
    candidate_words = set(meaningful_words(title + " " + description))
    shared = sorted(project_words & candidate_words)
    score = len(shared) / len(project_words) if project_words else 0.0
    return round(score, 3), shared


class PriorArtChecker:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(timeout=15, follow_redirects=True,
                                             headers={"User-Agent": "RadarInnowacji/1.0"})
        self.owns_client = client is None
        self.epo_key = os.getenv("EPO_OPS_KEY", "").strip()
        self.epo_secret = os.getenv("EPO_OPS_SECRET", "").strip()
        self.epo_token = None
        self.epo_token_expires = 0.0
        self.pbn_app_id = os.getenv("PBN_APP_ID", "").strip()
        self.pbn_app_token = os.getenv("PBN_APP_TOKEN", "").strip()
        self.interreg = None
        self.interreg_error = None

    def close(self) -> None:
        if self.owns_client:
            self.client.close()

    def _get(self, url: str, **kwargs: Any) -> httpx.Response:
        response = self.client.get(url, **kwargs)
        response.raise_for_status()
        return response

    def _epo(self, query: str) -> list[dict[str, Any]]:
        if not self.epo_key or not self.epo_secret:
            raise ValueError("Brak EPO_OPS_KEY lub EPO_OPS_SECRET")
        if not self.epo_token or time.monotonic() >= self.epo_token_expires:
            response = self.client.post("https://ops.epo.org/3.2/auth/accesstoken",
                                        auth=(self.epo_key, self.epo_secret),
                                        data={"grant_type": "client_credentials"})
            response.raise_for_status()
            self.epo_token = response.json()["access_token"]
            self.epo_token_expires = time.monotonic() + max(0, int(response.json().get("expires_in", 1200)) - 30)
        response = self.client.post(EPO_URL + "/published-data/search/biblio",
                        data={"q": 'ta all "' + " ".join(query.split()[:3]) + '"'},
                        headers={"Authorization": "Bearer " + self.epo_token,
                             "Accept": "application/xml", "X-OPS-Range": "1-25"})
        response.raise_for_status()
        root = ET.fromstring(response.content)
        results = root.find(".//{*}biblio-search")
        if results is None:
            raise ValueError("Nieprawidłowa odpowiedź EPO OPS")
        records = []
        for document in results.findall(".//{*}exchange-document"):
            title = next((" ".join(element.itertext()).strip() for element in
                          document.findall(".//{*}invention-title") if " ".join(element.itertext()).strip()), "")
            country = document.get("country", "")
            number = document.get("doc-number", "")
            kind = document.get("kind", "")
            if not title or not country or not number:
                continue
            identifier = country + number + kind
            abstract = " ".join(" ".join(element.itertext()) for element in document.findall(".//{*}abstract"))
            records.append({"source": "epo", "type": "patent", "title": title, "description": abstract,
                            "identifier": identifier, "url": "https://patents.google.com/patent/" + identifier})
        return records

    def _crossref(self, query: str) -> list[dict[str, Any]]:
        data = self._get("https://api.crossref.org/works", params={"query": query, "rows": 25}).json()
        items = data["message"]["items"]
        return [{"source": "crossref", "type": "publication", "title": item["title"][0],
                 "description": BeautifulSoup(item.get("abstract", ""), "html.parser").get_text(" "),
                 "identifier": item.get("DOI", ""), "url": item.get("URL", "")}
                for item in items if item.get("title") and isinstance(item["title"][0], str)]

    def _pbn(self, query: str) -> list[dict[str, Any]]:
        if not self.pbn_app_id or not self.pbn_app_token:
            raise ValueError("Brak PBN_APP_ID lub PBN_APP_TOKEN")
        response = self.client.post("https://pbn.nauka.gov.pl/api/v1/search/publications",
                                    headers={"X-App-Id": self.pbn_app_id, "X-App-Token": self.pbn_app_token},
                                    json={"title": query, "page": 0, "size": 25})
        response.raise_for_status()
        items = response.json()["content"]
        records = []
        for item in items:
            metadata = item.get("objectJson") or {}
            title = metadata.get("title")
            identifier = item.get("mongoId") or metadata.get("objectId") or ""
            if not isinstance(title, str) or not title.strip() or not identifier:
                continue
            doi = metadata.get("doi") or ""
            records.append({"source": "pbn", "type": "publication", "title": title,
                            "description": "", "identifier": str(identifier),
                            "url": "https://doi.org/" + doi if doi else
                            "https://pbn.nauka.gov.pl/core/#/search-start"})
        return records

    def _load_interreg(self) -> list[dict[str, Any]]:
        if self.interreg is not None:
            return self.interreg
        if self.interreg_error is not None:
            raise ValueError(self.interreg_error)
        try:
            page = self._get(INTERREG_URL)
            links = BeautifulSoup(page.text, "html.parser").find_all("a", href=True)
            files = [urljoin(INTERREG_URL, link["href"]) for link in links
                     if link["href"].split("?")[0].lower().endswith(".xlsx")
                     and "projekt" in link.get_text(" ").casefold()]
            if not files:
                raise ValueError("Nie znaleziono wykazu projektów XLSX")
            workbook = load_workbook(io.BytesIO(self._get(files[0]).content), read_only=True, data_only=True)
            records = []
            try:
                for sheet in workbook:
                    columns = None
                    for row in sheet.iter_rows(values_only=True):
                        if columns is None:
                            headers = [str(value or "").casefold() for value in row]
                            title = next((index for index, value in enumerate(headers) if "project title" in value), None)
                            description = next((index for index, value in enumerate(headers) if "project description" in value), None)
                            identifier = next((index for index, value in enumerate(headers) if "project no." in value), None)
                            if title is not None and description is not None and identifier is not None:
                                columns = (title, description, identifier)
                            continue
                        title, description, identifier = (row[index] for index in columns)
                        if isinstance(title, str) and title.strip() and identifier:
                            records.append({"source": "interreg", "type": "project", "title": title.strip(),
                                            "description": str(description or ""), "identifier": str(identifier),
                                            "url": files[0]})
                if not records:
                    raise ValueError("Wykaz Interreg nie zawiera rozpoznanych projektów")
                self.interreg = records
                return records
            finally:
                workbook.close()
        except (httpx.HTTPError, ValueError, KeyError, OSError, BadZipFile, InvalidFileException) as error:
            self.interreg_error = str(error)
            raise

    def check(self, project: dict[str, Any]) -> dict[str, Any]:
        query = search_query(project)
        statuses = {}
        matches = []
        sources = (("epo", lambda: self._epo(query)), ("pbn", lambda: self._pbn(query)),
               ("crossref", lambda: self._crossref(query)), ("interreg", self._load_interreg))
        for name, fetch in sources:
            if len(query.split()) < 2:
                statuses[name] = {"status": "skipped", "reason": "Za mało słów do wyszukiwania"}
                continue
            try:
                records = fetch()
                statuses[name] = {"status": "ok", "records_examined": len(records)}
                for record in records:
                    score, shared = similarity(project, record["title"], record["description"])
                    if len(shared) >= 2 and score >= 0.2:
                        matches.append({**record, "similarity": score, "shared_words": shared})
            except (httpx.HTTPError, ValueError, KeyError, TypeError, ET.ParseError, OSError,
                    BadZipFile, InvalidFileException) as error:
                statuses[name] = {"status": "unavailable", "reason": str(error)}
        matches.sort(key=lambda item: item["similarity"], reverse=True)
        return {"status": "matches_found" if matches else "inconclusive", "query": query,
                "sources": statuses, "matches": matches[:10]}