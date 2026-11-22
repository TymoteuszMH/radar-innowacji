import json
import os
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from dotenv import load_dotenv

from agents.local_agent import LocalAgent
from crawler.crawler_agent import CrawlerAgent


load_dotenv(PROJECT_DIR / ".env")


def configured_path(name: str, default: str) -> Path:
    path = Path(os.getenv(name, default))
    return path if path.is_absolute() else PROJECT_DIR / path


def main() -> None:
    crawler_dataset_path = configured_path(
        "CRAWLER_AGENT_DATASET_PATH",
        "data/crawler_agent_data.json",
    )
    crawler_records = json.loads(crawler_dataset_path.read_text(encoding="utf-8"))["records"]

    crawler_agent = CrawlerAgent()
    crawler_agent.fit(
        [record["url"] for record in crawler_records],
        [record["category"] for record in crawler_records],
        epochs=int(os.getenv("CRAWLER_AGENT_TRAIN_EPOCHS", "80")),
        learning_rate=float(os.getenv("CRAWLER_AGENT_LEARNING_RATE", "0.001")),
        batch_size=int(os.getenv("CRAWLER_AGENT_BATCH_SIZE", "64")),
    )
    crawler_model_path = configured_path(
        "CRAWLER_AGENT_MODEL_PATH",
        "models/crawler_agent.pt",
    )
    crawler_agent.save(crawler_model_path)

    dataset_path = configured_path("LOCAL_AGENT_DATASET_PATH", "data/dataset_clean.json")
    records = json.loads(dataset_path.read_text(encoding="utf-8"))["records"]
    local_agent = LocalAgent(load_existing=False)
    metrics = local_agent.fit(records)
    local_model_path = configured_path(
        "LOCAL_AGENT_MODEL_PATH",
        "models/local_agent.pt",
    )
    local_agent.save(local_model_path)

    print(f"CrawlerAgent checkpoint: {crawler_model_path}")
    print(f"CrawlerAgent training data: {len(crawler_records)} records from {crawler_dataset_path}")
    print(f"LocalAgent checkpoint: {local_model_path}")
    print(
        "LocalAgent walidacja: "
        f"accuracy={metrics['validation_accuracy']:.3f}, "
        f"loss={metrics['validation_loss']:.4f}"
    )


if __name__ == "__main__":
    main()