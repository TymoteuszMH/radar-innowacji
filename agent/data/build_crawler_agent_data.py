import argparse
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit


PROJECT_DIR = Path(__file__).resolve().parent.parent
CATEGORIES = ("article", "listing", "sitemap", "other")
TARGET_PER_CATEGORY = 1250

LOG_PATTERNS = {
    "article": re.compile(r"Odwiedzam \[article\]: (https?://\S+)"),
    "listing": re.compile(r"Odwiedzam \[listing\]: (https?://\S+)"),
    "sitemap": re.compile(r"Odwiedzam \[sitemap\]: (https?://\S+)"),
    "other": re.compile(r"Pominięto bez pobierania \[other\]: (https?://\S+)"),
}
SYNTHETIC_PATHS = {
    "article": (
        "/aktualnosci/{slug}-{index}",
        "/wiadomosci/{slug}-{index}",
        "/artykuly/{slug}-{index}",
        "/2026/04/{slug}-{index}",
        "/index.php/szkola/projekty/{slug}/{index}-{slug}",
        "/index.php/aktualnosci/{index}-{slug}",
    ),
    "listing": (
        "/",
        "/aktualnosci",
        "/category/{slug}",
        "/tag/{slug}",
        "/archiwum/{year}",
        "/index.php/szkola/projekty/{slug}",
        "/index.php/aktualnosci/{slug}",
        "/szkola/wydarzenia/{slug}",
    ),
    "sitemap": (
        "/sitemap.xml",
        "/sitemap_index.xml",
        "/wp-sitemap.xml",
        "/news-sitemap.xml",
    ),
    "other": (
        "/kontakt",
        "/logowanie",
        "/polityka-prywatnosci",
        "/regulamin",
        "/media/dokument-{index}.pdf",
        "/images/logo-{index}.png",
    ),
}
SLUGS = (
    "projekt-badawczy",
    "innowacje-w-edukacji",
    "wyniki-konkursu",
    "nowe-laboratorium",
    "wspolpraca-uczniow",
    "bezpieczenstwo-w-szkole",
    "program-rozwoju",
    "badanie-srodowiska",
    "cyfrowa-pracownia",
    "spotkanie-informacyjne",
)


def _clean_url(url: str) -> str:
    return url.rstrip(",.;")


def _add_real_record(
    records: dict[str, dict[str, str | bool]],
    url: str,
    category: str,
    source: str,
) -> None:
    url = _clean_url(url)
    if category not in CATEGORIES or not urlsplit(url).hostname:
        return
    current = records.get(url)
    if current is None or source in {"scrapped_json", "curated_training_data"}:
        records[url] = {
            "url": url,
            "domain": urlsplit(url).hostname or "",
            "category": category,
            "source": source,
            "is_synthetic": False,
        }


def _load_real_records() -> tuple[list[dict[str, str | bool]], int]:
    labels: dict[str, Counter[str]] = defaultdict(Counter)
    logs_path = PROJECT_DIR / "logs" / "logs.txt"
    if logs_path.is_file():
        for line in logs_path.read_text(encoding="utf-8", errors="replace").splitlines():
            for category, pattern in LOG_PATTERNS.items():
                match = pattern.search(line)
                if match:
                    labels[_clean_url(match.group(1))][category] += 1

    records: dict[str, dict[str, str | bool]] = {}
    conflict_count = 0
    for url, counts in labels.items():
        if len(counts) != 1:
            conflict_count += 1
            continue
        category = counts.most_common(1)[0][0]
        _add_real_record(records, url, category, "crawler_log_pseudo_label")

    scrapped_dir = PROJECT_DIR / "data" / "scrapped"
    for path in scrapped_dir.glob("*.json") if scrapped_dir.is_dir() else ():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        domain = data.get("domain", path.stem) if isinstance(data, dict) else path.stem
        articles = data.get("articles", []) if isinstance(data, dict) else []
        for article in articles:
            if isinstance(article, dict) and isinstance(article.get("url"), str):
                _add_real_record(records, article["url"], "article", "scrapped_json")

    mock_path = PROJECT_DIR / "data" / "article_mock.json"
    if mock_path.is_file():
        try:
            mock_records = json.loads(mock_path.read_text(encoding="utf-8")).get("articles", [])
        except (OSError, json.JSONDecodeError):
            mock_records = []
        for record in mock_records:
            if not isinstance(record, dict) or record.get("source") != "real_curated_4lo":
                continue
            category = record.get("crawler_category")
            url = record.get("url")
            if category in CATEGORIES and isinstance(url, str):
                _add_real_record(records, url, category, "curated_training_data")
    return list(records.values()), conflict_count


def _make_synthetic_records(category: str, count: int, offset: int) -> list[dict[str, str | bool]]:
    records = []
    paths = SYNTHETIC_PATHS[category]
    for index in range(offset, offset + count):
        slug = SLUGS[index % len(SLUGS)]
        path_template = paths[index % len(paths)]
        path = path_template.format(slug=slug, index=index + 1, year=2020 + index % 7)
        domain = f"mock-{category}-{index + 1:05d}.example"
        records.append({
            "url": f"https://{domain}{path}",
            "domain": domain,
            "category": category,
            "source": "synthetic_template",
            "is_synthetic": True,
        })
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=PROJECT_DIR / "data" / "crawler_agent_data.json")
    output_path = parser.parse_args().output
    real_records, conflict_count = _load_real_records()
    real_by_category: dict[str, list[dict[str, str | bool]]] = {
        category: [record for record in real_records if record["category"] == category]
        for category in CATEGORIES
    }
    sampler = random.Random(20261121)

    output_records: list[dict[str, str | bool]] = []
    synthetic_counts: dict[str, int] = {}
    selected_real_count = 0
    for category in CATEGORIES:
        category_records = sorted(real_by_category[category], key=lambda record: str(record["url"]))
        if len(category_records) > TARGET_PER_CATEGORY:
            curated = [record for record in category_records if record["source"] == "curated_training_data"]
            if len(curated) > TARGET_PER_CATEGORY:
                raise ValueError(f"Za dużo ręcznie oznaczonych rekordów w klasie {category}")
            remaining = [record for record in category_records if record["source"] != "curated_training_data"]
            category_records = sorted(
                curated + sampler.sample(remaining, TARGET_PER_CATEGORY - len(curated)),
                key=lambda record: str(record["url"]),
            )
        selected_real_count += len(category_records)
        synthetic_count = TARGET_PER_CATEGORY - len(category_records)
        synthetic_counts[category] = synthetic_count
        output_records.extend(category_records)
        output_records.extend(_make_synthetic_records(category, synthetic_count, 0))

    random.Random(20261121).shuffle(output_records)
    counts = Counter(str(record["category"]) for record in output_records)
    dataset = {
        "description": (
            "Zbiór URL-i do treningu CrawlerAgent. 5000 rekordów, równo po 1250 na klasę. "
            "Realne adresy są oznaczone source=crawler_log_pseudo_label, scrapped_json albo curated_training_data; "
            "syntetyczne mają source=synthetic_template "
            "i domenę .example. Etykiety logowe są pseudo-etykietami, nie ręczną weryfikacją."
        ),
        "categories": list(CATEGORIES),
        "counts": dict(counts),
        "real_records": selected_real_count,
        "synthetic_records": len(output_records) - selected_real_count,
        "conflicting_log_urls_excluded": conflict_count,
        "synthetic_counts_by_category": synthetic_counts,
        "records": output_records,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(".json.tmp")
    try:
        temporary_path.write_text(
            json.dumps(dataset, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary_path.replace(output_path)
    finally:
        temporary_path.unlink(missing_ok=True)

    check = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(check["records"]) == 5000
    assert len({record["url"] for record in check["records"]}) == 5000
    assert all(check["counts"][category] == TARGET_PER_CATEGORY for category in CATEGORIES)
    print(
        f"Created {output_path.name}: {selected_real_count} real, "
        f"{dataset['synthetic_records']} synthetic, {conflict_count} conflicting URLs excluded"
    )
    print("Class counts:", dict(counts))


if __name__ == "__main__":
    main()