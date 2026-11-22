import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


PROJECT_DIR = Path(__file__).resolve().parent.parent
SYNTHETIC_TEMPLATES = (
    ("{institution} opracowała aplikację {purpose}.", "{institution} zorganizowała szkolenie z obsługi aplikacji {purpose}."),
    ("{institution} zbudowała prototyp urządzenia {purpose}.", "{institution} kupiła gotowe urządzenie {purpose}."),
    ("{institution} zaprojektowała system {purpose}.", "{institution} prowadzi warsztaty dotyczące systemów {purpose}."),
    ("{institution} stworzyła oprogramowanie {purpose}.", "{institution} szkoli pracowników z istniejącego oprogramowania {purpose}."),
    ("{institution} opracowała nową metodę {purpose}.", "{institution} przeprowadziła kurs dotyczący metod {purpose}."),
    ("{institution} skonstruowała urządzenie {purpose}.", "{institution} ogłosiła przetarg na urządzenie {purpose}."),
    ("{institution} wdrożyła własny algorytm {purpose}.", "{institution} zorganizowała konferencję o algorytmach {purpose}."),
    ("{institution} stworzyła platformę {purpose}.", "{institution} korzysta z gotowej platformy {purpose} podczas zajęć."),
    ("{institution} zaprojektowała czujnik {purpose}.", "{institution} kupiła czujniki {purpose} na potrzeby szkoły."),
    ("{institution} opracowała rozwiązanie {purpose}.", "{institution} ogłosiła projekt warsztatów {purpose}."),
    ("{institution} zbudowała robota {purpose}.", "{institution} zabrała uczniów na pokaz robotów {purpose}."),
    ("{institution} udoskonaliła technologię {purpose}.", "{institution} sfinansowała kurs obsługi technologii {purpose}."),
)
SYNTHETIC_INSTITUTIONS = ("Szkoła", "Uczelnia", "Gmina")
SYNTHETIC_PURPOSES = (
    "do monitorowania jakości powietrza", "do wspierania osób z niepełnosprawnościami",
    "do oszczędzania energii", "do wspierania edukacji", "do organizacji transportu publicznego",
)


def _url_project_text(url: str, category: str) -> str:
    path = urlsplit(url).path.strip("/")
    slug = path.rsplit("/", 1)[-1].replace(".html", "")
    words = re.sub(r"[^\w]+", " ", slug, flags=re.UNICODE).replace("_", " ").strip()
    return f"{category}. Projekt opracował rozwiązanie opisane jako {words}."


def _known_project_records() -> list[dict[str, Any]]:
    source_path = PROJECT_DIR / "data" / "sites_and_projects.csv"
    verification_path = PROJECT_DIR / "data" / "radar_innowacji_weryfikacja_i_ocena.json"
    verified_by_url = {}
    if verification_path.is_file():
        verification = json.loads(verification_path.read_text(encoding="utf-8"))
        verified_by_url = {
            str(entry["url"]).rstrip("/"): entry
            for entry in verification.get("wpisy", [])
            if isinstance(entry, dict) and entry.get("url")
        }
    if not source_path.is_file():
        return []
    records = []
    with source_path.open(encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            url = (row.get("Bezpośredni link do wpisu") or "").strip()
            category = (row.get("Kategoria i projekt") or "").strip()
            domain = (row.get("Domena") or "").strip()
            if url:
                entry = verified_by_url.get(url.rstrip("/"))
                if entry:
                    text = " ".join(filter(None, (
                        str(entry.get("nazwa_projektu") or ""),
                        str(entry.get("kategoria_wejsciowa") or ""),
                        str(entry.get("typ_podmiotu") or ""),
                        str(entry.get("typ_innowacji") or ""),
                        str(entry.get("tworcy_i_wiek") or ""),
                        str(entry.get("zgodnosc_z_wymogami_pci", {}).get("uzasadnienie") or ""),
                        " ".join(entry.get("keywords") or []),
                    )))
                else:
                    text = _url_project_text(url, category)
                records.append({
                    "domain": domain or urlsplit(url).hostname or "unknown",
                    "text": text,
                    "url": url,
                    "label": 1,
                    "label_source": "verified_direct_url",
                })
    return records


def _current_output_negatives() -> list[dict[str, Any]]:
    output_path = PROJECT_DIR / "results" / "data.json"
    if not output_path.is_file():
        return []
    data = json.loads(output_path.read_text(encoding="utf-8"))
    records = []
    for record in data.get("records", []):
        if not isinstance(record, dict):
            continue
        text = "\n".join(filter(None, (record.get("source_title", ""), record.get("content", ""))))
        if text.strip():
            records.append({
                "domain": record.get("domain", "unknown"),
                "text": text,
                "url": record.get("url", ""),
                "label": 0,
                "label_source": "verified_crawl_negative",
            })
    return records


def build_synthetic_dataset() -> dict[str, Any]:
    records = []
    for index, templates in enumerate(SYNTHETIC_TEMPLATES):
        for label, template in ((1, templates[0]), (0, templates[1])):
            for institution in SYNTHETIC_INSTITUTIONS:
                for purpose in SYNTHETIC_PURPOSES:
                    records.append({
                        "domain": f"synthetic-template-{index}.invalid",
                        "text": template.format(institution=institution, purpose=purpose),
                        "label": label,
                        "label_source": "synthetic_template",
                    })
    project_count = sum(record["label"] == 1 for record in records)
    non_project_count = sum(record["label"] == 0 for record in records)
    return {
        "description": "Syntetyczne przykłady treningowe, niezweryfikowane rzeczywiste innowacje.",
        "counts": {"project": project_count, "non_project": non_project_count},
        "records": records,
    }


def build_training_dataset() -> dict[str, Any]:
    synthetic = build_synthetic_dataset()
    records = list(synthetic["records"])
    records.extend(_known_project_records())
    records.extend(_current_output_negatives())
    project_count = sum(record["label"] == 1 for record in records)
    non_project_count = sum(record["label"] == 0 for record in records)
    return {
        "description": "Zbalansowane kombinowane dane: zweryfikowane URL-e projektów, aktualne negatywne wyniki crawl'a i syntetyczne przykłady.",
        "counts": {"project": project_count, "non_project": non_project_count},
        "records": records,
    }


def write_dataset(output_path: Path, overwrite: bool = False) -> None:
    dataset = build_training_dataset()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w" if overwrite else "x", encoding="utf-8") as output:
        output.write(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n")
    print(f"Zapisano {output_path}: {dataset['counts']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Buduje niezależny syntetyczny zbiór innowacji.")
    parser.add_argument("--output", type=Path, default=PROJECT_DIR / "data" / "innovation_dataset.json")
    parser.add_argument("--force", action="store_true", help="Nadpisz istniejący zbiór")
    args = parser.parse_args()
    write_dataset(args.output, overwrite=args.force)


if __name__ == "__main__":
    main()