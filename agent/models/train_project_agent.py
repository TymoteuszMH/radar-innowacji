import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import torch
from datasets import Dataset
from sklearn.metrics import f1_score
from sklearn.model_selection import train_test_split
from sklearn.utils.class_weight import compute_class_weight
from dotenv import load_dotenv
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    Trainer,
    TrainingArguments,
    set_seed,
)

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from agents.project_agent import ProjectAgent, article_text, tokenize_text
from config import env_float, env_int

BASE_MODEL = "sdadas/polish-distilroberta"


def split_records(records: list[dict[str, Any]], seed: int | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not isinstance(records, list) or any(
        not isinstance(record, dict)
        or type(record.get("label")) is not int
        or record["label"] not in (0, 1)
        or not isinstance(record.get("text", article_text(record)), str)
        or not record.get("text", article_text(record)).strip()
        for record in records
    ):
        raise ValueError("Każdy rekord musi mieć tekst i etykietę 0 lub 1")
    labels = [record["label"] for record in records]
    if labels.count(0) < 2 or labels.count(1) < 2:
        raise ValueError("Zbiór treningowy musi zawierać co najmniej dwa przykłady każdej klasy")
    if seed is None:
        seed = env_int("PROJECT_AGENT_SEED", 42, 0, 2**32 - 1)
    validation_fraction = env_float("PROJECT_AGENT_VALIDATION_FRACTION", 0.2, 0, 1)
    if not 0 < validation_fraction < 1:
        raise ValueError("PROJECT_AGENT_VALIDATION_FRACTION musi być większe od 0 i mniejsze od 1")
    train, validation = train_test_split(records, test_size=validation_fraction, random_state=seed, stratify=labels)
    return train, validation


class WeightedTrainer(Trainer):
    def __init__(self, *args: Any, class_weights: torch.Tensor, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.class_weights = class_weights

    def compute_loss(self, model: Any, inputs: dict[str, torch.Tensor],
                     return_outputs: bool = False, num_items_in_batch: Any = None) -> Any:
        inputs = dict(inputs)
        labels = inputs.pop("labels")
        outputs = model(**inputs)
        loss = torch.nn.CrossEntropyLoss(weight=self.class_weights.to(outputs.logits.device))(
            outputs.logits, labels
        )
        return (loss, outputs) if return_outputs else loss


def fit_agent(agent: ProjectAgent, records: list[dict[str, Any]], epochs: int | None = None,
              seed: int | None = None) -> None:
    load_dotenv(PROJECT_DIR / ".env")
    if epochs is None:
        epochs = env_int("PROJECT_AGENT_TRAIN_EPOCHS", 5, 1)
    if seed is None:
        seed = env_int("PROJECT_AGENT_SEED", 42, 0, 2**32 - 1)
    if epochs < 1:
        raise ValueError("epochs musi być dodatnie")
    train_batch_size = env_int("PROJECT_AGENT_TRAIN_BATCH_SIZE", 8, 1)
    eval_batch_size = env_int("PROJECT_AGENT_EVAL_BATCH_SIZE", 8, 1)
    learning_rate = env_float("PROJECT_AGENT_LEARNING_RATE", 3e-5, 0)
    if learning_rate == 0:
        raise ValueError("PROJECT_AGENT_LEARNING_RATE musi być dodatnie")
    warmup_ratio = env_float("PROJECT_AGENT_WARMUP_RATIO", 0.1, 0, 1)
    weight_decay = env_float("PROJECT_AGENT_WEIGHT_DECAY", 0.01, 0)
    train, validation = split_records(records, seed)
    train_labels = [record["label"] for record in train]
    weights = compute_class_weight("balanced", classes=np.array([0, 1]), y=np.array(train_labels))
    set_seed(seed)
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(BASE_MODEL, num_labels=2)

    def dataset(items: list[dict[str, Any]]) -> Dataset:
        texts = [item["text"] if "text" in item else article_text(item) for item in items]
        data = Dataset.from_dict({"text": texts, "labels": [item["label"] for item in items]})
        return data.map(lambda row: tokenize_text(tokenizer, row["text"]), remove_columns=["text"])

    train_data, validation_data = dataset(train), dataset(validation)

    def metrics(prediction: Any) -> dict[str, float]:
        return {"f1": f1_score(prediction.label_ids, np.argmax(prediction.predictions, axis=-1), zero_division=0)}

    with tempfile.TemporaryDirectory(prefix="project-bert-training-") as directory:
        args = TrainingArguments(
            output_dir=directory,
            num_train_epochs=epochs,
            per_device_train_batch_size=train_batch_size,
            per_device_eval_batch_size=eval_batch_size,
            learning_rate=learning_rate,
            warmup_ratio=warmup_ratio,
            weight_decay=weight_decay,
            eval_strategy="epoch",
            save_strategy="epoch",
            save_total_limit=1,
            load_best_model_at_end=True,
            metric_for_best_model="f1",
            greater_is_better=True,
            report_to="none",
            seed=seed,
        )
        trainer = WeightedTrainer(
            model=model,
            args=args,
            train_dataset=train_data,
            eval_dataset=validation_data,
            data_collator=DataCollatorWithPadding(tokenizer),
            compute_metrics=metrics,
            class_weights=torch.tensor(weights, dtype=torch.float32),
        )
        trainer.train()
        agent.model = trainer.model.to(agent.device)
        agent.model.eval()
        agent.tokenizer = tokenizer
        print(f"Walidacja F1 klasy 1: {trainer.state.best_metric:.3f}; "
              f"trening={len(train)}, walidacja={len(validation)}, wagi={weights.tolist()}")


def train_project(dataset_path: Path, model_path: Path, epochs: int | None = None) -> None:
    records = json.loads(dataset_path.read_text(encoding="utf-8"))["records"]
    agent = ProjectAgent()
    agent.fit(records, epochs=epochs)
    agent.save(model_path)
    print(f"Zapisano model i tokenizer: {model_path}")


def main() -> None:
    load_dotenv(PROJECT_DIR / ".env")
    parser = argparse.ArgumentParser(description="Trenuje model wykrywania projektów.")
    parser.add_argument("--input", type=Path, default=PROJECT_DIR / os.getenv(
        "PROJECT_AGENT_DATASET_PATH", "data/innovation_dataset.json"))
    parser.add_argument("--output", type=Path, default=PROJECT_DIR / os.getenv(
        "PROJECT_AGENT_MODEL_PATH", "models/bert_innovation_classifier"))
    parser.add_argument("--epochs", type=int)
    args = parser.parse_args()
    train_project(args.input, args.output, args.epochs)


if __name__ == "__main__":
    main()
