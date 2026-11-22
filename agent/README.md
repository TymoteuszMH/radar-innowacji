# Agent

Główny pipeline uruchamia `main.py`: crawler pobiera strony z `data/sites.csv`,
a `RawDataFormatter` wybiera do `results/results.json` artykuły opublikowane
w ciągu ostatnich `ARTICLE_MAX_AGE_DAYS` dni (domyślnie 7). Wartość ustawisz
w pliku `.env`. Data publikacji jest pobierana z metadanych strony;
artykuły bez rozpoznanej daty pozostają w danych crawlera, ale nie są analizowane.
Każdy przekazany artykuł zawiera domenę, URL, tytuł źródła, datę publikacji
i pełną treść otrzymaną od crawlera.
Następnie `ProjectAgent` wykrywa projekty i zapisuje je do
`results/projects.json`, a całą analizę do `results/data.json`. Przed pierwszym
uruchomieniem potrzebny jest wytrenowany model w katalogu `models/bert_innovation_classifier`:
uruchom `train.bat` przed pobieraniem danych.
Domyślnie po zakończeniu usuwany jest katalog danych crawlera; ustaw
`DELETE_SCRAPPED_AFTER_RUN=0` w `.env`, aby go zachować.

## Uruchomienie

Polecenia poniżej wykonuj w katalogu `agent`:

```powershell
$agentPython = if (Test-Path .\.venv\Scripts\python.exe) { ".\.venv\Scripts\python.exe" } else { "python" }
& $agentPython -m pip install -r requirements.txt
& $agentPython -m playwright install chromium
.\train.bat
.\run.bat
```

Chromium jest potrzebny do pobierania stron wymagających JavaScriptu.
Konfiguracja znajduje się w `.env`; ścieżki względne odnoszą się do katalogu
`agent`. Uruchomienie pipeline'u korzysta z sieci i może nadpisać wynik analizy.
Crawler podąża za przekierowaniami HTTP oraz podczas renderowania JavaScript,
analizuje stronę docelową i zapisuje adresy źródłowy oraz docelowy na liście
odwiedzonych. Po przekierowaniu strony startowej dalsze linki są ograniczone do
nowego adresu startowego. Oba adresy wliczają się do limitu odwiedzonych stron,
który pojedyncze przekierowanie może przekroczyć o jeden.

```powershell
.\train.bat
```

Skrypt trenuje modele crawlera i `ProjectAgent`, nadpisując ich checkpointy w
`models`. Dane crawlera generuje w katalogu tymczasowym i usuwa również w razie
błędu. Jeśli brakuje `data/innovation_dataset.json`, tworzy zbiór treningowy;
istniejącego zbioru nie nadpisuje. `RawDataFormatter` tylko
formatuje dane i nie wymaga treningu. Oba skrypty BAT
korzystają z `.venv`, jeśli istnieje, a w przeciwnym razie z Pythona w `PATH`.

Ścieżki danych i modelu projektów można ustawić zmiennymi
`PROJECT_AGENT_DATASET_PATH` i `PROJECT_AGENT_MODEL_PATH`, a liczbę epok przez
`PROJECT_AGENT_TRAIN_EPOCHS` (domyślnie 5). Bezpośrednie uruchomienie `models/train_models.py`
wymaga istniejącego zbioru crawlera; brakujący zbiór projektów tworzy automatycznie.

## Parametry w `.env`

Zmienne środowiskowe mają pierwszeństwo przed plikiem `.env`; bez nich używane
są wartości domyślne poniżej. Zmiany treningowe wymagają ponownego treningu.
Nieprawidłowe nowe wartości powodują błąd z nazwą zmiennej.

| Zmienna | Domyślnie | Znaczenie i zakres |
|---|---:|---|
| `MAX_VISITED_PAGES` | 50 | Maksimum odwiedzonych stron na domenę, co najmniej 1 |
| `CRAWL_CONCURRENCY` | 8 | Liczba równoległych zadań crawlera, co najmniej 1 |
| `CRAWLER_TIMEOUT_SECONDS` | 15 | Timeout HTTP crawlera w sekundach, co najmniej 1 |
| `MAX_ARTICLES_TO_PROCESS` | 0 | Limit artykułów; 0 oznacza bez limitu |
| `ARTICLE_MAX_AGE_DAYS` | 7 | Maksymalny wiek artykułu w dniach |
| `CRAWLER_AGENT_HIDDEN_SIZE` | 32 | Rozmiar warstwy ukrytej przy treningu crawlera |
| `CRAWLER_AGENT_TRAIN_EPOCHS` | 80 | Liczba epok treningu crawlera |
| `CRAWLER_AGENT_LEARNING_RATE` | 0.001 | Learning rate crawlera |
| `CRAWLER_AGENT_BATCH_SIZE` | 64 | Wielkość batcha crawlera |
| `PROJECT_AGENT_TRAIN_EPOCHS` | 5 | Liczba epok, co najmniej 1 |
| `PROJECT_AGENT_TRAIN_BATCH_SIZE` | 8 | Batch treningowy na urządzenie, co najmniej 1 |
| `PROJECT_AGENT_EVAL_BATCH_SIZE` | 8 | Batch walidacyjny na urządzenie, co najmniej 1 |
| `PROJECT_AGENT_LEARNING_RATE` | 0.00003 | Dodatni learning rate |
| `PROJECT_AGENT_WARMUP_RATIO` | 0.1 | Udział rozgrzewki, 0–1 |
| `PROJECT_AGENT_WEIGHT_DECAY` | 0.01 | Nieujemna regularyzacja |
| `PROJECT_AGENT_VALIDATION_FRACTION` | 0.2 | Udział walidacji, wyłącznie między 0 a 1 |
| `PROJECT_AGENT_SEED` | 42 | Ziarno treningu i podziału, 0–4294967295 |
| `PROJECT_AGENT_THRESHOLD` | zapisany w modelu, zwykle 0.5 | Opcjonalny próg wykrywania, 0–1 |
| `PROJECT_AGENT_KEYWORDS_MAX` | 10 | Maksimum słów i fraz kluczowych, co najmniej 1 |
| `PROJECT_AGENT_KEYWORD_PHRASES_MAX` | 5 | Maksimum fraz, nieujemne i ograniczone przez powyższy limit |
| `PROJECT_AGENT_EVIDENCE_MAX_SENTENCES` | 3 | Maksimum fragmentów dowodowych lub zdań opisu, co najmniej 1 |
| `PRIOR_ART_ENABLED` | 1 | Włącz porównywanie ze źródłami; `0` je wyłącza |
| `PRIOR_ART_TIMEOUT_SECONDS` | 15 | Dodatni timeout HTTP w sekundach |
| `PRIOR_ART_MAX_MATCHES` | 10 | Maksimum zwracanych podobnych rekordów, co najmniej 1 |
| `PRIOR_ART_MIN_SHARED_WORDS` | 2 | Minimalna liczba wspólnych słów, co najmniej 1 |
| `PRIOR_ART_MIN_SIMILARITY` | 0.2 | Minimalne podobieństwo, 0–1 |
| `PRIOR_ART_QUERY_MAX_WORDS` | 8 | Maksimum słów w zapytaniu, co najmniej 2 |
| `JS_RENDER_FALLBACK` | 1 | Włącz renderowanie stron przez Chromium |
| `JS_RENDER_TIMEOUT_SECONDS` | 20 | Timeout renderowania w sekundach, co najmniej 1 |
| `JS_RENDER_MIN_ARTICLE_CHARS` | 200 | Minimalna długość tekstu artykułu bez renderowania |
| `JS_PAGINATION_MAX_PAGES` | 10 | Maksimum stron paginacji JS |
| `JS_PAGINATION_SCROLLS` | 3 | Maksimum przewinięć dla leniwego ładowania |
| `LISTING_MIN_ARTICLE_LINKS` | 3 | Minimum linków do artykułów na stronie listującej |
| `JS_NETWORK_IDLE_TIMEOUT_MS` | 3000 | Limit oczekiwania na bezczynność sieci w ms, co najmniej 1; dodatkowo ograniczony przez `JS_RENDER_TIMEOUT_SECONDS` |
| `JS_SCROLL_WAIT_MS` | 250 | Czas po przewinięciu w ms, nieujemny |
| `JS_PAGINATION_WAIT_MS` | 500 | Czas po zmianie strony w ms, nieujemny |

Ścieżki `PROJECT_AGENT_DATASET_PATH`, `PROJECT_AGENT_MODEL_PATH`,
`PROJECTS_OUTPUT_FILE`, `PROJECT_DATA_OUTPUT_FILE` oraz `ANALYSIS_OUTPUT_FILE`
działają także przy bezpośrednim uruchomieniu odpowiednich skryptów.
Opcje CLI mają pierwszeństwo; przy jawnym `--output` i bez `--data-output`
dane trafiają do `data.json` obok wybranego pliku wyjściowego.
Przekazany do `PriorArtChecker` klient HTTP zachowuje własny timeout.

## Niezależne wykrywanie projektów

`ProjectAgent` wykorzystuje `sdadas/polish-distilroberta` z binarną głowicą
klasyfikacyjną. Trening wymaga pobrania modelu bazowego z Hugging Face;
inferencja ładuje wyłącznie lokalnie zapisany model i tokenizer.
Wytrenuj model ponownie i zmień ewentualną własną wartość
`PROJECT_AGENT_MODEL_PATH` na katalog.
Po treningu można uruchomić model na gotowych wynikach:

```powershell
python -m agents.project_agent
```

Polecenie `python data/build_project_dataset.py` tworzy `data/innovation_dataset.json`
z 20 pozytywnymi i 35 negatywnymi przykładami. Pozytywy to 12 syntetycznych
parafraz wpisów z `projects_example.json` jawnie oznaczonych jako zgodne z PCI
oraz 8 wygenerowanych artykułów o konkretnych rozwiązaniach. Negatywy obejmują
20 deterministycznie wybranych hard-negative z `data/hard_negatives.csv` (po 5
na kategorię szkoła, uczelnia, JST i instytucja publiczna), 8 artykułów
niezwiązanych z innowacjami i 7 stron-śmieciowych. Wszystkie rekordy zawierają
`label_source`; parafrazy referencji mają dodatkowo `text_origin` i identyfikator
wpisu źródłowego. Parafrazy nie są oryginalnymi artykułami, a przykłady generowane
nie są danymi z rzeczywistych wdrożeń. Generator używa stałego ziarna 42.
Nie nadpisuje istniejącego pliku bez opcji `--force`; użyj jej, aby odtworzyć
dataset z aktualnych źródeł. Zbudowany zbiór można też zastąpić własnymi,
ręcznie oznaczonymi danymi.
Trening dzieli wszystkie rekordy w proporcji 80/20 ze stratyfikacją etykiet;
wagi klas są obliczane wyłącznie z części treningowej. Najlepszy checkpoint
wybierany jest według F1 klasy 1 na walidacji. Domyślne parametry podano wyżej.
GPU CUDA jest używane, jeśli jest dostępne, w przeciwnym razie CPU.
Podział nie izoluje domen ani podobnych szablonów, więc wynik walidacji może
być zawyżony i nie stanowi niezależnego wyniku testowego.
Zbiór w projekcie ma obecnie 20 pozytywów i 35 negatywów, a nie 33/120;
aby użyć większego zbioru, podaj własny plik JSON `{"records": [...]}` z polami
`text` i `label` (lub `title`, `content` i `label`). Wynik zależy od jakości danych.

Crawler nadal dobiera próg klasy `article` na wydzielonych domenach,
maksymalizując F0,5.
W syntetycznym zbiorze crawlera
szablony mogą występować zarówno w treningu, jak i walidacji.
Wyniki na danych syntetycznych nie są niezależną
oceną skuteczności na rzeczywistych artykułach. Wagi modelu nie są wersjonowane.
Po zmianie generatora istniejący zbiór i model nie zmieniają się automatycznie.
Przed ponownym treningiem wygeneruj zbiór pod nową ścieżką lub świadomie użyj
`--force`. Opisy wzorcowe w treningu i dopasowanie znanych adresów nie są
niezależnym testem skuteczności modelu.
Uruchomienie `ProjectAgent` zapisuje dwa pliki, nie zmieniając pliku wejściowego:
`results/projects.json` zawiera listę `projects` z nazwą projektu, opisem,
osobami, instytucją, fragmentami źródłowymi, adresem, `domain_tags` i `keywords`,
a `results/data.json` zawiera wszystkie
artykuły wraz z tekstem przekazanym modelowi (`analyzed_text`) i wynikiem
klasyfikacji (`project_detection`). Prawdopodobieństwo dotyczy wykrycia,
nie oceny wartości innowacji. Próg można ustawić przez `--threshold`, a ścieżki
plików przez `--output` i `--data-output`. Dla głównego pipeline'u ścieżki
można ustawić zmiennymi `PROJECTS_OUTPUT_FILE` i `PROJECT_DATA_OUTPUT_FILE`.
`--threshold` lub zmienna `PROJECT_AGENT_THRESHOLD` nadpisuje próg zapisany w modelu.

Model korzysta z tytułu i treści artykułu. Powyżej 350 słów zachowuje pierwsze
200 i ostatnie 150 słów; jeśli nadal jest więcej niż 512 tokenów, zachowuje
tokeny z początku i końca. `predict(text, threshold=0.5)` zwraca `label`
oraz prawdopodobieństwo klasy 1; `predict_proba(text)` zachowuje dotychczasowy
interfejs. Artykuł spoza listy znanych adresów jest projektem tylko wtedy, gdy
przekracza próg modelu i treść zawiera rozpoznany dowód opracowania lub wdrożenia
rozwiązania. Sam wysoki wynik modelu nie wystarcza. Zweryfikowane wpisy referencyjne
zachowują swoje oznaczenia niezależnie od wyniku modelu.
Liczba wyników zależy od dostępnych artykułów i nie ma gwarantowanego minimum.
Pola projektu są
wyodrębniane prostymi regułami z tekstu źródłowego; nie są generowane przez sieć.
Nieznane dane pozostają puste, a gdy nie znaleziono nazwy, używany jest tytuł
źródła lub fragment tekstu. Artykuł może dać kilka rekordów, jeśli zawiera
kilka nazwanych projektów i dla każdego znaleziono fragment opisujący konkretne
rozwiązanie. Jeśli żaden fragment nie spełnia tego warunku, artykuł daje jeden
kandydat do weryfikacji. Reguły przypisują opis i twórców na podstawie fragmentu tekstu,
więc mogą błędnie rozdzielić lub pominąć projekty.
W ramach jednego uruchomienia projekty o tej samej nazwie i tym samym zestawie
osób są pomijane jako duplikaty; jeśli brak osób, porównywana jest instytucja.
Porównanie ignoruje wielkość liter i nadmiarowe odstępy. Bez znanego twórcy
projekty nie są deduplikowane. Zachowywany jest pierwszy znaleziony rekord.
Plik wynikowy jest nadpisywany, a nie uzupełniany o wyniki poprzednich uruchomień.
Wyniki mogą zawierać błędy i wymagają weryfikacji.
Licznik pokrycia porównuje unikalne adresy wynikowe z adresami w
`sites_and_projects.csv`, osobno licząc adresy spoza wzorca. To pokrycie adresów,
nie miara poprawności wykrywania; filtr dat i ograniczenia crawlera mogą wykluczyć
większość starszego zestawu wzorcowego.
Tagi dziedzinowe są wybierane z ograniczonej listy na podstawie słów w nazwie
i opisie projektu. Słowa kluczowe to domyślnie maksymalnie 10 częstych słów z tych pól,
z większą wagą nazwy i pominięciem wybranych słów ogólnych. Nie są odmieniane
ani generowane przez model; mogą być niepełne lub nietrafne. Starsze zapisane
projekty uzyskają je dopiero po ponownym uruchomieniu analizy.

## Ocena potencjału

Każdy nowo wykryty projekt zawiera `assessment`: trzy kryteria o wagach 45%,
35% i 20%, rozpoznane oceny 1–5 wraz z cytatami, wynik `score` w procentach,
pewność `coverage` (0–1), brakujące obszary, status i rekomendację. Wynik to
średnia ważona dostępnych ocen podzielona przez 5; bez ocen wynosi `null`.
Pewność jest sumą wag ocenionych kryteriów. Poniżej 70% status to `uncertain`,
w przeciwnym razie progi wyniku 75% i 50% wyznaczają `high`, `development`
albo `low`. Starsze pliki nie zawierają oceny: aby ją uzyskać, trzeba ponownie
uruchomić agenta na zapisanych artykułach.

Ocena jest ostrożną heurystyką językową, a nie pełnym badaniem eksperckim.
Rozpoznaje tylko wybrane sformułowania o możliwości transferu, adaptacji
istniejącej technologii i etapie prac; pomija niejednoznaczne, zaprzeczone lub
planowane informacje. Nagrody i hasła marketingowe nie są punktowane. Wykryte
podobieństwo nie dowodzi duplikatu, a brak wyników nie dowodzi nowości, dlatego
wyszukiwanie w obecnych bazach nie przyznaje automatycznie 1 ani 5 punktów za
unikalność. Rozpoznanie może pominąć fakty, mylić kontekst i wymaga sprawdzenia
cytatów przez człowieka. Projekt może podać kontakt w wierszu `Kontakt: adres`;
adres jest cytowany ze źródła, bez gwarancji, że należy do twórcy.

## Porównanie z istniejącymi rozwiązaniami

Domyślnie każdy wykryty projekt jest porównywany ze źródłami zewnętrznymi.
W `projects.json` pole `prior_art` zawiera zapytanie, status poszczególnych
źródeł oraz domyślnie maksymalnie 10 podobnych rekordów z tytułem, opisem, identyfikatorem,
adresem, wynikiem podobieństwa i wspólnymi słowami. `matches_found` oznacza
kandydatów do ręcznej weryfikacji, a `inconclusive` brak takich kandydatów,
nie potwierdzenie nowości projektu. Status `unavailable` lub `skipped` oznacza,
że dane źródło nie zostało sprawdzone.

- EPO OPS: wyszukiwanie danych bibliograficznych patentów z tej samej bazy co
  Espacenet i rejestr EPO. Zarejestruj aplikację na https://developers.epo.org/
  i ustaw w `.env` `EPO_OPS_KEY` oraz `EPO_OPS_SECRET`. Bez obu kluczy źródło
  będzie oznaczone jako niedostępne.
- Interreg: aktualny plik XLSX z https://interreg.gov.pl/lista-projektow/ jest
  pobierany raz w trakcie uruchomienia. Obejmuje programy zarządzane przez Polskę,
  a adres wyniku prowadzi do arkusza; numer projektu identyfikuje wiersz.
- Crossref: publiczne metadane publikacji naukowych, niezależne od PBN.
- PBN: wyszukiwanie publikacji po tytule przez oficjalne API. Wymaga ustawienia
  `PBN_APP_ID` i `PBN_APP_TOKEN` otrzymanych dla aplikacji instytucji. Dla
  publikacji bez DOI wynik zawiera identyfikator oraz adres wyszukiwarki PBN.

UPRP, PPM, biblioteki PAN i BazTOL oraz NCBiR nie są bezpośrednio
przeszukiwane. UPRP może wymagać kontroli bezpieczeństwa, a EPO OPS nie oznacza
pełnego pokrycia UPRP. Wyszukiwanie
porównuje dosłowne słowa tytułu i opisu, bez tłumaczenia, odmiany wyrazów ani
oceny zastrzeżeń patentowych; EPO, PBN i Crossref zwracają maksymalnie po 25 wyników.
Przesłanie zapytania do tych usług przekazuje im część tytułu i opisu projektu.
Nie zastępuje to profesjonalnego badania stanu techniki ani ustalenia tożsamości
projektów. W razie braku sieci źródła są oznaczane jako niedostępne, a projekty
nadal są zapisywane. Ustaw `PRIOR_ART_ENABLED=0` dla głównego pipeline'u lub użyj
`python -m agents.project_agent --no-prior-art`, aby pominąć ten etap.

## Struktura

- `crawler/` pobiera strony i klasyfikuje adresy.
- `crawler/raw_data_formatter.py` formatuje dane crawlera jako artykuły.
- `agents/project_agent.py` wykrywa potencjalne projekty w zapisanych wynikach.
- `data/build_project_dataset.py` przygotowuje syntetyczne dane dla ProjectAgent.
- `data/crawler_curated.json` przechowuje ręcznie oznaczone adresy crawlera.
- `models/train_project_agent.py` trenuje niezależny model ProjectAgent.
- `agents/content_utils.py` wyodrębnia główną treść HTML.
- `logging_utils.py` konfiguruje logowanie aktywnych modułów.
