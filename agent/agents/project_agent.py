import argparse
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

import torch
from torch import nn


PROJECT_DIR = Path(__file__).resolve().parent.parent

def article_text(record: dict[str, Any]) -> str:
    parts = []
    fields = ("source_title", "content") if "content" in record else ("source_title", "summary", "facts", "evidence")
    for field in fields:
        value = record.get(field, "")
        values = value if isinstance(value, list) else [value]
        for item in values:
            if isinstance(item, str) and item.strip() and item.strip() not in parts:
                parts.append(item.strip())
    return "\n".join(parts)


def tokens(text: str) -> list[str]:
    return re.findall(r"[^\W_]+", text.casefold(), re.UNICODE)


class _ProjectClassifier(nn.Module):
    def __init__(self, input_size: int, hidden_size: int) -> None:
        super().__init__()
        self.layers = nn.Sequential(
            nn.Linear(input_size, hidden_size), nn.ReLU(), nn.Dropout(0.15), nn.Linear(hidden_size, 2)
        )

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return self.layers(inputs)


class ProjectAgent:
    def __init__(self, hidden_size: int = 64) -> None:
        if hidden_size < 1:
            raise ValueError("hidden_size musi być dodatni")
        self.hidden_size = hidden_size
        self.vocabulary: dict[str, int] = {}
        self.model: _ProjectClassifier | None = None

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
        self.model = _ProjectClassifier(len(self.vocabulary), self.hidden_size)
        weights = torch.tensor([len(records) / (2 * counts[label]) for label in (0, 1)])
        loss_function = nn.CrossEntropyLoss(weight=weights)
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
        agent.vocabulary = checkpoint["vocabulary"]
        agent.model = _ProjectClassifier(len(agent.vocabulary), agent.hidden_size)
        agent.model.load_state_dict(checkpoint["state_dict"])
        agent.model.eval()
        return agent

    def classify_results(self, source: dict[str, Any], threshold: float = 0.5) -> dict[str, Any]:
        if not 0 <= threshold <= 1:
            raise ValueError("Próg musi być między 0 i 1")
        articles = source.get("articles")
        if not isinstance(articles, list) or any(not isinstance(article, dict) for article in articles):
            raise ValueError("Plik źródłowy musi zawierać listę artykułów")
        classified = []
        for article in articles:
            text = article_text(article)
            probability = self.predict_proba(text)
            classified.append({**article, "analyzed_text": text, "project_detection": {
                "is_project": None if probability is None else probability >= threshold,
                "probability": probability,
            }})
        return {"projects": [
                    {"domain": item.get("domain", ""), "url": item.get("url", ""),
                     "source_title": item.get("source_title", "")}
                    for item in classified if item["project_detection"]["is_project"] is True
                ],
                "records": classified}


def main() -> None:
    parser = argparse.ArgumentParser(description="Wykrywa projekty w gotowych wynikach analizy.")
    parser.add_argument("--input", type=Path, default=PROJECT_DIR / "results" / "results.json")
    parser.add_argument("--output", type=Path, default=PROJECT_DIR / "results" / "projects.json")
    parser.add_argument("--data-output", type=Path, help="Plik wszystkich przeanalizowanych artykułów (domyślnie data.json obok --output)")
    parser.add_argument("--model", type=Path, default=PROJECT_DIR / "models" / "project_agent.pt")
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()
    data_output = args.data_output or args.output.with_name("data.json")
    paths = [args.input.resolve(), args.model.resolve(), args.output.resolve(), data_output.resolve()]
    if len(set(paths)) != len(paths):
        raise ValueError("Pliki wejściowe, modelu i oba pliki wyjściowe muszą być różne")
    source = json.loads(args.input.read_text(encoding="utf-8"))
    output = ProjectAgent.load(args.model).classify_results(source, args.threshold)
    for path, data in ((data_output, {"records": output["records"]}),
                       (args.output, {"projects": output["projects"]})):
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
    print(f"Wykryto {len(output['projects'])} potencjalnych projektów w {len(output['records'])} artykułach: {args.output}; dane: {data_output}")


if __name__ == "__main__":
    main()