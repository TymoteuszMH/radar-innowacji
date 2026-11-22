import json
import random
import re
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


PROJECT_DIR = Path(__file__).resolve().parent.parent
SOURCE_PATH = PROJECT_DIR / "data" / "article_mock.json"
OUTPUT_PATH = PROJECT_DIR / "data" / "dataset_clean.json"
SYNTHETIC_PER_CLASS = 500
REAL_OVERSAMPLE = 5
SEED = 20261122
EXPECTED_KEYS = {"url", "domain", "title", "content", "label", "is_article", "source_type"}
_WORD_QUESTION_MARK = re.compile(r"\w\?\w", re.UNICODE)

DOMAINS = (
    "lo4.edu.pl", "sp12-krakow.pl", "bip.gmina-zielonki.pl", "fundacja-edukacja.org.pl",
    "zsp-nowemiasto.edu.pl", "liceum-nadwislanskie.edu.pl", "gmina-brzeziny.pl", "ngo-mlodzi.org.pl",
    "zs3-powiat.pl", "biblioteka-miejska.org.pl", "sp7-olsztyn.pl", "centrum-kultury.edu.pl",
    "bip.powiat-polnoc.pl", "fundacja-rozwoj.org.pl", "zst-mazowsze.edu.pl", "szkola-miejska.pl",
    "gmina-lesna.pl", "stowarzyszenie-razem.org.pl", "lo-imienia-nauczyciela.edu.pl", "osrodek-edukacji.org.pl",
)
COMMON_ROUTES = (
    "/aktualnosci/{item_id}",
    "/?p={item_id}",
    "/index.php/wydarzenia/{slug}?ref={item_id}",
    "/projekty/{slug}/{item_id}",
    "/index.php/aktualnosci/{slug}",
)
ARTICLE_ROUTES = (
    "/relacje/{slug}/{item_id}",
    "/z-zycia-szkoly/{slug}/{item_id}",
    "/wydarzenia/{slug}-{item_id}",
    "/index.php/projekty/{slug}/wpis-{item_id}",
    "/aktualnosc/{slug}/{item_id}",
)
JUNK_ROUTES = (
    "/aktualnosci/archiwum?page={page}",
    "/bip/ogloszenia?page={page}",
    "/o-szkole/kadra",
    "/projekty/regulamin",
    "/dokumenty/{slug}",
)
SLUGS = (
    "projekt-badawczy", "innowacje-w-edukacji", "wyniki-konkursu", "nowe-laboratorium",
    "wspolpraca-uczniow", "bezpieczenstwo-w-szkole", "program-rozwoju", "badanie-srodowiska",
    "cyfrowa-pracownia", "spotkanie-informacyjne", "wycieczka-edukacyjna", "wolontariat-mlodziezy",
)
DATES = (
    "12.09.2025", "14.10.2025", "05.11.2025", "18.03.2026", "22.04.2026",
    "7 maja 2026", "16 czerwca 2026", "2 września 2026", "15 października 2026",
    "20 listopada 2026",
)
PEOPLE = (
    "Anna Nowak", "Ewa Kamińska", "Joanna Lewandowska", "Katarzyna Dudek", "Alicja Nowicka",
    "Monika Pawlak", "Zofia Jankowska", "Natalia Piotrowska",
)
SCHOOLS = (
    {"gen": "Liceum Ogólnokształcącego nr 4", "loc": "Liceum Ogólnokształcącym nr 4"},
    {"gen": "Szkoły Podstawowej nr 12", "loc": "Szkole Podstawowej nr 12"},
    {"gen": "Zespołu Szkół w Zielonkach", "loc": "Zespole Szkół w Zielonkach"},
    {"gen": "Centrum Edukacji w Brzezinach", "loc": "Centrum Edukacji w Brzezinach"},
    {"gen": "Zespołu Szkół Technicznych", "loc": "Zespole Szkół Technicznych"},
    {"gen": "szkoły miejskiej", "loc": "szkole miejskiej"},
)
PLACES = ("Toruniu", "Krakowie", "Gdańsku", "Warszawie", "Olsztynie", "Poznaniu", "Łodzi", "Lublinie")
TOPICS = (
    "jakości wody", "robotyki edukacyjnej", "historii regionu", "energii odnawialnej",
    "czytelnictwa wśród młodzieży", "bezpieczeństwa w sieci", "ochrony lokalnej przyrody",
    "promocji zdrowia", "współpracy międzynarodowej", "edukacji zawodowej",
    "wolontariatu szkolnego", "wykorzystania nowych technologii", "wsparcia uczniów",
    "kultury regionu", "bezpiecznego transportu", "przedsiębiorczości młodzieży",
)
AMOUNTS = (
    "12 tysięcy złotych", "18 tysięcy złotych", "25 tysięcy złotych", "40 tysięcy złotych",
    "60 tysięcy złotych", "80 tysięcy złotych", "120 tysięcy złotych", "250 tysięcy złotych",
)

ARTICLE_STORIES = (
    ("Uczniowie wrócili z wycieczki edukacyjnej", (
            "W {date} grupa uczniów ze szkoły odwiedziła Muzeum Okręgowe w {place}. Program obejmował wystawę i warsztaty.",
        "Opiekę nad grupą sprawowała {person}. Po powrocie uczniowie przygotowali relację ze spotkania.",
    )),
    ("Ogłoszono wyniki konkursu przedmiotowego", (
        "W konkursie nagrodzono pracę przygotowaną przez {person}. Jury doceniło samodzielny research i prezentację wyników.",
        "Uroczystość odbyła się {date} w {school_loc}. Laureat opowiedział o przygotowaniach.",
    )),
    ("Placówka zaprasza na dzień otwarty", (
        "Dzień otwarty odbędzie się {date} w {school_loc}. Spotkanie rozpocznie się o godzinie 10.00.",
        "W programie są prezentacje pracowni, rozmowy z nauczycielami i warsztaty dla kandydatów.",
        "Informacji o wydarzeniu udziela {person}.",
    )),
    ("Zakończyła się szkolna akcja charytatywna", (
            "W akcji zebrano {amount} na zakup wyposażenia dla lokalnego hospicjum.",
        "Włączyli się uczniowie, rodzice i pracownicy {school_gen}. Koordynację prowadzi {person}.",
        "Podziękowania przekazano darczyńcom {date}.",
    )),
    ("Dyrekcja przekazała komunikat społeczności szkoły", (
            "Dyrekcja szkoły poinformowała o zmianie organizacji zajęć w dniu {date}.",
        "Decyzję podjęto po konsultacjach z pracownikami i przedstawicielami rodziców.",
        "Za przygotowanie harmonogramu odpowiada {person}.",
    )),
    ("Rozpoczęto realizację projektu międzynarodowego", (
            "W {school} rozpoczęto realizację projektu Erasmus+ dotyczącego {topic}.",
        "Uczestnicy wezmą udział w warsztatach i wymianie doświadczeń.",
        "Koordynację projektu prowadzi {person}. Pierwsze spotkanie partnerów odbyło się {date}.",
        "W kolejnych miesiącach zaplanowano wyjazdy edukacyjne i podsumowanie rezultatów.",
    )),
    ("Uczennica opowiedziała o projekcie badawczym", (
        "W rozmowie z redakcją {person} opowiedziała o badaniu dotyczącym {topic}.",
        "Prace rozpoczęły się wiosną w laboratorium szkolnym. Uczennica porównuje próbki i zapisuje wyniki.",
        "Gotowy raport zostanie zaprezentowany {date}.",
    )),
    ("Zespół rozpoczął badania nad lokalnym środowiskiem", (
        "Zespół badawczy rozpoczął pomiary dotyczące {topic} w okolicy szkoły.",
        "Uczniowie pobierają próbki według harmonogramu i konsultują wyniki z ekspertem.",
        "Za koordynację odpowiada {person}. Pierwsze dane zebrano {date}.",
    )),
    ("Drużyna zdobyła medal w zawodach wojewódzkich", (
        "Reprezentacja {school_gen} zajęła drugie miejsce w wojewódzkich zawodach sportowych.",
        "Finał rozegrano {date}. Zespół przygotowywał się do startu pod opieką {person}.",
        "Uczestnicy wskazali, że o wyniku zdecydowała współpraca i regularne treningi.",
    )),
    ("W bibliotece otwarto wystawę prac uczniowskich", (
        "Wystawę dotyczącą {topic} można oglądać w bibliotece szkolnej do końca miesiąca.",
        "Zaprezentowano fotografie, plakaty i prace wykonane podczas zajęć.",
        "Przygotowania koordynowała {person}. Wernisaż odbył się {date}.",
    )),
    ("Fundacja przyznała grant na rozwój inicjatywy", (
            "Fundacja Edukacja przyznała {school_loc} grant w wysokości {amount}.",
        "Środki przeznaczono na wyposażenie pracowni i zajęcia dotyczące {topic}.",
        "Projekt prowadzi {person}; zakończenie zaplanowano na przyszły rok.",
    )),
    ("Uczniowie zaprezentowali prototyp urządzenia", (
            "Porozumienie podpisali przedstawiciele szkoły i domu kultury.",
        "Zespół zebrał uwagi uczestników i przygotował listę zmian przed kolejnymi testami.",
        "Opiekę nad pracami sprawuje {person}. Demonstracja odbyła się {date}.",
    )),
    ("Szkoła i lokalna instytucja rozpoczęły współpracę", (
        "Porozumienie podpisali przedstawiciele {school_gen} i domu kultury.",
        "Program obejmuje warsztaty, spotkania z ekspertami i działania dotyczące {topic}.",
        "W imieniu zespołu projektowego dokument podpisała {person}.",
    )),
    ("Wystartował cykl warsztatów dla młodzieży", (
            "W akcji porządkowej uczestniczyli uczniowie szkoły i mieszkańcy gminy.",
        "Uczestnicy pracowali w małych zespołach i przygotowali propozycje dalszych działań.",
        "Cykl prowadzi {person}; kolejne spotkanie odbędzie się w przyszłym miesiącu.",
    )),
    ("Mieszkańcy i uczniowie posprzątali teren nad rzeką", (
        "W akcji porządkowej uczestniczyli uczniowie {school_gen} i mieszkańcy gminy.",
        "Zebrano odpady z kilku odcinków brzegu, a część materiałów przekazano do recyklingu.",
        "Wydarzenie koordynowała {person}. Kolejną akcję zaplanowano {date}.",
    )),
    ("Uczestnicy podsumowali efekty całorocznych działań", (
        "Podczas spotkania w {school_loc} przedstawiono rezultaty projektu dotyczącego {topic}.",
        "Uczestnicy omówili zadania, trudności i plany na kolejny etap.",
        "Podsumowanie przygotowała {person}. Prezentacja odbyła się {date}.",
        "W wydarzeniu wzięli udział uczniowie i partnerzy projektu.",
    )),
)

JUNK_CASES = (
    ("Lista aktualności", "Ostatnie wpisy:\n{title1} — {date1}\n{title2} — {date2}\n{title3} — {date3}\nWięcej »\nStrona {page} z 14. Poprzednia | Następna"),
    ("Plan dzwonków", "Lekcja 1: 8:00–8:45. Lekcja 2: 8:55–9:40. Lekcja 3: 9:50–10:35. Przerwa obiadowa rozpoczyna się po szóstej lekcji."),
    ("Plan lekcji", "Poniedziałek: matematyka, język polski, biologia. Wtorek: historia, fizyka, język angielski. Wybierz klasę z listy, aby zobaczyć pełny harmonogram."),
    ("Wykaz podręczników", "Klasa 1A: język polski — lista wydawnictw. Klasa 1B: matematyka — zakres podstawowy. Pliki z wykazami można pobrać w sekcji dokumentów."),
    ("Kontakt z sekretariatem", "Adres: ul. Szkolna 12. Telefon: 12 345 67 89. Sekretariat pracuje w dni robocze w godzinach 7:30–15:30. Napisz do nas przez formularz."),
    ("Klauzula informacyjna RODO", "Administratorem danych jest placówka. Dane są przetwarzane w celu obsługi spraw uczniów i rodziców. Przysługuje prawo dostępu, sprostowania i usunięcia danych."),
    ("Deklaracja dostępności", "Placówka zobowiązuje się zapewnić dostępność cyfrową strony. Zgłoszenia barier można przekazywać na adres sekretariatu."),
    ("Dokumenty do pobrania", "Regulamin_konkursu_2025.pdf (450 KB)\nZgoda_rodzica.docx (82 KB)\nHarmonogram_zajec.pdf (220 KB)\nPobierz plik | Wróć do dokumentów."),
    ("Brak wpisów w tej kategorii", "Brak wpisów w tej kategorii. Wybierz inną kategorię z menu lub wróć na stronę główną."),
    ("Menu strony", "Start | O szkole | Aktualności | Projekty | Dokumenty | Kontakt. Przejdź do treści. Mapa strony. Polityka prywatności. Administrator serwisu."),
    ("Ogłoszenia BIP", "Lista ogłoszeń urzędu:\nOgłoszenie o naborze — {date1}\nInformacja o konsultacjach — {date2}\nStrona 1 z 8. Następna strona »"),
    ("Wykaz kadry", "Dyrektor: Jan Kowalski. Sekretariat: Anna Nowak. Nauczyciele pełnią dyżury według harmonogramu. Wybierz nazwisko, aby sprawdzić godziny konsultacji."),
    ("Regulamin projektu", "Uczestnik zobowiązuje się przestrzegać zasad rekrutacji. Formularz zgłoszeniowy należy złożyć w sekretariacie do wskazanego terminu."),
    ("Informacja o zapisach", "Zapisy prowadzone są w sekretariacie. Należy dostarczyć wniosek, zdjęcie i zgodę opiekuna. Lista wymaganych dokumentów znajduje się poniżej."),
    ("Wyniki wyszukiwania", "Znaleziono 12 pozycji. Sortuj według daty lub tytułu. Poprzednia strona | Strona {page} z 5 | Następna strona."),
)

COMMON_ROUTES = (
    "/aktualnosci/{item_id}",
    "/?p={item_id}",
    "/index.php/wydarzenia/{slug}?ref={item_id}",
    "/projekty/{slug}/{item_id}",
    "/index.php/aktualnosci/{slug}/{item_id}",
)
ARTICLE_ROUTES = (
    "/relacje/{slug}/{item_id}",
    "/z-zycia-szkoly/{slug}/{item_id}",
    "/wydarzenia/{slug}-{item_id}",
    "/index.php/projekty/{slug}/wpis-{item_id}",
    "/aktualnosc/{slug}/{item_id}",
)
JUNK_ROUTES = (
    "/aktualnosci/archiwum?page={page}",
    "/bip/ogloszenia?page={page}",
    "/o-szkole/kadra",
    "/projekty/regulamin",
    "/dokumenty/{slug}",
)
DOMAIN_POOL = (
    "lo4.edu.pl", "sp12-krakow.pl", "bip.gmina-zielonki.pl", "fundacja-edukacja.org.pl",
    "zsp-nowemiasto.edu.pl", "liceum-nadwislanskie.edu.pl", "gmina-brzeziny.pl", "ngo-mlodzi.org.pl",
    "zs3-powiat.pl", "biblioteka-miejska.org.pl", "sp7-olsztyn.pl", "centrum-kultury.edu.pl",
    "bip.powiat-polnoc.pl", "fundacja-rozwoj.org.pl", "zst-mazowsze.edu.pl", "szkola-miejska.pl",
    "gmina-lesna.pl", "stowarzyszenie-razem.org.pl", "lo-imienia-nauczyciela.edu.pl", "osrodek-edukacji.org.pl",
)
TOPICS = (
    "jakości wody", "robotyki edukacyjnej", "historii regionu", "energii odnawialnej",
    "czytelnictwa wśród młodzieży", "bezpieczeństwa w sieci", "ochrony lokalnej przyrody",
    "promocji zdrowia", "współpracy międzynarodowej", "edukacji zawodowej",
    "wolontariatu szkolnego", "wykorzystania nowych technologii", "wsparcia uczniów",
    "kultury regionu", "bezpiecznego transportu", "przedsiębiorczości młodzieży",
)
PLACES = ("Toruniu", "Krakowie", "Gdańsku", "Warszawie", "Olsztynie", "Poznaniu", "Łodzi", "Lublinie")
SCHOOLS = (
    "Liceum Ogólnokształcącym nr 4", "Szkole Podstawowej nr 12", "Zespole Szkół w Zielonkach",
    "Centrum Edukacji w Brzezinach", "Zespole Szkół Technicznych", "szkole miejskiej",
)
PEOPLE = (
    "Anna Nowak", "Marek Zieliński", "Ewa Kamińska", "Piotr Wiśniewski", "Joanna Lewandowska",
    "Tomasz Wójcik", "Katarzyna Dudek", "Robert Kaczmarek", "Alicja Nowicka", "Paweł Król",
    "Monika Pawlak", "Jakub Malinowski", "Zofia Jankowska", "Grzegorz Michalski", "Natalia Piotrowska",
)
AMOUNTS = ("12 tysięcy złotych", "18 tysięcy złotych", "25 tysięcy złotych", "40 tysięcy złotych", "60 tysięcy złotych", "80 tysięcy złotych")
DATES = ("12.09.2025", "14.10.2025", "05.11.2025", "18.03.2026", "22.04.2026", "7 maja 2026", "16 czerwca 2026", "2 września 2026")
ARTICLE_STORIES = (
    ("Uczniowie wrócili z wycieczki edukacyjnej", ("W {date} uczniowie odwiedzili muzeum w {place}. Program obejmował wystawę i warsztaty.", "Opiekę nad grupą sprawowała {person}. Po powrocie uczniowie przygotowali relację ze spotkania.")),
    ("Ogłoszono wyniki konkursu przedmiotowego", ("W konkursie nagrodzono pracę uczennicy {person}. Jury doceniło samodzielny research i prezentację wyników.", "Uroczystość odbyła się {date} w {school}. Osoba wyróżniona opowiedziała o przygotowaniach.")),
    ("Placówka zaprasza na dzień otwarty", ("Dzień otwarty odbędzie się {date} w {school}. Spotkanie rozpocznie się o godzinie 10.00.", "W programie są prezentacje pracowni, rozmowy z nauczycielami i warsztaty dla kandydatów.", "Informacji o wydarzeniu udziela {person}.")),
    ("Zakończyła się szkolna akcja charytatywna", ("W akcji zebrano {amount} na zakup wyposażenia dla lokalnego hospicjum.", "Włączyli się uczniowie, rodzice i pracownicy szkoły. Koordynację prowadzi {person}.", "Podziękowania przekazano darczyńcom {date}.")),
    ("Dyrekcja przekazała komunikat społeczności szkoły", ("Dyrekcja placówki poinformowała o zmianie organizacji zajęć w dniu {date}.", "Decyzję podjęto po konsultacjach z pracownikami i przedstawicielami rodziców.", "Za przygotowanie harmonogramu odpowiada {person}.")),
    ("Rozpoczęto realizację projektu międzynarodowego", ("W {school} rozpoczęto projekt Erasmus+ dotyczący {topic}.", "Uczestnicy wezmą udział w warsztatach i wymianie doświadczeń.", "Koordynację projektu prowadzi {person}. Pierwsze spotkanie partnerów odbyło się {date}.", "W kolejnych miesiącach zaplanowano wyjazdy edukacyjne i podsumowanie rezultatów.")),
    ("Uczennica opowiedziała o projekcie badawczym", ("W rozmowie z redakcją {person} opowiedziała o badaniu dotyczącym {topic}.", "Prace rozpoczęły się wiosną w laboratorium szkolnym. Uczennica porównuje próbki i zapisuje wyniki.", "Gotowy raport zostanie zaprezentowany {date}.")),
    ("Zespół rozpoczął badania nad lokalnym środowiskiem", ("Zespół badawczy rozpoczął pomiary dotyczące {topic} w okolicy szkoły.", "Uczniowie pobierają próbki według harmonogramu i konsultują wyniki z ekspertem.", "Za koordynację odpowiada {person}. Pierwsze dane zebrano {date}.")),
    ("Drużyna zdobyła medal w zawodach wojewódzkich", ("Drużyna szkolna zajęła drugie miejsce w wojewódzkich zawodach sportowych.", "Finał rozegrano {date}. Zespół przygotowywał się do startu pod okiem trenerów.", "Uczestnicy wskazali, że o wyniku zdecydowała współpraca i regularne treningi.")),
    ("W bibliotece otwarto wystawę prac uczniowskich", ("Wystawę dotyczącą {topic} można oglądać w bibliotece szkolnej do końca miesiąca.", "Zaprezentowano fotografie, plakaty i prace wykonane podczas zajęć.", "Przygotowania koordynowała {person}. Wernisaż odbył się {date}.")),
    ("Fundacja przyznała grant na rozwój inicjatywy", ("Fundacja Edukacja przyznała placówce oświatowej grant w wysokości {amount}.", "Środki przeznaczono na wyposażenie pracowni i zajęcia dotyczące {topic}.", "Projekt prowadzi {person}; zakończenie zaplanowano na przyszły rok.")),
    ("Uczniowie zaprezentowali prototyp urządzenia", ("Podczas spotkania w {school} zaprezentowano prototyp wspierający {topic}.", "Zespół zebrał uwagi uczestników i przygotował listę zmian przed kolejnymi testami.", "Opiekę nad pracami sprawuje {person}. Demonstracja odbyła się {date}.")),
    ("Szkoła i lokalna instytucja rozpoczęły współpracę", ("Porozumienie podpisali przedstawiciele szkoły i domu kultury.", "Program obejmuje warsztaty, spotkania z ekspertami i działania dotyczące {topic}.", "W imieniu zespołu projektowego dokument podpisała {person}.")),
    ("Wystartował cykl warsztatów dla młodzieży", ("Pierwsze warsztaty dotyczące {topic} odbyły się {date} w {school}.", "Uczestnicy pracowali w małych zespołach i przygotowali propozycje dalszych działań.", "Cykl prowadzi {person}; kolejne spotkanie odbędzie się w przyszłym miesiącu.")),
    ("Mieszkańcy i uczniowie posprzątali teren nad rzeką", ("W akcji porządkowej uczestniczyli uczniowie szkoły i mieszkańcy gminy.", "Zebrano odpady z kilku odcinków brzegu, a część materiałów przekazano do recyklingu.", "Wydarzenie koordynowała {person}. Kolejną akcję zaplanowano {date}.")),
    ("Uczestnicy podsumowali efekty całorocznych działań", ("Podczas spotkania w {school} przedstawiono rezultaty projektu dotyczącego {topic}.", "Uczestnicy omówili zadania, trudności i plany na kolejny etap.", "Podsumowanie przygotowała {person}. Prezentacja odbyła się {date}.", "W wydarzeniu wzięli udział uczniowie i partnerzy projektu.")),
)


def _existing_real_records() -> list[dict[str, Any]]:
    source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    real_records = {}
    for row in source.get("articles", []):
        is_real = row.get("source_type") == "real" or row.get("source") == "real_curated_4lo"
        if not is_real:
            continue
        label = row.get("label")
        is_article = row.get("is_article")
        if label not in {"article", "junk"}:
            if not isinstance(is_article, bool):
                continue
            label = "article" if is_article else "junk"
        elif isinstance(is_article, bool) and (is_article != (label == "article")):
            raise ValueError(f"Niespójna etykieta w rekordzie real: {row.get('url')}")
        url = row.get("url")
        if not isinstance(url, str) or not urlsplit(url).hostname:
            continue
        real_records[url] = {
            "url": url,
            "domain": row.get("domain") or urlsplit(url).hostname or "",
            "title": row.get("title") or "",
            "content": row.get("content") or "",
            "label": label,
            "is_article": label == "article",
            "source_type": "real",
        }
    return list(real_records.values())


def _add_noise(content: str, index: int, date: str, rng: random.Random) -> str:
    if index % 5 not in (0, 1):
        return content
    prefix = (
        f"Start > Aktualności > Wydarzenia\nOpublikowano: {date}\nAutor: Administrator\n\n",
        f"Opublikowano: {date}\nStart > Życie szkoły > Relacje\n\n",
    )
    suffix = (
        f"\n\nAutor: Redakcja\nLiczba odsłon: {rng.randint(42, 2841)}\nCzytaj więcej...",
        f"\n\nOpublikowano: {date}\nLiczba odsłon: {rng.randint(42, 2841)}",
    )
    return rng.choice(prefix) + content if index % 2 == 0 else content + rng.choice(suffix)


def _format_story(index: int, rng: random.Random) -> tuple[str, str]:
    title_template, paragraphs = ARTICLE_STORIES[index % len(ARTICLE_STORIES)]
    school = SCHOOLS[(index * 7) % len(SCHOOLS)]
    fields = {
        "date": DATES[(index * 3) % len(DATES)],
        "person": PEOPLE[(index * 7) % len(PEOPLE)],
        "school": school,
        "place": PLACES[(index * 5) % len(PLACES)],
        "topic": TOPICS[(index * 11) % len(TOPICS)],
        "amount": AMOUNTS[(index * 3) % len(AMOUNTS)],
    }
    title = title_template.format(**fields)
    paragraph_text = [paragraph.format(**fields) for paragraph in paragraphs]
    return title, "\n\n".join(paragraph_text)


def _synthetic_url(index: int, is_article: bool, item_id: int, slug: str) -> tuple[str, str]:
    domain = DOMAINS[index % len(DOMAINS)]
    route_index = index % 10
    if route_index < len(COMMON_ROUTES):
        route = COMMON_ROUTES[route_index].format(item_id=item_id, slug=slug)
    elif is_article:
        route = ARTICLE_ROUTES[route_index - len(COMMON_ROUTES)].format(item_id=item_id, slug=slug)
    else:
        route = JUNK_ROUTES[route_index - len(COMMON_ROUTES)].format(
            page=(item_id % 14) + 1,
            slug=slug,
        )
        if "?" in route:
            route += f"&ref={item_id}"
        else:
            route += f"?ref={item_id}"
    return f"https://{domain}{route}", domain


def _synthetic_records() -> list[dict[str, Any]]:
    rng = random.Random(SEED)
    identifiers = rng.sample(range(10_000, 999_999), SYNTHETIC_PER_CLASS * 2)
    records: list[dict[str, Any]] = []

    for label, is_article, offset in (("article", True, 0), ("junk", False, SYNTHETIC_PER_CLASS)):
        for index in range(SYNTHETIC_PER_CLASS):
            global_index = offset + index
            item_id = identifiers[global_index]
            slug = SLUGS[(index * 7 + offset) % len(SLUGS)]
            url, domain = _synthetic_url(index, is_article, item_id, slug)
            if is_article:
                title, content = _format_story(index, rng)
                content = _add_noise(content, index, DATES[(index * 3) % len(DATES)], rng)
            else:
                case_title, template = JUNK_CASES[index % len(JUNK_CASES)]
                fields = {
                    "title1": ("Warsztaty dla uczniów", "Zmiana organizacji zajęć", "Spotkanie informacyjne")[index % 3],
                    "title2": ("Konkurs szkolny", "Dzień otwarty", "Komunikat dyrekcji")[(index + 1) % 3],
                    "title3": ("Zajęcia biblioteczne", "Wyniki naboru", "Konsultacje społeczne")[(index + 2) % 3],
                    "date1": DATES[index % len(DATES)],
                    "date2": DATES[(index + 3) % len(DATES)],
                    "date3": DATES[(index + 6) % len(DATES)],
                    "page": (item_id % 13) + 1,
                }
                title = case_title
                content = template.format(**fields)
            records.append({
                "url": url,
                "domain": domain,
                "title": title,
                "content": content,
                "label": label,
                "is_article": is_article,
                "source_type": "synthetic",
            })
    return records


def build_dataset() -> dict[str, Any]:
    real_base = _existing_real_records()
    real_oversampled = [dict(record) for record in real_base for _ in range(REAL_OVERSAMPLE)]
    synthetic = _synthetic_records()
    records = real_oversampled + synthetic
    random.Random(SEED).shuffle(records)
    return {
        "description": (
            "Czysty dataset UTF-8. Zawiera 1000 nowych rekordów syntetycznych, "
            "zbalansowanych 500/500, oraz istniejące rekordy realne powtórzone 5 razy. "
            "Domeny i pięć rodzin ścieżek URL są wspólne dla obu klas; source_type odróżnia źródło."
        ),
        "synthetic_count": len(synthetic),
        "real_unique_count": len(real_base),
        "real_oversample_factor": REAL_OVERSAMPLE,
        "counts": {
            "synthetic": dict(Counter(record["label"] for record in synthetic)),
            "real_unique": dict(Counter(record["label"] for record in real_base)),
            "all_records": dict(Counter(record["label"] for record in records)),
        },
        "records": records,
    }


def validate_dataset(dataset: dict[str, Any]) -> None:
    records = dataset["records"]
    synthetic = [record for record in records if record["source_type"] == "synthetic"]
    real = [record for record in records if record["source_type"] == "real"]
    assert len(synthetic) == 1000
    assert Counter(record["label"] for record in synthetic) == {"article": 500, "junk": 500}
    assert len(real) == dataset["real_unique_count"] * REAL_OVERSAMPLE
    assert all(set(record) == EXPECTED_KEYS for record in records)
    assert all(record["is_article"] == (record["label"] == "article") for record in records)
    assert all(not _WORD_QUESTION_MARK.search(record["title"] + " " + record["content"]) for record in records)
    assert all("\ufffd" not in record["title"] + record["content"] for record in records)

    article_domains = Counter(record["domain"] for record in synthetic if record["is_article"])
    junk_domains = Counter(record["domain"] for record in synthetic if not record["is_article"])
    assert article_domains == junk_domains
    article_common_routes = Counter(index % 5 for index in range(SYNTHETIC_PER_CLASS) if index % 10 < 5)
    junk_common_routes = Counter(index % 5 for index in range(SYNTHETIC_PER_CLASS) if index % 10 < 5)
    assert article_common_routes == junk_common_routes
    assert len({record["url"] for record in synthetic}) == len(synthetic)


def main() -> None:
    dataset = build_dataset()
    validate_dataset(dataset)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(dataset, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    # Re-read with UTF-8 to validate the actual serialized artifact.
    validate_dataset(json.loads(OUTPUT_PATH.read_text(encoding="utf-8")))
    print(f"Dataset: {OUTPUT_PATH}")
    print(f"Records: {len(dataset['records'])}")
    print(f"Synthetic: {dataset['synthetic_count']} (500 article / 500 junk)")
    print(f"Unique real: {dataset['real_unique_count']} x {REAL_OVERSAMPLE} = {dataset['real_unique_count'] * REAL_OVERSAMPLE}")
    print("Label counts:", dataset["counts"]["all_records"])
    print("Validation: UTF-8, schema, balance, shared domain/path distributions, no in-word '?' or U+FFFD")


if __name__ == "__main__":
    main()
