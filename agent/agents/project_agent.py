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
PROJECT_MENTION = re.compile(
    r"\b(?:projekt(?:u|em|owi|ie)?|inwestycj\w*|innowacyjn\w*|prototyp\w*|"
    r"wynalaz\w*|wdroż\w*|pilotaż\w*)\b", re.IGNORECASE
)


def project_from_article(article: dict[str, Any]) -> dict[str, Any]:
    title = article.get("source_title", "")
    content = article.get("content") or article.get("summary", "")
    title = title.strip() if isinstance(title, str) else ""
    content = content.strip() if isinstance(content, str) else ""
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    named_project = re.search(
        r"(?:tytuł|nazwa)\s+projektu\s*[:\-]\s*([^\n]+)|"
        r"\b(?:projekt(?:u|em|owi|ie)?|program(?:u|em|owi|ie)?)"
        r"(?:\s+[\w-]+){0,3}\s*[„\"“]([^”\"\n]+)[”\"“]",
        content, re.IGNORECASE,
    )
    project_title = next((group.strip().rstrip(". ") for group in named_project.groups() if group), "") if named_project else ""
    if not project_title:
        unquoted_name = re.search(
            r"\b[Pp]rojektu\s+([A-ZĄĆĘŁŃÓŚŹŻ][\wĄĆĘŁŃÓŚŹŻąćęłńóśźż -]{2,100})(?=[)\n.,;]|$)",
            content,
        )
        if unquoted_name:
            project_title = unquoted_name.group(1).strip()
    sentences = [sentence.strip() for line in lines for sentence in re.split(r"(?<=[.!?])\s+", line) if sentence.strip()]
    evidence = [sentence for sentence in sentences if PROJECT_MENTION.search(sentence)][:3]
    description = " ".join(evidence or sentences[:3])
    if not project_title and re.match(r"^(?:zespół szkół|szkoła|zsp\b|kujawsko-pomorski specjalny)", title, re.IGNORECASE):
        project_title = description[:160].rstrip()
    organization_match = re.search(r"(?im)^\s*(?:beneficjent|realizator)\s*:\s*([^\n]+)", content)
    creators = re.findall(
        r"(?:autor(?:ka|em|ką)?|koordynator(?:ka|em|ką)?|kierownik(?:iem)?)\s*[:\-]?\s*"
        r"([A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+(?:-[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+)?\s+"
        r"[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+(?:-[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+)?)",
        content,
    )
    return {
        "project_title": project_title or title,
        "summary": description,
        "organization": organization_match.group(1).strip() if organization_match else "",
        "people": [{"name": name} for name in dict.fromkeys(creators)],
        "evidence": evidence,
        "url": article.get("url", ""),
        "domain": article.get("domain", ""),
        "source_title": title,
    }

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
        return {"projects": [project_from_article(item)
                    for item in classified if item["project_detection"]["is_project"] is True
                    and PROJECT_MENTION.search(str(item.get("content") or item.get("summary") or ""))],
                "records": classified}


def process_file(input_file: Path, output_file: Path, data_output: Path, model_file: Path,
                 threshold: float = 0.5, agent: ProjectAgent | None = None) -> dict[str, Any]:
    paths = [input_file.resolve(), model_file.resolve(), output_file.resolve(), data_output.resolve()]
    if len(set(paths)) != len(paths):
        raise ValueError("Pliki wejściowe, modelu i oba pliki wyjściowe muszą być różne")
    source = json.loads(input_file.read_text(encoding="utf-8"))
    output = (agent or ProjectAgent.load(model_file)).classify_results(source, threshold)
    for path, data in ((data_output, {"records": output["records"]}),
                       (output_file, {"projects": output["projects"]})):
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
    print(f"Wykryto {len(output['projects'])} potencjalnych projektów w {len(output['records'])} artykułach: {output_file}; dane: {data_output}")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Wykrywa projekty w gotowych wynikach analizy.")
    parser.add_argument("--input", type=Path, default=PROJECT_DIR / "results" / "results.json")
    parser.add_argument("--output", type=Path, default=PROJECT_DIR / "results" / "projects.json")
    parser.add_argument("--data-output", type=Path, help="Plik wszystkich przeanalizowanych artykułów (domyślnie data.json obok --output)")
    parser.add_argument("--model", type=Path, default=PROJECT_DIR / "models" / "project_agent.pt")
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()
    process_file(args.input, args.output, args.data_output or args.output.with_name("data.json"),
                 args.model, args.threshold)


if __name__ == "__main__":
    main()