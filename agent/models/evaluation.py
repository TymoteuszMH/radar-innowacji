import math
import random
from typing import Any
from urllib.parse import urlsplit


def split_crawler_domains(records: list[dict[str, Any]], seed: int = 42) -> tuple[list[dict], list[dict]]:
    categories = {"article", "listing", "sitemap", "other"}
    groups: dict[str, list[dict]] = {}
    for record in records:
        domain = urlsplit(record["url"]).hostname
        if not domain or record["category"] not in categories:
            raise ValueError("Każdy rekord crawlera musi mieć poprawny URL i kategorię")
        groups.setdefault(domain.casefold(), []).append(record)
    domains = sorted(groups)
    generator = random.Random(seed)
    for _ in range(200):
        shuffled = domains[:]
        generator.shuffle(shuffled)
        held_out = set(shuffled[:max(1, round(len(domains) * 0.2))])
        train = [record for domain, group in groups.items() if domain not in held_out for record in group]
        validation = [record for domain, group in groups.items() if domain in held_out for record in group]
        if ({record["category"] for record in train} == categories
                and {record["category"] for record in validation} == categories):
            return train, validation
    raise ValueError("Walidacja crawlera wymaga wszystkich kategorii w obu rozłącznych grupach domen")


def best_fbeta_threshold(probabilities: list[float | None], labels: list[bool],
                         beta: float = 0.5) -> tuple[float, float]:
    if not probabilities or len(probabilities) != len(labels):
        raise ValueError("Podaj równą, niepustą liczbę prawdopodobieństw i etykiet")
    if any(value is not None and (not math.isfinite(value) or not 0 <= value <= 1)
           for value in probabilities):
        raise ValueError("Prawdopodobieństwa muszą należeć do przedziału 0–1")
    candidates = {0.0, 1.0, *(value for value in probabilities if value is not None)}
    best_threshold, best_score = 1.0, -1.0
    for threshold in sorted(candidates, reverse=True):
        true_positive = sum(value is not None and value >= threshold and label
                            for value, label in zip(probabilities, labels))
        predicted_positive = sum(value is not None and value >= threshold for value in probabilities)
        actual_positive = sum(labels)
        denominator = beta ** 2 * actual_positive + predicted_positive
        score = (1 + beta ** 2) * true_positive / denominator if denominator else 0.0
        if score > best_score:
            best_threshold, best_score = threshold, score
    return best_threshold, best_score
