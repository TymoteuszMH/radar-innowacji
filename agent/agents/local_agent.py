import csv
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any, Sequence

import torch
from dotenv import load_dotenv
from torch import nn

from logging_utils import get_logger
from .content_utils import extract_main_text


PROJECT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_DIR / ".env")
_TOKEN_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)
_SENTENCE_PATTERN = re.compile(r"(?<=[.!?])\s+")
_DATE_PATTERN = re.compile(
    r"(?<![\d./-])(?:\d{4}-\d{2}-\d{2}|\d{1,2}\.\d{1,2}\.\d{4}|"
    r"\d{1,2}-\d{1,2}-\d{4})(?![\d./-])"
)
_AMOUNT_PATTERN = re.compile(
    r"\b\d[\d\s.,]*(?:\s*(?:tys\.?|tysięcy|mln|milionów))?\s*(?:zł(?:otych)?|PLN|EUR|euro)\b",
    re.IGNORECASE,
)
_PERSON_PATTERN = re.compile(
    r"\b(?:(?:dr|mgr|prof(?:esor)?|inż)\.?\s+)?"
    r"([A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+(?:-[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+)?"
    r"(?:\s+[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+(?:-[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+)?){1,2})"
)
_PERSON_ROLE_PREFIXES = {
    "koordynator", "koordynatorka", "opiekun", "opiekunka", "autor", "autorka",
    "lider", "liderka", "prezes", "prezeska", "dyrektor", "dyrektorka",
    "kierownik", "kierowniczka", "nauczyciel", "nauczycielka", "badacz",
    "badaczka", "profesor", "koordynatora", "koordynatorki",
}
_PERSON_EXCLUDED_TERMS = {
    "urząd", "urzędem", "urzed", "ministerstwo", "ministerstwa", "ministerstwem",
    "związek", "związkiem", "związku", "szkoła", "szkoły", "szkole", "szkołą",
    "fundacja", "fundacji", "fundacją", "miasto", "miasta", "miastem", "gmina",
    "gminy", "gminą", "powiat", "powiatu", "starostwo", "starostwa", "kuratorium",
    "uniwersytet", "uniwersytetu", "politechnika", "politechniki", "instytut", "instytutu",
    "centrum", "akademia", "akademii", "stowarzyszenie", "stowarzyszenia", "klub", "klubu",
}
_RESPONSIBILITY_PATTERN = re.compile(
    r"\b(?:koordynatorka|koordynator|odpowiada|prowadzi|kieruje|opiekunka|opiekun|"
    r"autorka|autor|liderka|lider|prezeska|prezes|dyrektorka|dyrektor|"
    r"kierowniczka|kierownik|realizuje)\b",
    re.IGNORECASE,
)
_PROJECT_KEYWORDS = (
    "projekt", "badani", "badawc", "innowac", "wdroż", "patent", "prototyp",
    "inwestyc", "grant", "pilotaż", "opracowano", "uruchomiono",
)
LOGGER = get_logger("local_agent")
csv.field_size_limit(2**31 - 1)


class _TextClassifier(nn.Module):
    def __init__(self, input_size: int, hidden_size: int) -> None:
        super().__init__()
        self.layers = nn.Sequential(
            nn.Linear(input_size, hidden_size),
            nn.ReLU(),
            nn.Dropout(0.15),
            nn.Linear(hidden_size, 2),
        )

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return self.layers(inputs)


class LocalAgent:
    """Trainable local text classifier for article-versus-junk detection."""

    def __init__(
        self,
        model_path: str | Path | None = None,
        hidden_size: int | None = None,
        load_existing: bool = True,
        input_dir: str | Path | None = None,
        output_file: str | Path | None = None,
    ) -> None:
        project_dir = PROJECT_DIR
        configured_path = Path(model_path or os.getenv("LOCAL_AGENT_MODEL_PATH", "models/local_agent.pt"))
        self.model_path = (
            configured_path if configured_path.is_absolute() else project_dir / configured_path
        )
        input_path = Path(input_dir or os.getenv("SCRAPPED_DIR", "data/scrapped"))
        output_path = Path(output_file or os.getenv("ANALYSIS_OUTPUT_FILE", "results/results.json"))
        self.input_dir = input_path if input_path.is_absolute() else project_dir / input_path
        self.output_file = output_path if output_path.is_absolute() else project_dir / output_path
        self.hidden_size = hidden_size or int(os.getenv("LOCAL_AGENT_HIDDEN_SIZE", "64"))
        self.vocabulary: dict[str, int] = {}
        self.model: _TextClassifier | None = None
        if self.hidden_size < 1:
            raise ValueError("hidden_size musi wynosić co najmniej 1")
        if load_existing and self.model_path.is_file():
            self.load()

    def _load_records(self) -> list[dict[str, str]]:
        if not self.input_dir.is_dir():
            LOGGER.warning("Nie znaleziono folderu z danymi: %s", self.input_dir)
            return []

        records: list[dict[str, str]] = []
        seen_urls: set[str] = set()
        files = sorted(self.input_dir.rglob("*.json")) + sorted(self.input_dir.rglob("*.csv"))
        for path in files:
            try:
                if path.suffix.lower() == ".json":
                    data = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        default_domain = data.get("domain", path.stem)
                        items = data.get("articles", [data])
                    elif isinstance(data, list):
                        default_domain, items = path.stem, data
                    else:
                        continue
                else:
                    default_domain = path.stem
                    with path.open(encoding="utf-8-sig", newline="") as csv_file:
                        items = list(csv.DictReader(csv_file))

                for values in items:
                    if not isinstance(values, dict):
                        continue
                    record = {
                        key: (value.strip() if isinstance(value, str) else "")
                        for key, value in {
                            "domain": values.get("domain", default_domain),
                            "url": values.get("url", ""),
                            "title": values.get("title", ""),
                            "content": values.get("content", ""),
                            "crawler_category": values.get("crawler_category", ""),
                        }.items()
                    }
                    if record["url"] and record["content"] and record["url"] not in seen_urls:
                        records.append(record)
                        seen_urls.add(record["url"])
            except (OSError, csv.Error, json.JSONDecodeError, TypeError) as error:
                LOGGER.error("Nie udało się odczytać %s: %s", path, error)
        return records

    @staticmethod
    def _tokens(text: str) -> list[str]:
        return [token.casefold() for token in _TOKEN_PATTERN.findall(text)]

    @staticmethod
    def _record_text(record: dict[str, Any]) -> str:
        title = record.get("title", "")
        title = title.strip() if isinstance(title, str) else ""
        content = record.get("content", "")
        content = extract_main_text(content) if isinstance(content, str) else ""
        return "\n".join(value for value in (title, content) if value)

    @staticmethod
    def _label(record: dict[str, Any]) -> int:
        label = record.get("is_article", record.get("label"))
        if label is True or label == 1 or label == "article":
            return 1
        if label is False or label == 0 or label == "junk":
            return 0
        raise ValueError("Każdy rekord treningowy musi mieć etykietę is_article lub label")

    def _vectorize(self, text: str) -> torch.Tensor:
        vector = torch.zeros(len(self.vocabulary), dtype=torch.float32)
        for token in set(self._tokens(text)):
            index = self.vocabulary.get(token)
            if index is not None:
                vector[index] = 1.0
        return vector

    def fit(
        self,
        records: Sequence[dict[str, Any]],
        epochs: int | None = None,
        learning_rate: float | None = None,
        batch_size: int | None = None,
        validation_fraction: float | None = None,
        seed: int = 42,
    ) -> dict[str, float]:
        if len(records) < 4:
            raise ValueError("Do treningu potrzebne są co najmniej 4 rekordy")
        epochs = epochs or int(os.getenv("LOCAL_AGENT_TRAIN_EPOCHS", "25"))
        learning_rate = learning_rate or float(os.getenv("LOCAL_AGENT_LEARNING_RATE", "0.001"))
        batch_size = batch_size or int(os.getenv("LOCAL_AGENT_BATCH_SIZE", "32"))
        validation_fraction = (
            validation_fraction
            if validation_fraction is not None
            else float(os.getenv("LOCAL_AGENT_VALIDATION_FRACTION", "0.2"))
        )
        if epochs < 1 or learning_rate <= 0 or batch_size < 1:
            raise ValueError("epochs, learning_rate i batch_size muszą być dodatnie")
        if not 0 < validation_fraction < 1:
            raise ValueError("validation_fraction musi być między 0 i 1")

        examples = [(self._record_text(record), self._label(record)) for record in records]
        if any(not text for text, _ in examples):
            raise ValueError("Każdy rekord treningowy musi mieć tytuł lub treść")
        counts = Counter(token for text, _ in examples for token in self._tokens(text))
        self.vocabulary = {
            token: index
            for index, (token, _) in enumerate(
                sorted(counts.items(), key=lambda item: (-item[1], item[0]))
            )
        }
        if not self.vocabulary:
            raise ValueError("Nie znaleziono tokenów do treningu")

        generator = torch.Generator().manual_seed(seed)
        order = torch.randperm(len(examples), generator=generator).tolist()
        validation_size = max(1, round(len(order) * validation_fraction))
        validation_indexes = order[:validation_size]
        training_indexes = order[validation_size:]
        if len({examples[index][1] for index in training_indexes}) < 2:
            raise ValueError("Zbiór treningowy musi zawierać obie klasy")

        features = torch.stack([self._vectorize(text) for text, _ in examples])
        labels = torch.tensor([label for _, label in examples], dtype=torch.long)
        self.model = _TextClassifier(len(self.vocabulary), self.hidden_size)
        optimizer = torch.optim.AdamW(self.model.parameters(), lr=learning_rate)
        loss_function = nn.CrossEntropyLoss()

        for _ in range(epochs):
            self.model.train()
            shuffled = torch.tensor(training_indexes)[torch.randperm(len(training_indexes), generator=generator)]
            for batch_start in range(0, len(shuffled), batch_size):
                batch_indexes = shuffled[batch_start:batch_start + batch_size]
                logits = self.model(features[batch_indexes])
                loss = loss_function(logits, labels[batch_indexes])
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

        self.model.eval()
        with torch.no_grad():
            validation_logits = self.model(features[validation_indexes])
            validation_loss = loss_function(
                validation_logits,
                labels[validation_indexes],
            ).item()
            accuracy = (
                (validation_logits.argmax(dim=1) == labels[validation_indexes])
                .float()
                .mean()
                .item()
            )
        return {"validation_accuracy": accuracy, "validation_loss": validation_loss}

    def predict_proba(self, text: str | dict[str, Any]) -> dict[str, float]:
        if self.model is None:
            raise RuntimeError("LocalAgent nie ma wytrenowanego ani załadowanego modelu")
        input_text = self._record_text(text) if isinstance(text, dict) else text
        self.model.eval()
        with torch.no_grad():
            probabilities = torch.softmax(
                self.model(self._vectorize(input_text).unsqueeze(0)),
                dim=1,
            )[0]
        return {"junk": probabilities[0].item(), "article": probabilities[1].item()}

    def classify(self, text: str | dict[str, Any]) -> str:
        probabilities = self.predict_proba(text)
        return max(probabilities, key=probabilities.get)

    @staticmethod
    def _sentences(text: str) -> list[str]:
        return [sentence.strip() for sentence in _SENTENCE_PATTERN.split(text) if sentence.strip()]

    @staticmethod
    def _project_type(text: str) -> str:
        value = text.casefold()
        if "patent" in value:
            return "patent"
        if any(term in value for term in ("badani", "badawc", "eksperyment")):
            return "projekt badawczy"
        if any(term in value for term in ("inwestyc", "dofinans", "grant", "złotych", "euro")):
            return "inwestycja"
        if any(term in value for term in ("wdroż", "uruchomiono", "zastosowano")):
            return "wdrożenie"
        if "pomysł" in value or "koncepcj" in value:
            return "pomysł"
        return "inne"

    @staticmethod
    def _project_stage(text: str) -> str:
        value = text.casefold()
        if any(term in value for term in ("zakończono", "zakończył", "zrealizowano", "ukończono")):
            return "zakończony"
        if "komercjaliz" in value:
            return "komercjalizacja"
        if any(term in value for term in ("wdrożono", "wdrażan", "wdrożeni")):
            return "wdrożenie"
        if any(term in value for term in ("testy", "testuj", "testowan", "pilotaż")):
            return "testy"
        if "prototyp" in value:
            return "prototyp"
        if any(term in value for term in ("badani", "analizę", "analiza")):
            return "badania"
        if any(term in value for term in ("planowan", "planuje", "pomysł", "koncepcj")):
            return "pomysł"
        return "nieustalony"

    @staticmethod
    def _extract_people(sentences: list[str]) -> list[dict[str, str]]:
        people: list[dict[str, str]] = []
        for sentence in sentences:
            responsibility = _RESPONSIBILITY_PATTERN.search(sentence)
            if not responsibility:
                continue
            role = responsibility.group(0).casefold()
            for match in _PERSON_PATTERN.finditer(sentence):
                name_parts = match.group(1).split()
                while name_parts and name_parts[0].casefold().rstrip(".") in _PERSON_ROLE_PREFIXES:
                    name_parts.pop(0)
                if len(name_parts) < 2:
                    continue
                name = " ".join(name_parts)
                normalized_parts = {part.casefold().strip(".,:;()") for part in name_parts}
                if normalized_parts & _PERSON_EXCLUDED_TERMS:
                    continue
                if all(person["name"] != name for person in people):
                    people.append({"name": name, "role": role})
                    if len(people) == 5:
                        return people
        return people

    @classmethod
    def _format_record(
        cls,
        record: dict[str, str],
        probabilities: dict[str, float],
        threshold: float,
    ) -> dict[str, Any]:
        main_text = extract_main_text(record["content"])
        text = f"{record['title']}\n{main_text}".strip()
        folded = text.casefold()
        sentences = cls._sentences(text)
        crawler_category = record.get("crawler_category", "")
        crawler_labeled = crawler_category in {"article", "listing", "sitemap", "other"}
        is_article = (
            crawler_category == "article"
            if crawler_labeled
            else probabilities["article"] >= threshold
        )
        relevant = is_article and any(keyword in folded for keyword in _PROJECT_KEYWORDS)
        local_prediction = max(probabilities, key=probabilities.get)
        if local_prediction == "junk" and probabilities["junk"] > 0.85:
            relevant = False
        stage = cls._project_stage(text) if relevant else "nieustalony"
        people = cls._extract_people(sentences)

        date_match = _DATE_PATTERN.search(text)
        amount_match = _AMOUNT_PATTERN.search(text)
        evidence = [
            sentence for sentence in sentences
            if any(keyword in sentence.casefold() for keyword in _PROJECT_KEYWORDS)
        ][:3]
        facts = [
            sentence for sentence in sentences
            if _DATE_PATTERN.search(sentence)
            or _AMOUNT_PATTERN.search(sentence)
            or any(keyword in sentence.casefold() for keyword in _PROJECT_KEYWORDS)
        ][:5]
        summary = " ".join(sentences[:2])[:700] if is_article else ""
        missing_information = []
        if relevant:
            if not people:
                missing_information.append("osoby odpowiedzialne")
            if not date_match:
                missing_information.append("data publikacji lub realizacji")
            if not amount_match:
                missing_information.append("wartość finansowania")
            if stage == "nieustalony":
                missing_information.append("etap projektu")

        return {
            "domain": record["domain"],
            "url": record["url"],
            "source_title": record["title"],
            "is_article": is_article,
            "crawler_category": record.get("crawler_category", ""),
            "local_prediction": local_prediction,
            "classification_source": "crawler_agent" if crawler_labeled else "local_agent",
            "relevant": relevant,
            "discard_reason": "" if is_article else "Klasyfikator lokalny ocenił tekst jako nie-artykuł.",
            "published_at": date_match.group(0) if date_match else "",
            "project_type": cls._project_type(text) if relevant else "inne",
            "project_title": record["title"] if relevant else "",
            "summary": summary,
            "stage": stage,
            "people": people,
            "organization": "",
            "investment": amount_match.group(0) if amount_match else "",
            "facts": facts,
            "missing_information": missing_information,
            "evidence": evidence,
            "probabilities": probabilities,
            "extraction_method": "local_rules",
        }

    def analyze_all(self) -> dict[str, int]:
        if self.model is None:
            raise RuntimeError("LocalAgent nie ma wytrenowanego ani załadowanego modelu")
        records = self._load_records()
        max_records = int(os.getenv("MAX_ARTICLES_TO_PROCESS", "0"))
        skipped = max(0, len(records) - max_records) if max_records else 0
        if max_records:
            records = records[:max_records]

        threshold = float(os.getenv("LOCAL_AGENT_ARTICLE_THRESHOLD", "0.5"))
        if not 0 <= threshold <= 1:
            raise ValueError("LOCAL_AGENT_ARTICLE_THRESHOLD musi być między 0 i 1")

        results: list[dict[str, Any]] = []
        article_count = 0
        LOGGER.info("Lokalna analiza treści: %d rekordów", len(records))
        for index, record in enumerate(records, start=1):
            probabilities = self.predict_proba(record)
            formatted = self._format_record(record, probabilities, threshold)
            article_count += int(formatted["is_article"])
            results.append(formatted)
            LOGGER.info(
                "Analiza lokalna %d/%d: %s (%s)",
                index,
                len(records),
                "article" if formatted["is_article"] else "junk",
                record["url"],
            )

        output = {
            "articles": [record for record in results if record["is_article"]],
            "rejected": [record for record in results if not record["is_article"]],
            "records": results,
        }
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        temporary_file = self.output_file.with_suffix(self.output_file.suffix + ".tmp")
        try:
            temporary_file.write_text(
                json.dumps(output, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary_file, self.output_file)
        finally:
            temporary_file.unlink(missing_ok=True)

        counts = {
            "processed": len(results),
            "articles": article_count,
            "junk": len(results) - article_count,
            "skipped": skipped,
        }
        LOGGER.info(
            "Analiza lokalna zakończona: %d przetworzonych, %d article, %d junk, %d pominiętych",
            counts["processed"],
            counts["articles"],
            counts["junk"],
            counts["skipped"],
        )
        return counts

    def run(self) -> dict[str, int]:
        return self.analyze_all()

    def save(self, path: str | Path | None = None) -> Path:
        if self.model is None:
            raise RuntimeError("Nie można zapisać LocalAgent przed treningiem")
        model_path = Path(path) if path else self.model_path
        if not model_path.is_absolute():
            model_path = PROJECT_DIR / model_path
        model_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = model_path.with_suffix(model_path.suffix + ".tmp")
        try:
            torch.save(
                {
                    "version": 1,
                    "hidden_size": self.hidden_size,
                    "vocabulary": self.vocabulary,
                    "state_dict": self.model.state_dict(),
                },
                temporary_path,
            )
            os.replace(temporary_path, model_path)
        finally:
            temporary_path.unlink(missing_ok=True)
        self.model_path = model_path
        return model_path

    def load(self, path: str | Path | None = None) -> None:
        model_path = Path(path) if path else self.model_path
        if not model_path.is_absolute():
            model_path = PROJECT_DIR / model_path
        checkpoint = torch.load(model_path, map_location="cpu", weights_only=True)
        if checkpoint.get("version") != 1:
            raise ValueError("Nieobsługiwany format checkpointu LocalAgent")
        self.hidden_size = int(checkpoint["hidden_size"])
        self.vocabulary = {
            str(token): int(index)
            for token, index in checkpoint["vocabulary"].items()
        }
        self.model = _TextClassifier(len(self.vocabulary), self.hidden_size)
        self.model.load_state_dict(checkpoint["state_dict"])
        self.model.eval()
        self.model_path = model_path