import math
import os
import re
from pathlib import Path
from typing import Literal, Sequence
from urllib.parse import unquote, urlsplit

import torch
from torch import nn


CrawlerCategory = Literal["sitemap", "article", "listing", "other"]
_CATEGORIES: tuple[CrawlerCategory, ...] = ("sitemap", "article", "listing", "other")
_ARTICLE_HINTS = ("artykul", "article", "post", "story")
_SECTION_HINTS = ("aktualn", "wiadom", "wydarzen", "news", "blog", "komunikat")
_HUB_HINTS = ("projekt", "project", "aktualn", "wiadom", "news", "wydarzen", "artykul", "blog")
_LISTING_HINTS = (
    "archiw",
    "category",
    "kategoria",
    "tag",
    "author",
    "search",
    "szukaj",
)
_OTHER_HINTS = (
    "logowanie",
    "kontakt",
    "polityka",
    "login",
    "privacy",
    "contact",
    "regulamin",
    "terms",
)
_ASSET_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".pdf"}
_DATE_PATTERN = re.compile(r"(?:19|20)\d{2}")
_SITEMAP_PATTERN = re.compile(r"(?:^|[/_-])sitemap(?:[_-][^/]*)?\.xml(?:\.gz)?$")


class _CrawlerNetwork(nn.Module):
    def __init__(self, input_size: int, hidden_size: int) -> None:
        super().__init__()
        self.layers = nn.Sequential(
            nn.Linear(input_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, len(_CATEGORIES)),
        )

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return self.layers(features)


class CrawlerAgent:
    def __init__(self) -> None:
        self.weights = [
            [9.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [-8.0, 2.6, 0.1, 1.2, 0.4, 0.3, 3.0, -2.0, -3.0, -3.5, -1.5],
            [-8.0, -1.5, 2.4, 0.0, 0.2, 0.0, -0.5, 2.2, -2.5, -3.0, 1.0],
            [-8.0, -1.0, -1.6, 0.0, -0.2, -0.2, -0.5, -0.4, 3.0, 5.0, -0.5],
        ]
        self.biases = [-4.0, -1.5, -0.7, 0.5]
        self.hidden_size = int(os.getenv("CRAWLER_AGENT_HIDDEN_SIZE", "32"))
        self.model: _CrawlerNetwork | None = None
        if self.hidden_size < 1:
            raise ValueError("CRAWLER_AGENT_HIDDEN_SIZE musi wynosić co najmniej 1")

    @staticmethod
    def _features(link: str) -> list[float]:
        path = unquote(urlsplit(link.strip()).path).casefold()
        segments = [segment for segment in path.split("/") if segment]
        slug = segments[-1] if segments else ""
        is_asset = Path(slug).suffix in _ASSET_EXTENSIONS

        return [
            float(bool(_SITEMAP_PATTERN.search(path))),
            float(any(hint in path for hint in _ARTICLE_HINTS)),
            float(any(hint in path for hint in _SECTION_HINTS)),
            float(bool(_DATE_PATTERN.search(path))),
            min(len(segments) / 4, 1.0),
            min(len(slug) / 80, 1.0),
            float(len(slug) > 14 and len(segments) > 1 and not is_asset),
            float(any(hint in path for hint in _LISTING_HINTS)),
            float(any(hint in path for hint in _OTHER_HINTS)),
            float(is_asset),
            float(not segments),
            float(
                len(segments) >= 3
                and len(slug) <= 16
                and not any(character.isdigit() for character in slug)
                and any(hint in path for hint in _HUB_HINTS)
            ),
            float(bool(re.match(r"^\d{3,}[-_]", slug))),
        ]

    def predict_proba(self, link: str) -> dict[CrawlerCategory, float]:
        features = self._features(link)
        if self.model is not None:
            self.model.eval()
            with torch.no_grad():
                logits = self.model(torch.tensor(features, dtype=torch.float32).unsqueeze(0))
                probabilities = torch.softmax(logits, dim=1)[0].tolist()
            return dict(zip(_CATEGORIES, probabilities))
        probabilities = self._predict_proba_from_features(features)
        return dict(zip(_CATEGORIES, probabilities))

    def _predict_proba_from_features(self, features: Sequence[float]) -> list[float]:
        scores = [
            bias + sum(weight * feature for weight, feature in zip(weights, features))
            for weights, bias in zip(self.weights, self.biases)
        ]
        max_score = max(scores)
        exponentials = [math.exp(score - max_score) for score in scores]
        total = sum(exponentials)
        return [value / total for value in exponentials]

    def classify(self, link: str) -> CrawlerCategory:
        probabilities = self.predict_proba(link)
        return max(probabilities, key=probabilities.get)

    def analyze(self, link: str) -> float:
        return self.predict_proba(link)["article"]

    def fit(
        self,
        links: Sequence[str],
        labels: Sequence[int | str | bool],
        epochs: int = 300,
        learning_rate: float = 0.005,
        batch_size: int = 64,
        seed: int = 42,
    ) -> None:
        if not links or len(links) != len(labels):
            raise ValueError("Podaj taką samą, niepustą liczbę linków i etykiet")
        if epochs < 1 or learning_rate <= 0 or batch_size < 1:
            raise ValueError("epochs, learning_rate i batch_size muszą być dodatnie")

        label_indexes = []
        for label in labels:
            if isinstance(label, bool):
                label_indexes.append(_CATEGORIES.index("article" if label else "other"))
            elif label in _CATEGORIES:
                label_indexes.append(_CATEGORIES.index(label))
            elif label == 0:
                label_indexes.append(_CATEGORIES.index("listing"))
            elif label == 1:
                label_indexes.append(_CATEGORIES.index("article"))
            elif label == 2:
                label_indexes.append(_CATEGORIES.index("sitemap"))
            elif label == 3:
                label_indexes.append(_CATEGORIES.index("other"))
            else:
                raise ValueError("Etykiety muszą być nazwą klasy lub liczbą 0, 1, 2 albo 3")

        torch.manual_seed(seed)
        features = torch.tensor([self._features(link) for link in links], dtype=torch.float32)
        targets = torch.tensor(label_indexes, dtype=torch.long)
        self.model = _CrawlerNetwork(len(self._features(links[0])), self.hidden_size)
        optimizer = torch.optim.AdamW(self.model.parameters(), lr=learning_rate)
        loss_function = nn.CrossEntropyLoss()
        for _ in range(epochs):
            self.model.train()
            order = torch.randperm(len(links))
            for start in range(0, len(links), batch_size):
                batch_indexes = order[start:start + batch_size]
                logits = self.model(features[batch_indexes])
                loss = loss_function(logits, targets[batch_indexes])
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
        self.model.eval()

    def save(self, path: str | Path) -> None:
        if self.model is None:
            raise RuntimeError("Nie można zapisać CrawlerAgent przed treningiem")
        model_path = Path(path)
        model_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = model_path.with_suffix(model_path.suffix + ".tmp")
        try:
            torch.save(
                {
                    "version": 1,
                    "categories": list(_CATEGORIES),
                    "input_size": len(self._features("https://example.test/")),
                    "hidden_size": self.hidden_size,
                    "state_dict": self.model.state_dict(),
                },
                temporary_path,
            )
            os.replace(temporary_path, model_path)
        finally:
            temporary_path.unlink(missing_ok=True)

    @classmethod
    def load(cls, path: str | Path) -> "CrawlerAgent":
        data = torch.load(path, map_location="cpu", weights_only=True)
        if (
            data.get("version") != 1
            or tuple(data.get("categories", ())) != _CATEGORIES
            or data.get("input_size") != len(cls._features("https://example.test/"))
        ):
            raise ValueError("Nieobsługiwany format modelu CrawlerAgent")
        agent = cls()
        agent.hidden_size = int(data["hidden_size"])
        agent.model = _CrawlerNetwork(data["input_size"], agent.hidden_size)
        agent.model.load_state_dict(data["state_dict"])
        agent.model.eval()
        return agent

