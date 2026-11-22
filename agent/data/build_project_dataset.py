import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from agents.project_agent import article_text


PROJECT_SIGNAL = re.compile(
    r"\b(?:projekt\w*|inwestycj\w*|prototyp\w*|wynalaz\w*|patent\w*|"
    r"pilotaż\w*|wdrożeni\w*|innowacyjn\w*)\b",
    re.IGNORECASE,
)
NON_PROJECT_SIGNAL = re.compile(
    r"\b(?:wycieczk\w*|konkurs\w*|zawod\w*|uroczystoś\w*|"
    r"wystaw\w*|rekrutacj\w*|życzeni\w*|spotkani\w*|"
    r"ogłoszeni\w*|harmonogram\w*|lekcj\w*)\b",
    re.IGNORECASE,
)


def build_dataset(source: dict[str, Any]) -> dict[str, Any]:
    articles = source.get("articles")
    if not isinstance(articles, list):
        raise ValueError("Plik źródłowy musi zawierać listę articles")
    records = []
    unlabeled = []
    seen_urls: set[str] = set()
    seen_texts: set[str] = set()
    for article in articles:
        if not isinstance(article, dict):
            continue
        url = article.get("url")
        if not isinstance(url, str) or not url.strip() or url in seen_urls:
            continue
        seen_urls.add(url)
        text = article_text(article)
        normalized_text = " ".join(text.casefold().split())
        project = PROJECT_SIGNAL.search(text)
        non_project = NON_PROJECT_SIGNAL.search(text)
        if (len(text) < 50 or normalized_text in seen_texts
            or "strona jest w trakcie tworzenia" in normalized_text
            or (project and non_project) or not (project or non_project)):
            unlabeled.append({"url": url, "text": text})
            continue
        seen_texts.add(normalized_text)
        label = int(bool(project))
        signal = project or non_project
        records.append({
            "url": url,
            "domain": article.get("domain", ""),
            "text": text,
            "label": label,
            "label_source": "bootstrap_rules",
            "label_signal": signal.group(0),
        })
    counts = Counter(record["label"] for record in records)
    return {
        "description": "Etykiety heurystyczne wymagają ręcznej weryfikacji; 1 oznacza potencjalny projekt.",
        "counts": {"project": counts[1], "non_project": counts[0], "unlabeled": len(unlabeled)},
        "records": records,
        "unlabeled": unlabeled,
    }


def write_dataset(input_path: Path, output_path: Path, overwrite: bool = True) -> None:
    if input_path.resolve() == output_path.resolve():
        raise ValueError("Plik wyjściowy musi być inny niż wejściowy")
    source = json.loads(input_path.read_text(encoding="utf-8"))
    dataset = build_dataset(source)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w" if overwrite else "x", encoding="utf-8") as output:
        output.write(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n")
    print(f"Zapisano {output_path}: {dataset['counts']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Buduje słabo etykietowany zbiór projektów z wyników analizy.")
    parser.add_argument("--input", type=Path, default=PROJECT_DIR / "results" / "results.json")
    parser.add_argument("--output", type=Path, default=PROJECT_DIR / "data" / "project_dataset.json")
    args = parser.parse_args()
    write_dataset(args.input, args.output)


if __name__ == "__main__":
    main()