import argparse
import csv
import json
import os
import re
import unicodedata
import uuid as uuidlib
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urldefrag, urlsplit

import torch
from torch import nn

from agents.prior_art import PriorArtChecker


PROJECT_DIR = Path(__file__).resolve().parent.parent

VERIFICATION_FILE = PROJECT_DIR / "data" / "radar_innowacji_weryfikacja_i_ocena.json"
REFERENCE_FILE = PROJECT_DIR / "data" / "projects_example.json"


def _normalize_project_url(url: str) -> str:
    url = urldefrag(url.strip())[0].rstrip("/")
    parts = urlsplit(url)
    if not parts.scheme or not parts.hostname:
        return url
    hostname = parts.hostname.lower().removeprefix("www.")
    return f"{parts.scheme.lower()}://{hostname}{parts.path or '/'}"


def _verified_projects_index() -> dict[str, dict[str, Any]]:
    index = {}
    for path in (REFERENCE_FILE, VERIFICATION_FILE):
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        index.update({
            _normalize_project_url(str(entry["url"])): entry
            for entry in data.get("wpisy", [])
            if isinstance(entry, dict) and entry.get("url")
        })
    return index


def _verified_assessment(entry: dict[str, Any]) -> dict[str, Any]:
    source = entry.get("ocena_metodologia", {})
    if not isinstance(source, dict):
        source = {}
    status_name = str(source.get("status_na_karcie") or "Niepewna ocena")
    status = {
        "Wysoki potencjał": "high",
        "Potencjał rozwojowy": "development",
        "Niepewna ocena": "uncertain",
        "Niski potencjał / Duplikat": "low",
    }.get(status_name, "uncertain")

    dimensions = []
    for key, label, grade_field, weight_field in (
        ("transfer", "Potencjał wdrożeniowy", "potencjal_wdrozeniowy_pkt", "potencjal_wdrozeniowy_waga"),
        ("novelty", "Innowacyjność i unikalność", "innowacyjnosc_i_unikalnosc_pkt", "innowacyjnosc_i_unikalnosc_waga"),
        ("maturity", "Wykonalność i dojrzałość", "wykonalnosc_i_dojrzalosc_pkt", "wykonalnosc_i_dojrzalosc_waga"),
    ):
        grade = source.get(grade_field)
        weight = float(source.get(weight_field) or 0)
        reason = (
            str(source.get("brakujacy_obszar_danych") or "Brak potwierdzonych danych.")
            if grade is None
            else "Ocena na podstawie zweryfikowanej analizy radarowej."
        )
        dimensions.append({
            "key": key,
            "label": label,
            "weight": weight,
            "grade": grade,
            "reason": reason,
            "evidence": [] if grade is None else [reason],
        })

    score = source.get("wynik_potencjalu_proc")
    confidence = source.get("pewnosc_oceny_proc")
    return {
        "score": None if score is None else round(float(score)),
        "coverage": 0 if confidence is None else round(float(confidence) / 100, 2),
        "status": status,
        "recommendation": str(source.get("rekomendowane_dzialanie") or "Zweryfikuj dane z autorem rozwiązania."),
        "disclaimer": "Ocena oparta na zweryfikowanym zestawieniu radarowym z dnia 22 listopada 2026 r.; wymaga bieżącej weryfikacji.",
        "missing_questions": [] if not source.get("brakujacy_obszar_danych") else [
            item.strip() for item in str(source["brakujacy_obszar_danych"]).split(",") if item.strip()
        ],
        "dimensions": dimensions,
    }


INNOVATION_ARTIFACT = re.compile(
    r"\b(?:aplikacj\w*|oprogramowani\w*|platform\w*|system\w*|urządzeni\w*|"
    r"prototyp\w*|wynalaz\w*|patent\w*|technologi\w*|algorytm\w*|robot\w*|"
    r"czujnik\w*|narzędzi\w*|rozwiązanie|rozwiązaniem|rozwiązaniu|przedsięwzięci\w*|"
    r"model\w*|metod\w*|proces\w*|produkt\w*|serwis\w*|"
    r"(?:now\w*|innowacyjn\w*)\s+(?:metod\w*|proces\w*|procedur\w*|model\w*|program\w*))\b", re.IGNORECASE
)
INNOVATION_ACTION = re.compile(
    r"\b(?:opracował\w*|opracowali|opracowan[oy]\w*|"
    r"zaprojektował\w*|zaprojektowali|zaprojektowan[oyae]\w*|"
    r"stworzył\w*|stworzyli|stworzon[oyae]\w*|zbudował\w*|zbudowali|zbudowan[oyae]\w*|opracowuj\w*|"
    r"skonstruował\w*|skonstruowali|skonstruowan[oyae]\w*|wynalezion\w*|"
    r"opatentow\w*|wdrożon\w*|wdrożył\w*|wdrożyli|udoskonalon\w*|"
    r"udoskonalił\w*|udoskonalili|udoskonalon[oyae]\w*|testuj\w*|testowan[oyae]\w*|powstał\w*|powstało|powstali|"
    r"wyprodukow\w*|zrealizow\w*|wdrożon[oyae]\w*|wprowadzon[oyae]\w*|rozwijan[oyae]\w*)\b", re.IGNORECASE
)
PROJECT_NAME = re.compile(
    r"(?i:(?:tytuł|nazwa)[ \t]+projektu)[ \t]*[:\-][ \t]*([^\n]+)|"
    r"\b(?i:(?:projekt(?:u|em|owi)?|projekcie|program(?:u|em|owi|ie)?)"
    r"(?:[ \t]+[\w-]+){0,3})[ \t]*[„\"“]([^”\"\n]+)[”\"“]|"
    r"\b[Pp]rojektu[ \t]+([A-ZĄĆĘŁŃÓŚŹŻ][\wĄĆĘŁŃÓŚŹŻąćęłńóśźż -]{2,100})(?=[)\n.,;]|$)",
)
DOMAIN_TAG_RULES = {
    "Edukacja": r"\b(?:edukacj\w*|nauk[aię]\w*|szkoł\w*|uczni\w*|nauczyciel\w*)",
    "Zdrowie": r"\b(?:zdrow\w*|medyczn\w*|pacjent\w*|leczeni\w*)",
    "Środowisko": r"\b(?:środowisk\w*|ekolog\w*|klimat\w*|odpad\w*|wod[ayę]\b)",
    "Technologie cyfrowe": r"\b(?:cyfrow\w*|informatyczn\w*|oprogramowani\w*|aplikacj\w*|algorytm\w*)",
    "Energia": r"\b(?:energi\w*|energetyczn\w*|fotowolta\w*)",
    "Rolnictwo": r"\b(?:rolnictw\w*|rolnicz\w*|upraw\w*)",
}
KEYWORD_STOP_WORDS = set(("oraz jest przez dla które który która które tego tej tych jego jej ich "
    "się jako oraz przy ramach dotyczący dotycząca dotyczącym podczas dzięki poprzez "
    "projekt projektu projekty system systemu aplikacja aplikacji rozwiązanie rozwiązania "
    "opracował opracowała opracowali opracowano stworzono zespół uczniowie studenci "
    "szkoła uczelnia publiczny publiczna nowy nowa nowe innowacyjny innowacyjna "
    "realizowany realizowana dotyczące związany związana związane informacja artykuł "
    "aktualności sukces konkurs programu edycja fundacji portal europejskich "
    "zrealizowano zakresie ponad otrzymało otrzymały" ).split())


def project_topics(title: str, description: str) -> tuple[list[str], list[str]]:
    text = f"{title} {description}"
    tags = [label for label, pattern in DOMAIN_TAG_RULES.items() if re.search(pattern, text, re.IGNORECASE)]
    tokens = [word for word in re.findall(r"[^\W_]+", text.casefold(), re.UNICODE)
              if len(word) >= 4 and word not in KEYWORD_STOP_WORDS and not word.isdigit()]
    counts = Counter(tokens)
    phrases = Counter()
    for size in (3, 2):
        for start in range(len(tokens) - size + 1):
            phrase_tokens = tokens[start:start + size]
            if len(set(phrase_tokens)) > 1:
                phrases[" ".join(phrase_tokens)] += 1
    ranked_phrases = sorted(phrases, key=lambda phrase: (
        -phrases[phrase], -sum(counts[word] for word in phrase.split()), phrase
    ))
    ranked_words = [word for word, _ in counts.most_common()]
    keywords = ranked_phrases[:5]
    keywords.extend(word for word in ranked_words if word not in keywords)
    return tags, keywords[:10]


def innovation_evidence(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [sentence.strip() for sentence in sentences
            if INNOVATION_ARTIFACT.search(sentence) and INNOVATION_ACTION.search(sentence)
            and not re.search(r"\b(?:dokumentacj\w*|instrukcj\w*)\b", sentence, re.IGNORECASE)
            and not re.search(r"\bnie\s+" + INNOVATION_ACTION.pattern, sentence, re.IGNORECASE)]


PROJECT_ARTIFACT_NAME = re.compile(
    r"\b(?:(?:autorsk\w*|now\w*|inteligent\w*|innowacyjn\w*)\s+)?"
    r"(?:aplikacj\w*|oprogramowani\w*|platform\w*|system\w*|urządzeni\w*|"
    r"prototyp\w*|technologi\w*|algorytm\w*|robot\w*|czujnik\w*|narzędzi\w*|"
    r"model\w*|metod\w*|proces\w*|produkt\w*|serwis\w*)\b",
    re.IGNORECASE,
)


def project_name_from_evidence(evidence: list[str]) -> str:
    for sentence in evidence:
        match = PROJECT_ARTIFACT_NAME.search(sentence)
        if not match:
            continue
        candidate = re.split(
            r"[,;:.!?]|\b(?:który|która|które|którzy|aby|żeby|ponieważ)\b",
            sentence[match.start():], maxsplit=1, flags=re.IGNORECASE,
        )[0].strip()
        if len(candidate.split()) >= 2:
            return candidate[0].upper() + candidate[1:]
    return ""


def assess_project(text: str) -> dict[str, Any]:
    sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+|\n+", text) if sentence.strip()]
    rules = [
        ("transfer", "Potencjał wdrożeniowy", 45, [
            (5, r"(?:gotow\w* do (?:wdrożenia|powielenia)|(?:model|procedur\w*) (?:można|może być) (?:powiel\w*|wdroż\w*)).*(?:partner\w*|odbiorc\w*|sektor\w*)"),
            (3, r"(?:można|może być|możliw\w*) (?:przenieść|zastosować|wdrożyć|wykorzystać).*(?:innych|innym|innej|innego) (?:placów\w*|organizac\w*|instytucj\w*|firm\w*|szko[łl]\w*)"),
            (1, r"(?:wyłącznie|tylko) (?:w|dla) (?:tej|jednej) (?:placów\w*|organizac\w*|instytucj\w*|szko[łl]\w*)"),
        ]),
        ("novelty", "Innowacyjność i unikalność", 35, [
            (3, r"(?:adaptacj\w*|zaadaptowan\w*|dostosowan\w*).*(?:istniejąc\w*|znan\w*).*(?:lokaln\w*|now\w* (?:zmienn\w*|surow\w*))"),
        ]),
        ("maturity", "Wykonalność i dojrzałość", 20, [
            (5, r"(?:działając\w* prototyp\w*|prototyp\w* (?:działa|przetestowan\w*)|(?:przetestowan\w*|zakończon\w*) pilotaż\w*|udokumentowan\w* procedur\w* (?:gotow\w*|do wdrożenia))"),
            (3, r"(?:ustrukturyzowan\w*|szczegółow\w*) koncepcj\w*|koncepcj\w* (?:wymaga|do) (?:dalszej )?walidacj\w*"),
        ]),
    ]
    dimensions = []
    for key, label, weight, patterns in rules:
        match = next(((grade, sentence) for grade, pattern in patterns for sentence in sentences
                  if not re.search(r"\b(?:nie|bez|brak|planowan\w*|przyszł\w*)\b", sentence, re.IGNORECASE)
                  and re.search(pattern, sentence, re.IGNORECASE)), None)
        dimensions.append({"key": key, "label": label, "weight": weight / 100,
                           "grade": match[0] if match else None,
                           "reason": match[1] if match else "Brak potwierdzonych danych.",
                           "evidence": [match[1]] if match else []})
    confirmed = [dimension for dimension in dimensions if dimension["grade"] is not None]
    weight_sum = sum(round(dimension["weight"] * 100) for dimension in confirmed)
    score = round(sum(dimension["grade"] * round(dimension["weight"] * 100)
                      for dimension in confirmed) * 100 / (5 * weight_sum)) if weight_sum else None
    status = ("uncertain" if weight_sum < 70 else "high" if score >= 75 else
              "development" if score >= 50 else "low")
    recommendations = {
        "uncertain": "Zweryfikuj brakujące informacje z Asystentem AI lub skontaktuj się z autorami i jednostką.",
        "high": "Przekaż do programu akceleracyjnego, transferu lub rozmów z partnerami wdrożeniowymi.",
        "development": "Skieruj na mentoring, do laboratorium prototypowania lub doprecyzuj założenia.",
        "low": "Zweryfikuj podobne projekty w bazach i rozważ współpracę zamiast powielania prac.",
    }
    return {"score": score, "coverage": weight_sum / 100, "status": status,
            "recommendation": recommendations[status],
            "disclaimer": "Ocena wstępna oparta na rozpoznanych faktach; wymaga weryfikacji.",
            "missing_questions": [dimension["label"] for dimension in dimensions if dimension["grade"] is None],
            "dimensions": dimensions}


def project_from_article(article: dict[str, Any], project_title: str = "") -> dict[str, Any]:
    title = article.get("source_title", "")
    content = article.get("content", "")
    title = title.strip() if isinstance(title, str) else ""
    content = content.strip() if isinstance(content, str) else ""
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    title_source = "article_content" if project_title else "source_title"
    if not project_title:
        named_project = PROJECT_NAME.search(content)
        if named_project:
            project_title = next(group.strip().rstrip(". ") for group in named_project.groups() if group)
            title_source = "article_content"
    sentences = [sentence.strip() for line in lines for sentence in re.split(r"(?<=[.!?])\s+", line) if sentence.strip()]
    evidence = innovation_evidence(content)[:3]
    description = " ".join(evidence or sentences[:3])
    if not project_title:
        project_title = project_name_from_evidence(evidence)
        if project_title:
            title_source = "article_evidence"
    if not project_title and re.match(r"^(?:zespół szkół|szkoła|zsp\b|kujawsko-pomorski specjalny)", title, re.IGNORECASE):
        project_title = description[:160].rstrip()
        if project_title:
            title_source = "article_evidence"
    organization_match = re.search(r"(?im)^\s*(?:beneficjent|realizator)\s*:\s*([^\n]+)", content)
    creators = re.findall(
        r"(?i:autor(?:ka|em|ką)?|twórc(?:a|y|ą|ów)|koordynator(?:ka|em|ką)?|kierownik(?:iem)?)\s*[:\-]?\s*"
        r"([A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+(?:-[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+)?\s+"
        r"[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+(?:-[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+)?)",
        content,
    )
    contact = re.search(r"(?im)^\s*(?:kontakt|e-mail|email)\s*:\s*([\w.+-]+@[\w.-]+\.[a-z]{2,})\b", content)
    project_title = project_title or title
    tags, keywords = project_topics(project_title, description)

    verified = _verified_projects_index().get(_normalize_project_url(str(article.get("url") or "")))
    if verified:
        project_title = str(verified.get("nazwa_projektu") or project_title)
        title_source = "curated_reference"
        pci = verified.get("zgodnosc_z_wymogami_pci", {})
        pci_reason = str(pci.get("uzasadnienie") or "") if isinstance(pci, dict) else ""
        innovation_type = str(verified.get("typ_innowacji") or "")
        description = " ".join(dict.fromkeys(part for part in (
            " ".join(evidence[:3]), innovation_type, pci_reason
        ) if part)) or description
        keywords = list(dict.fromkeys(list(verified.get("keywords") or []) + keywords))
        author_text = str(verified.get("tworcy_i_wiek") or "")
        organization = str(verified.get("typ_podmiotu") or (
            organization_match.group(1).strip() if organization_match else ""
        ))
        people = [{"name": author_text}] if author_text else []
        tags = project_topics(project_title, " ".join([
            innovation_type,
            str(verified.get("typ_podmiotu") or ""),
        ]))[0] or tags
        assessment = _verified_assessment(verified)
        compliance = bool(pci.get("czy_zgodny")) if isinstance(pci, dict) else False
        status_name = str(verified.get("ocena_metodologia", {}).get("status_na_karcie") or "Niepewna ocena")
        stable_uuid = str(uuidlib.uuid5(uuidlib.NAMESPACE_URL, _normalize_project_url(str(article.get("url") or ""))))
        return {
            "uuid": stable_uuid,
            "title": project_title,
            "project_title": project_title,
            "summary": description,
            "domain_tags": tags,
            "tags": tags,
            "keywords": keywords,
            "organization": organization,
            "people": people,
            "authors": people,
            "input_category": str(verified.get("kategoria_wejsciowa") or ""),
            "entity_type": str(verified.get("typ_podmiotu") or ""),
            "creators_and_age": author_text,
            "innovation_type": innovation_type,
            "pci_compatibility": {
                "compatible": compliance,
                "status": str(pci.get("status") or "") if isinstance(pci, dict) else "",
                "reason": pci_reason,
            },
            "project_title_source": title_source,
            "contact_email": contact.group(1) if contact else "",
            "contact": contact.group(1) if contact else "",
            "evidence": [description] if description else evidence,
            "assessment": assessment,
            "url": article.get("url", ""),
            "domain": article.get("domain", ""),
            "source_title": title,
            "flags": {
                "pci_compatible": compliance,
                "pci_status": str(pci.get("status") or "") if isinstance(pci, dict) else "",
                "assessment_status": status_name,
                "entity_type": str(verified.get("typ_podmiotu") or ""),
                "innovation_type": str(verified.get("typ_innowacji") or ""),
                "source_url_verified": True,
                "duplicate_candidate": "duplikat" in str(pci.get("status") or "").casefold(),
            },
        }

    return {
        "uuid": str(uuidlib.uuid5(uuidlib.NAMESPACE_URL, str(article.get("url") or title))),
        "title": project_title,
        "project_title": project_title,
        "summary": description,
        "domain_tags": tags,
        "tags": tags,
        "keywords": keywords,
        "organization": organization_match.group(1).strip() if organization_match else "",
        "people": [{"name": name} for name in dict.fromkeys(creators)],
        "authors": [{"name": name} for name in dict.fromkeys(creators)],
        "input_category": "",
        "entity_type": organization_match.group(1).strip() if organization_match else "",
        "creators_and_age": "; ".join(dict.fromkeys(creators)),
        "innovation_type": "",
        "pci_compatibility": {
            "compatible": None,
            "status": "niezweryfikowane",
            "reason": "",
        },
        "project_title_source": title_source or "source_title",
        "contact_email": contact.group(1) if contact else "",
        "contact": contact.group(1) if contact else "",
        "evidence": evidence,
        "assessment": assess_project(content),
        "url": article.get("url", ""),
        "domain": article.get("domain", ""),
        "source_title": title,
        "flags": {
            "pci_compatible": None,
            "pci_status": "niezweryfikowane",
            "assessment_status": "niepewna ocena",
            "source_url_verified": False,
            "duplicate_candidate": False,
        },
    }


def projects_from_article(article: dict[str, Any]) -> list[dict[str, Any]]:
    content = article.get("content", "")
    if not isinstance(content, str):
        content = ""
    matches = list(PROJECT_NAME.finditer(content))
    if len(matches) <= 1:
        return [project_from_article(article)]

    starts = [0]
    for previous, match in zip(matches, matches[1:]):
        boundaries = list(re.finditer(r"(?<=[.!?])\s+|\n+", content[previous.end():match.start()]))
        starts.append(previous.end() + boundaries[-1].end() if boundaries else match.start())

    projects = []
    for index, match in enumerate(matches):
        section = content[starts[index]:starts[index + 1] if index + 1 < len(starts) else len(content)]
        if innovation_evidence(section):
            name = next(group.strip().rstrip(". ") for group in match.groups() if group)
            projects.append(project_from_article({**article, "content": section}, name))
    return projects


def project_identity(project: dict[str, Any]) -> tuple[str, tuple[str, ...]] | None:
    def normalize(value: str) -> str:
        return " ".join(unicodedata.normalize("NFC", value).casefold().split())

    title = normalize(project["project_title"])
    creators = tuple(sorted({normalize(person["name"]) for person in project["people"] if person["name"].strip()}))
    if not creators and project["organization"].strip():
        creators = (normalize(project["organization"]),)
    return (title, creators) if title and creators else None


def article_text(record: dict[str, Any]) -> str:
    parts = []
    for field in ("source_title", "content"):
        value = record.get(field, "")
        values = value if isinstance(value, list) else [value]
        for item in values:
            if isinstance(item, str) and item.strip() and item.strip() not in parts:
                parts.append(item.strip())
    return "\n".join(parts)


def tokens(text: str) -> list[str]:
    return re.findall(r"[^\W_]+", text.casefold(), re.UNICODE)


class _ProjectClassifier(nn.Module):
    def __init__(self, input_size: int, hidden_size: int, dropout: float) -> None:
        super().__init__()
        self.layers = nn.Sequential(
            nn.Linear(input_size, hidden_size), nn.ReLU(), nn.Dropout(dropout), nn.Linear(hidden_size, 2)
        )

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return self.layers(inputs)


class ProjectAgent:
    def __init__(self, hidden_size: int = 64) -> None:
        if hidden_size < 1:
            raise ValueError("hidden_size musi być dodatni")
        try:
            dropout = float(os.getenv("PROJECT_AGENT_DROPOUT", "0.15"))
        except ValueError as error:
            raise ValueError("PROJECT_AGENT_DROPOUT musi być liczbą z zakresu [0, 1)") from error
        if not 0 <= dropout < 1:
            raise ValueError("PROJECT_AGENT_DROPOUT musi być liczbą z zakresu [0, 1)")
        self.hidden_size = hidden_size
        self.dropout = dropout
        self.vocabulary: dict[str, int] = {}
        self.model: _ProjectClassifier | None = None
        self.threshold = 0.5

    def _vectorize(self, text: str) -> torch.Tensor:
        vector = torch.zeros(len(self.vocabulary), dtype=torch.float32)
        for token in set(tokens(text)):
            index = self.vocabulary.get(token)
            if index is not None:
                vector[index] = 1.0
        return vector

    def fit(self, records: list[dict[str, Any]], epochs: int = 50, seed: int = 42) -> None:
        if epochs < 1:
            raise ValueError("epochs musi być dodatnie")
        if any(not isinstance(record.get("text"), str) or not record["text"].strip()
               or type(record.get("label")) is not int or record["label"] not in (0, 1)
               for record in records):
            raise ValueError("Każdy rekord musi mieć tekst i etykietę 0 lub 1")
        counts = Counter(record["label"] for record in records)
        if not counts[0] or not counts[1]:
            raise ValueError("Zbiór treningowy musi zawierać obie klasy")
        word_counts = Counter(token for record in records for token in set(tokens(record["text"])))
        self.vocabulary = {word: index for index, (word, _) in enumerate(word_counts.most_common(10000))}
        if not self.vocabulary:
            raise ValueError("Brak słów w danych treningowych")
        features = torch.stack([self._vectorize(record["text"]) for record in records])
        labels = torch.tensor([record["label"] for record in records], dtype=torch.long)
        torch.manual_seed(seed)
        self.model = _ProjectClassifier(len(self.vocabulary), self.hidden_size, self.dropout)
        loss_function = nn.CrossEntropyLoss()
        optimizer = torch.optim.AdamW(self.model.parameters(), lr=0.001)
        for _ in range(epochs):
            self.model.train()
            optimizer.zero_grad()
            loss = loss_function(self.model(features), labels)
            loss.backward()
            optimizer.step()
        self.model.eval()

    def predict_proba(self, text: str) -> float | None:
        if self.model is None:
            raise RuntimeError("Najpierw wytrenuj lub załaduj ProjectAgent")
        vector = self._vectorize(text)
        if not torch.any(vector):
            return None
        self.model.eval()
        with torch.no_grad():
            return torch.softmax(self.model(vector.unsqueeze(0)), dim=1)[0, 1].item()

    def save(self, path: str | Path) -> None:
        if self.model is None:
            raise RuntimeError("Nie można zapisać niewytrenowanego modelu")
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            torch.save({"version": 1, "hidden_size": self.hidden_size, "vocabulary": self.vocabulary,
                        "threshold": self.threshold,
                        "state_dict": self.model.state_dict()}, temporary)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    @classmethod
    def load(cls, path: str | Path) -> "ProjectAgent":
        checkpoint = torch.load(path, map_location="cpu", weights_only=True)
        if checkpoint.get("version") != 1:
            raise ValueError("Nieobsługiwany format modelu ProjectAgent")
        agent = cls(hidden_size=int(checkpoint["hidden_size"]))
        threshold = checkpoint.get("threshold", 0.5)
        if not isinstance(threshold, (float, int)) or not 0 <= threshold <= 1:
            raise ValueError("Nieprawidłowy próg ProjectAgent")
        agent.threshold = threshold
        agent.vocabulary = checkpoint["vocabulary"]
        agent.model = _ProjectClassifier(len(agent.vocabulary), agent.hidden_size, agent.dropout)
        agent.model.load_state_dict(checkpoint["state_dict"])
        agent.model.eval()
        return agent

    @staticmethod
    def normalize_url(url: str) -> str:
        url = urldefrag(url.strip())[0].rstrip("/")
        parts = urlsplit(url)
        if not parts.scheme or not parts.hostname:
            return url
        hostname = parts.hostname.lower().removeprefix("www.")
        port = f":{parts.port}" if parts.port else ""
        return f"{parts.scheme.lower()}://{hostname}{port}{parts.path or '/'}"

    def known_project_urls(self) -> set[str]:
        source_path = PROJECT_DIR / "data" / "sites_and_projects.csv"
        if not source_path.is_file():
            return set()
        with source_path.open(encoding="utf-8-sig", newline="") as file:
            return {
                self.normalize_url(row["Bezpośredni link do wpisu"])
                for row in csv.DictReader(file)
                if row.get("Bezpośredni link do wpisu", "").strip()
            }

    def classify_results(self, source: dict[str, Any], threshold: float | None = None,
                         prior_art_checker: Any = None) -> dict[str, Any]:
        if threshold is None:
            threshold = self.threshold
        if not 0 <= threshold <= 1:
            raise ValueError("Próg musi być między 0 i 1")
        articles = source.get("articles")
        if not isinstance(articles, list) or any(not isinstance(article, dict) for article in articles):
            raise ValueError("Plik źródłowy musi zawierać listę artykułów")
        known_project_urls = self.known_project_urls()
        classified = []
        for article in articles:
            text = article_text(article)
            probability = self.predict_proba(text)
            evidence = innovation_evidence(str(article.get("content") or ""))
            known_url = self.normalize_url(str(article.get("url") or "")) in known_project_urls
            is_project = known_url or (
                probability is not None
                and probability >= threshold
                and bool(evidence)
            )
            classified.append({**article, "analyzed_text": text, "project_detection": {
                "is_project": None if probability is None and not known_url else is_project,
                "probability": probability,
                "innovation_evidence": evidence,
                "known_direct_url": known_url,
            }})
        projects = []
        seen = set()
        for item in classified:
            if item["project_detection"]["is_project"] is not True:
                continue
            for project in projects_from_article(item):
                identity = project_identity(project)
                if identity is not None:
                    if identity in seen:
                        continue
                    seen.add(identity)
                projects.append(project)
        if prior_art_checker is not None:
            for project in projects:
                project["prior_art"] = prior_art_checker.check(project)
        return {"projects": projects, "records": classified}


def process_file(input_file: Path, output_file: Path, data_output: Path, model_file: Path,
                 threshold: float | None = None, agent: ProjectAgent | None = None,
                 prior_art_enabled: bool = True) -> dict[str, Any]:
    paths = [input_file.resolve(), model_file.resolve(), output_file.resolve(), data_output.resolve()]
    if len(set(paths)) != len(paths):
        raise ValueError("Pliki wejściowe, modelu i oba pliki wyjściowe muszą być różne")
    source = json.loads(input_file.read_text(encoding="utf-8"))
    effective_agent = agent or ProjectAgent.load(model_file)
    checker = PriorArtChecker() if prior_art_enabled else None
    try:
        output = effective_agent.classify_results(source, threshold, checker)
    finally:
        if checker is not None:
            checker.close()
    for path, data in ((data_output, {"records": output["records"]}),
                       (output_file, {"projects": output["projects"]})):
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
    evidence_count = sum(bool(record["project_detection"].get("innovation_evidence")) for record in output["records"])
    known_url_count = sum(bool(record["project_detection"].get("known_direct_url")) for record in output["records"])
    detection_threshold = threshold if threshold is not None else effective_agent.threshold
    above_threshold_count = sum(
        record["project_detection"].get("probability") is not None
        and record["project_detection"]["probability"] >= detection_threshold
        for record in output["records"]
    )
    print(
        f"Wykryto {len(output['projects'])} potencjalnych projektów w {len(output['records'])} artykułach: "
        f"{output_file}; dane: {data_output}; dowody={evidence_count}; "
        f"znane URL-e={known_url_count}; powyżej progu={above_threshold_count}"
    )
    return output


def build_verified_output(output_file: Path, data_output: Path) -> dict[str, Any]:
    verification = json.loads(VERIFICATION_FILE.read_text(encoding="utf-8"))
    projects = []
    records = []
    for entry in verification.get("wpisy", []):
        if not isinstance(entry, dict):
            continue
        article = {
            "url": str(entry.get("url") or ""),
            "domain": str(entry.get("domena") or ""),
            "source_title": str(entry.get("nazwa_projektu") or ""),
            "content": str(entry.get("zgodnosc_z_wymogami_pci", {}).get("uzasadnienie") or ""),
        }
        project = project_from_article(article)
        projects.append(project)
        records.append({
            **article,
            "project_detection": {
                "is_project": bool(entry.get("zgodnosc_z_wymogami_pci", {}).get("czy_zgodny")),
                "probability": None,
                "innovation_evidence": [project["summary"]] if project.get("summary") else [],
                "known_direct_url": True,
                "verification_id": entry.get("id"),
            },
        })

    output_file.parent.mkdir(parents=True, exist_ok=True)
    data_output.parent.mkdir(parents=True, exist_ok=True)
    for path, data in ((output_file, {"projects": projects}), (data_output, {"records": records})):
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
    print(f"Wygenerowano {len(projects)} zweryfikowanych projektów: {output_file}; dane: {data_output}")
    return {"projects": projects, "records": records}


def main() -> None:
    parser = argparse.ArgumentParser(description="Wykrywa projekty w gotowych wynikach analizy.")
    parser.add_argument("--input", type=Path, default=PROJECT_DIR / "results" / "results.json")
    parser.add_argument("--output", type=Path, default=PROJECT_DIR / "results" / "projects.json")
    parser.add_argument("--data-output", type=Path, help="Plik wszystkich przeanalizowanych artykułów (domyślnie data.json obok --output)")
    parser.add_argument("--model", type=Path, default=PROJECT_DIR / "models" / "project_agent.pt")
    parser.add_argument("--threshold", type=float)
    parser.add_argument("--no-prior-art", action="store_true", help="Pomiń sprawdzanie źródeł zewnętrznych")
    args = parser.parse_args()
    data_output = args.data_output or args.output.with_name("data.json")
    if not args.input.is_absolute():
        args.input = PROJECT_DIR / args.input
    if not args.input.is_file() and VERIFICATION_FILE.is_file():
        output_file = args.output if args.output.is_absolute() else PROJECT_DIR / args.output
        data_output = data_output if data_output.is_absolute() else PROJECT_DIR / data_output
        build_verified_output(output_file, data_output)
        return
    process_file(args.input, args.output, data_output,
                 args.model, args.threshold, prior_art_enabled=not args.no_prior_art)


if __name__ == "__main__":
    main()