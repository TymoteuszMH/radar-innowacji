import argparse
import csv
import json
import random
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


PROJECT_DIR = Path(__file__).resolve().parent.parent
REFERENCE_POSITIVE_COUNT = 12
HARD_NEGATIVE_PER_CATEGORY = 5
DATASET_SEED = 42
REFERENCE_ACTIONS = ("opracowali", "zaprojektowali", "stworzyli", "zbudowali")

GENERATED_POSITIVE_ARTICLES = (
    ("szkola", "Uczniowie opracowali prototyp czujnika jakości wody",
     "Zespół uczniów z pracowni biologicznej opracował prototyp czujnika jakości wody dla małych zbiorników. Urządzenie wykorzystuje wymienne paski pomiarowe i zapisuje wyniki w aplikacji przygotowanej przez uczniów. Pierwsze testy wykonano na próbkach z lokalnego jeziora.",
     "generated-positive-school-01.invalid"),
    ("uczelnia", "Badacze zaprojektowali algorytm prognozowania zużycia energii",
     "Zespół z wydziału elektrotechniki zaprojektował algorytm prognozowania zużycia energii w budynkach publicznych. Model opracowano na podstawie pomiarów z kampusu, a jego prototyp połączono z istniejącymi licznikami. Uczelnia planuje pilotaż w dwóch budynkach.",
     "generated-positive-university-01.invalid"),
    ("jst", "Gmina opracowała nową procedurę szybkiego wykrywania wycieków",
     "Pracownicy miejskich wodociągów opracowali nową procedurę wykrywania wycieków w sieci wodociągowej. Łączy ona odczyty czujników ciśnienia z mapą zgłoszeń mieszkańców i pozwala kierować ekipy do najbardziej prawdopodobnych awarii. Rozwiązanie przetestowano w jednej dzielnicy.",
     "generated-positive-municipality-01.invalid"),
    ("instytucja_publiczna", "Instytut zbudował stanowisko do odzysku włókien kompozytowych",
     "Zespół instytutu badawczego zbudował prototyp stanowiska do odzysku włókien z zużytych elementów kompozytowych. Opracowany proces rozdziela warstwy materiału bez ich mechanicznego rozdrabniania. Badacze sprawdzili jakość odzyskanych włókien w serii prób laboratoryjnych.",
     "generated-positive-public-lab-01.invalid"),
    ("szkola", "Młodzi konstruktorzy stworzyli aplikację wspierającą osoby słabowidzące",
     "Uczniowski zespół informatyczny stworzył aplikację, która odczytuje etykiety produktów i powiększa tekst na ekranie telefonu. Prototyp opracowano po konsultacjach z lokalnym kołem osób niewidomych. Szkoła przygotowuje testy użyteczności z udziałem przyszłych użytkowników.",
     "generated-positive-school-02.invalid"),
    ("uczelnia", "Studentki skonstruowały czujnik do monitorowania gleby w szklarni",
     "Studentki kierunku automatyka skonstruowały moduł monitorujący wilgotność i temperaturę gleby w szklarni. Własny układ pomiarowy przekazuje dane do panelu przygotowanego przez zespół i uruchamia alarm po przekroczeniu ustalonych progów. Prototyp sprawdzono podczas semestralnych upraw.",
     "generated-positive-university-02.invalid"),
    ("jst", "Miasto wdrożyło własny model priorytetyzacji napraw chodników",
     "Zespół miejskiego laboratorium danych opracował model priorytetyzacji napraw chodników, wykorzystujący zgłoszenia mieszkańców i wyniki audytów dostępności. Miasto wdrożyło rozwiązanie pilotażowo w trzech dzielnicach i porównuje czas realizacji napraw z poprzednim rokiem.",
     "generated-positive-municipality-02.invalid"),
    ("instytucja_publiczna", "Opracowano metodę ponownego użycia wody w laboratorium",
     "Badacze publicznego instytutu opracowali metodę ponownego użycia wody procesowej po filtracji membranowej. Zespół zbudował stanowisko testowe i wykazał, że odzyskana woda może być wykorzystana w wybranych etapach mycia aparatury. Kolejny etap obejmuje dłuższe testy eksploatacyjne.",
     "generated-positive-public-lab-02.invalid"),
)

UNRELATED_ARTICLES = (
    ("szkola", "Szkolna drużyna wygrała turniej siatkówki", "Drużyna liceum zwyciężyła w powiatowym turnieju siatkówki. Finałowe spotkanie zakończyło się wynikiem 2:1, a nagrody wręczył starosta.", "unrelated-school-01.invalid"),
    ("szkola", "Zebranie rodziców odbędzie się w przyszłym tygodniu", "Dyrekcja szkoły zaprasza rodziców na zebrania klasowe. Harmonogram spotkań i numery sal opublikowano w dzienniku elektronicznym.", "unrelated-school-02.invalid"),
    ("uczelnia", "Rekrutacja na semestr letni potrwa do końca stycznia", "Uczelnia przypomina kandydatom o terminach rekrutacji. Wnioski należy złożyć przez system internetowy wraz z wymaganymi dokumentami.", "unrelated-university-01.invalid"),
    ("uczelnia", "Biblioteka zmienia godziny pracy w okresie świątecznym", "W okresie świątecznym biblioteka główna będzie czynna krócej. Czytelnicy mogą sprawdzić aktualny grafik na stronie uczelni.", "unrelated-university-02.invalid"),
    ("jst", "Utrudnienia w ruchu podczas sobotniego biegu ulicznego", "W związku z organizacją biegu miejskiego część ulic zostanie czasowo zamknięta. Autobusy pojadą objazdami, a szczegółowa mapa trasy jest dostępna na stronie miasta.", "unrelated-municipality-01.invalid"),
    ("jst", "Urząd przypomina o terminie płatności podatku od nieruchomości", "Mieszkańcy mogą opłacić podatek przelewem lub w kasie urzędu. Indywidualne numery rachunków znajdują się w decyzjach podatkowych.", "unrelated-municipality-02.invalid"),
    ("instytucja_publiczna", "Instytut ogłasza nabór na stanowisko księgowe", "Publiczny instytut poszukuje pracownika do obsługi finansowej projektów. Wymagane dokumenty aplikacyjne należy przesłać do piątku.", "unrelated-institution-01.invalid"),
    ("instytucja_publiczna", "Komunikat o zmianie godzin obsługi interesantów", "W najbliższy poniedziałek punkt obsługi interesantów będzie czynny od godziny 10.00. Sprawy pilne można zgłaszać telefonicznie.", "unrelated-institution-02.invalid"),
)

JUNK_PAGES = (
    ("Strona nie została znaleziona", "404 Not Found. Żądany adres nie istnieje. Wróć do strony głównej.", "junk-page-01.invalid"),
    ("Włącz obsługę JavaScript", "Aby wyświetlić tę stronę, włącz JavaScript i odśwież przeglądarkę.", "junk-page-02.invalid"),
    ("Weryfikacja przeglądarki", "Checking your browser before accessing this website. Please wait while we verify your connection.", "junk-page-03.invalid"),
    ("Polityka prywatności i pliki cookie", "Strona używa plików cookie. Administrator przetwarza dane zgodnie z polityką prywatności. Ustawienia zgód można zmienić w dowolnym momencie.", "junk-page-04.invalid"),
    ("Wyniki wyszukiwania", "Nie znaleziono wyników. Spróbuj użyć innych słów. Strona główna | Kontakt | Regulamin | Polityka prywatności.", "junk-page-05.invalid"),
    ("Błąd serwera", "500 Internal Server Error. The server encountered an unexpected condition and could not complete the request.", "junk-page-06.invalid"),
    ("Menu serwisu", "Aktualności Archiwum O stronie Kontakt Deklaracja dostępności RSS Zaloguj się. Brak treści artykułu.", "junk-page-07.invalid"),
)


def _entity_category(value: str) -> str:
    normalized = value.casefold()
    if any(token in normalized for token in ("szko", "liceum", "uczni")):
        return "szkola"
    if any(token in normalized for token in ("uczeln", "politechnik", "uniwersytet")):
        return "uczelnia"
    if any(token in normalized for token in ("jst", "gmin", "miast", "samorz")):
        return "jst"
    return "instytucja_publiczna"


def _reference_project_records(limit: int = REFERENCE_POSITIVE_COUNT) -> list[dict[str, Any]]:
    reference_path = PROJECT_DIR / "data" / "projects_example.json"
    data = json.loads(reference_path.read_text(encoding="utf-8"))
    grouped: dict[str, list[dict[str, Any]]] = {
        category: [] for category in ("szkola", "uczelnia", "jst", "instytucja_publiczna")
    }
    seen_names = set()
    for entry in data.get("wpisy", []):
        compatibility = entry.get("zgodnosc_z_wymogami_pci", {})
        name = str(entry.get("nazwa_projektu") or "").strip()
        if compatibility.get("czy_zgodny") is not True or not name or name.casefold() in seen_names:
            continue
        seen_names.add(name.casefold())
        category = _entity_category(str(entry.get("typ_podmiotu") or entry.get("kategoria_wejsciowa") or ""))
        grouped[category].append(entry)

    for entries in grouped.values():
        entries.sort(key=lambda entry: (entry.get("id", 0), entry.get("nazwa_projektu", "")))
    selected = []
    while len(selected) < limit and any(grouped.values()):
        for category in grouped:
            if grouped[category] and len(selected) < limit:
                selected.append(grouped[category].pop(0))
    if len(selected) != limit:
        raise ValueError(f"projects_example.json ma tylko {len(selected)} unikalnych zgodnych rekordow; wymagane {limit}")

    records = []
    for index, entry in enumerate(selected):
        compatibility = entry["zgodnosc_z_wymogami_pci"]
        url = str(entry.get("url") or "")
        name = str(entry.get("nazwa_projektu") or "")
        action = REFERENCE_ACTIONS[index % len(REFERENCE_ACTIONS)]
        fields = (
            entry.get("kategoria_wejsciowa"),
            entry.get("typ_podmiotu"),
            entry.get("typ_innowacji"),
            entry.get("tworcy_i_wiek"),
            compatibility.get("uzasadnienie"),
            " ".join(entry.get("keywords") or []),
        )
        records.append({
            "domain": urlsplit(url).hostname or f"reference-project-{entry.get('id', len(records))}.invalid",
            "url": url,
            "title": name,
            "text": "\n".join((
                name,
                f"Autorzy {action} rozwiązanie: {name}.",
                *(str(value).strip() for value in fields if value),
            )),
            "label": 1,
            "label_source": "generated_reference_article",
            "text_origin": "synthetic_paraphrase_from_projects_example",
            "entity_category": _entity_category(str(entry.get("typ_podmiotu") or "")),
            "reference_id": entry.get("id"),
        })
    return records


def _generated_positive_records() -> list[dict[str, Any]]:
    return [{
        "domain": domain,
        "title": title,
        "text": f"{title}.\n{content}",
        "label": 1,
        "label_source": "generated_positive_article",
        "entity_category": category,
    } for category, title, content, domain in GENERATED_POSITIVE_ARTICLES]


def _hard_negative_records(per_category: int = HARD_NEGATIVE_PER_CATEGORY) -> list[dict[str, Any]]:
    source_path = PROJECT_DIR / "data" / "hard_negatives.csv"
    with source_path.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        if row.get("label") != "0" or not row.get("title") or not row.get("content"):
            raise ValueError("hard_negatives.csv musi zawierac kompletne rekordy z etykieta 0")
        grouped.setdefault(row["entity_category"], []).append(row)

    generator = random.Random(DATASET_SEED)
    selected = []
    for category in sorted(grouped):
        candidates = sorted(grouped[category], key=lambda row: int(row["id"]))
        if len(candidates) < per_category:
            raise ValueError(f"Za malo hard-negative dla kategorii {category}")
        selected.extend(generator.sample(candidates, per_category))

    return [{
        "domain": f"hard-negative-{row['entity_category']}-{row['id']}.invalid",
        "title": row["title"],
        "text": f"{row['title']}\n{row['content']}",
        "label": 0,
        "label_source": "hard_negative_message",
        "entity_category": row["entity_category"],
        "hard_negative_type": row["hard_negative_type"],
        "source_record_id": int(row["id"]),
    } for row in selected]


def _article_records(examples: tuple[tuple[str, str, str, str], ...], label_source: str) -> list[dict[str, Any]]:
    records = []
    for example in examples:
        if len(example) == 4:
            category, title, content, domain = example
        else:
            title, content, domain = example
            category = "strona_smieciowa"
        records.append({
            "domain": domain,
            "title": title,
            "text": f"{title}\n{content}",
            "label": 0,
            "label_source": label_source,
            "entity_category": category,
        })
    return records


def build_training_dataset() -> dict[str, Any]:
    positive = _reference_project_records() + _generated_positive_records()
    negative = (
        _hard_negative_records()
        + _article_records(UNRELATED_ARTICLES, "generated_unrelated_article")
        + _article_records(JUNK_PAGES, "generated_junk_page")
    )
    if len(positive) != 20 or len(negative) != 35:
        raise ValueError(f"Nieprawidlowa liczebnosc datasetu: pozytywne={len(positive)}, negatywne={len(negative)}")
    records = positive + negative
    return {
        "description": "Kuratorowany dataset: syntetyczne artykuly o zgodnych projektach referencyjnych, wygenerowane innowacje, hard-negative, artykuly niezwiązane i strony-smieciowe.",
        "counts": {"project": len(positive), "non_project": len(negative)},
        "source_counts": {
            source: sum(record["label_source"] == source for record in records)
            for source in sorted({record["label_source"] for record in records})
        },
        "records": records,
    }


def write_dataset(output_path: Path, overwrite: bool = False) -> None:
    dataset = build_training_dataset()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w" if overwrite else "x", encoding="utf-8") as output:
        output.write(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n")
    print(f"Zapisano {output_path}: {dataset['counts']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Buduje kuratorowany dataset wykrywania innowacji.")
    parser.add_argument("--output", type=Path, default=PROJECT_DIR / "data" / "innovation_dataset.json")
    parser.add_argument("--force", action="store_true", help="Nadpisz istniejący zbiór")
    args = parser.parse_args()
    write_dataset(args.output, overwrite=args.force)


if __name__ == "__main__":
    main()