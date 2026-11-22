import csv
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

from logging_utils import get_logger


PROJECT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_DIR / ".env")
LOGGER = get_logger("raw_data_formatter")
csv.field_size_limit(2**31 - 1)


def _is_recent_article(published_at: str, now: datetime, max_age: timedelta) -> bool:
    try:
        parsed = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    parsed = parsed.astimezone(timezone.utc)
    return now - max_age <= parsed <= now


class RawDataFormatter:
    """Format crawler records as articles without classifying their contents."""

    def __init__(
        self,
        input_dir: str | Path | None = None,
        output_file: str | Path | None = None,
    ) -> None:
        input_path = Path(input_dir or os.getenv("SCRAPPED_DIR", "data/scrapped"))
        output_path = Path(output_file or os.getenv("ANALYSIS_OUTPUT_FILE", "results/results.json"))
        self.input_dir = input_path if input_path.is_absolute() else PROJECT_DIR / input_path
        self.output_file = output_path if output_path.is_absolute() else PROJECT_DIR / output_path

    def _load_records(self) -> list[dict[str, str]]:
        if not self.input_dir.is_dir():
            LOGGER.warning("Nie znaleziono folderu z danymi: %s", self.input_dir)
            return []

        records: list[dict[str, str]] = []
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
                    records.append({
                        key: (value.strip() if isinstance(value, str) else "")
                        for key, value in {
                            "domain": values.get("domain", default_domain),
                            "url": values.get("url", ""),
                            "source_title": values.get("title", ""),
                            "content": values.get("content", ""),
                            "published_at": values.get("published_at", ""),
                        }.items()
                    })
            except (OSError, csv.Error, json.JSONDecodeError, TypeError) as error:
                LOGGER.error("Nie udało się odczytać %s: %s", path, error)
                raise
        return records

    def analyze_all(self) -> dict[str, int]:
        loaded_records = self._load_records()
        now = datetime.now(timezone.utc)
        max_age = timedelta(days=int(os.getenv("ARTICLE_MAX_AGE_DAYS", "7")))
        records = [
            record for record in loaded_records
            if _is_recent_article(record["published_at"], now, max_age)
        ]
        max_records = int(os.getenv("MAX_ARTICLES_TO_PROCESS", "0"))
        skipped = len(loaded_records) - len(records)
        if max_records:
            skipped += max(0, len(records) - max_records)
            records = records[:max_records]

        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        temporary_file = self.output_file.with_suffix(self.output_file.suffix + ".tmp")
        try:
            temporary_file.write_text(
                json.dumps({"articles": records}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary_file, self.output_file)
        finally:
            temporary_file.unlink(missing_ok=True)

        counts = {"processed": len(records), "articles": len(records), "skipped": skipped}
        LOGGER.info("Sformatowano %d artykułów, pominięto %d", counts["articles"], skipped)
        return counts

    def run(self) -> dict[str, int]:
        return self.analyze_all()