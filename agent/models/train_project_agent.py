import argparse
import json
import random
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from agents.project_agent import ProjectAgent


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


def train_project(dataset_path: Path, model_path: Path, epochs: int = 50) -> None:
    records = json.loads(dataset_path.read_text(encoding="utf-8"))["records"]
    train, validation = split_by_domain(records)
    agent = ProjectAgent()
    agent.fit(train, epochs=epochs)
    predictions = [agent.predict_proba(record["text"]) for record in validation]
    true_positive = sum(probability is not None and probability >= 0.5 and record["label"] == 1
                        for probability, record in zip(predictions, validation))
    predicted_positive = sum(probability is not None and probability >= 0.5 for probability in predictions)
    actual_positive = sum(record["label"] == 1 for record in validation)
    print(f"Walidacja na etykietach bootstrapowych: rekordy={len(validation)}, "
          f"precision={true_positive / predicted_positive if predicted_positive else 0:.3f}, "
          f"recall={true_positive / actual_positive:.3f}")
    agent.fit(records, epochs=epochs)
    agent.save(model_path)
    print(f"Zapisano model wytrenowany na {len(records)} rekordach: {model_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Trenuje niezależny model wykrywania projektów.")
    parser.add_argument("--input", type=Path, default=PROJECT_DIR / "data" / "project_dataset.json")
    parser.add_argument("--output", type=Path, default=PROJECT_DIR / "models" / "project_agent.pt")
    parser.add_argument("--epochs", type=int, default=50)
    args = parser.parse_args()
    train_project(args.input, args.output, args.epochs)


if __name__ == "__main__":
    main()