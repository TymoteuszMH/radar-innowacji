import json
import os
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from dotenv import load_dotenv

from crawler.crawler_agent import CrawlerAgent
from config import env_int
from data.build_project_dataset import write_dataset
from models.evaluation import best_fbeta_threshold, split_crawler_domains
from models.train_project_agent import split_records, train_project


load_dotenv(PROJECT_DIR / ".env")


def configured_path(name: str, default: str) -> Path:
    path = Path(os.getenv(name, default))
    return path if path.is_absolute() else PROJECT_DIR / path


def main() -> None:
    project_epochs = env_int("PROJECT_AGENT_TRAIN_EPOCHS", 5, 1)
    project_dataset_path = configured_path("PROJECT_AGENT_DATASET_PATH", "data/innovation_dataset.json")
    if not project_dataset_path.is_file():
        write_dataset(project_dataset_path)
    project_records = json.loads(project_dataset_path.read_text(encoding="utf-8"))["records"]
    try:
        split_records(project_records)
    except ValueError as error:
        raise ValueError(
            f"Zbiór innowacji {project_dataset_path} nie wystarcza do treningu i walidacji. "
            "Uzupełnij ręcznie zweryfikowane przykłady obu klas."
        ) from error
    crawler_dataset_path = configured_path(
        "CRAWLER_AGENT_DATASET_PATH",
        "data/crawler_agent_data.json",
    )
    crawler_records = json.loads(crawler_dataset_path.read_text(encoding="utf-8"))["records"]

    crawler_train, crawler_validation = split_crawler_domains(crawler_records)
    crawler_agent = CrawlerAgent()
    crawler_agent.fit(
        [record["url"] for record in crawler_train],
        [record["category"] for record in crawler_train],
        epochs=int(os.getenv("CRAWLER_AGENT_TRAIN_EPOCHS", "80")),
        learning_rate=float(os.getenv("CRAWLER_AGENT_LEARNING_RATE", "0.001")),
        batch_size=int(os.getenv("CRAWLER_AGENT_BATCH_SIZE", "64")),
    )
    probabilities = [crawler_agent.predict_proba(record["url"])["article"] for record in crawler_validation]
    crawler_agent.article_threshold, score = best_fbeta_threshold(
        probabilities, [record["category"] == "article" for record in crawler_validation])
    print(f"Walidacja i dobór progu CrawlerAgent (article): rekordy={len(crawler_validation)}, "
          f"F0.5={score:.3f}, próg={crawler_agent.article_threshold:.6f}")
    crawler_model_path = configured_path(
        "CRAWLER_AGENT_MODEL_PATH",
        "models/crawler_agent.pt",
    )
    crawler_agent.save(crawler_model_path)

    print(f"CrawlerAgent checkpoint: {crawler_model_path}")
    print(f"CrawlerAgent training data: {len(crawler_train)} records from {crawler_dataset_path}")

    train_project(
        project_dataset_path,
        configured_path("PROJECT_AGENT_MODEL_PATH", "models/bert_innovation_classifier"),
        epochs=project_epochs,
    )


if __name__ == "__main__":
    main()