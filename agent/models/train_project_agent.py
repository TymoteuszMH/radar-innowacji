import argparse
import json
import random
import sys
from pathlib import Path

from dotenv import load_dotenv


PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from agents.project_agent import ProjectAgent, innovation_evidence
from models.evaluation import best_fbeta_threshold, configured_beta


def split_by_domain(records: list[dict], seed: int = 42) -> tuple[list[dict], list[dict]]:
    domains = sorted({record.get("domain") for record in records if record.get("domain")})
    if len(domains) < 2 or any(not record.get("domain") for record in records):
        raise ValueError("Walidacja wymaga co najmniej dwóch domen i domeny dla każdego rekordu")
    generator = random.Random(seed)
    for _ in range(200):
        shuffled = domains[:]
        generator.shuffle(shuffled)
        validation_domains = set(shuffled[:max(1, round(len(domains) * 0.2))])
        train = [record for record in records if record["domain"] not in validation_domains]
        validation = [record for record in records if record["domain"] in validation_domains]
        if {record["label"] for record in train} == {0, 1} and {record["label"] for record in validation} == {0, 1}:
            return train, validation
    raise ValueError("Nie udało się podzielić domen tak, aby obie części zawierały obie klasy")


def undersample_training(records: list[dict], seed: int = 42) -> list[dict]:
    if any(not isinstance(record.get("text"), str) or not record["text"].strip()
           or type(record.get("label")) is not int or record["label"] not in (0, 1)
           for record in records):
        raise ValueError("Każdy rekord treningowy musi mieć tekst i etykietę 0 lub 1")
    positive = [index for index, record in enumerate(records) if record["label"] == 1]
    negative = [index for index, record in enumerate(records) if record["label"] == 0]
    count = min(len(positive), len(negative))
    if count == 0:
        raise ValueError("Trening 50/50 wymaga pozytywnych i negatywnych przykładów")
    generator = random.Random(seed)
    selected = set(generator.sample(positive, count) + generator.sample(negative, count))
    return [record for index, record in enumerate(records) if index in selected]


def train_project(dataset_path: Path, model_path: Path, epochs: int = 50) -> None:
    beta = configured_beta()
    records = json.loads(dataset_path.read_text(encoding="utf-8"))["records"]
    train, validation = split_by_domain(records)
    train = undersample_training(train)
    agent = ProjectAgent()
    agent.fit(train, epochs=epochs)
    predictions = [agent.predict_proba(record["text"]) if innovation_evidence(record["text"]) else None
                   for record in validation]
    agent.threshold, score = best_fbeta_threshold(
        predictions, [record["label"] == 1 for record in validation], beta)
    print(f"Walidacja i dobór progu ProjectAgent: rekordy={len(validation)}, "
          f"F{beta:g}={score:.3f}, próg={agent.threshold:.6f}")
    agent.save(model_path)
    print(f"Zapisano model wytrenowany na {len(train)} rekordach "
          f"(pozytywne={len(train) // 2}, negatywne={len(train) // 2}): {model_path}")


def main() -> None:
    load_dotenv(PROJECT_DIR / ".env")
    parser = argparse.ArgumentParser(description="Trenuje niezależny model wykrywania projektów.")
    parser.add_argument("--input", type=Path, default=PROJECT_DIR / "data" / "innovation_dataset.json")
    parser.add_argument("--output", type=Path, default=PROJECT_DIR / "models" / "project_agent.pt")
    parser.add_argument("--epochs", type=int, default=50)
    args = parser.parse_args()
    train_project(args.input, args.output, args.epochs)


if __name__ == "__main__":
    main()