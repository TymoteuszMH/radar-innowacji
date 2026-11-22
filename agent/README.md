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
uruchomieniem potrzebny jest wytrenowany model `models/project_agent.pt`:
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
`PROJECT_AGENT_TRAIN_EPOCHS`. Dropout modelu ustawisz przez
`PROJECT_AGENT_DROPOUT` (domyślnie `0.15`, zakres od 0 do poniżej 1); zmiana
wymaga ponownego treningu. Bezpośrednie uruchomienie `models/train_models.py`
wymaga istniejącego zbioru crawlera; brakujący zbiór projektów tworzy automatycznie.

## Niezależne wykrywanie projektów

`ProjectAgent` to sieć PyTorch, która klasyfikuje zapisane artykuły; używa jej
główny pipeline. Po treningu można go też uruchomić na gotowych wynikach:

```powershell
python -m agents.project_agent
```

Polecenie `python data/build_project_dataset.py` tworzy `data/innovation_dataset.json`
z przykładów syntetycznych, dostępnych znanych projektów i zapisanych wyników
crawlera oznaczanych jako negatywne. Nie nadpisuje istniejącego pliku bez opcji
`--force`. Zbiór można zastąpić ręcznie oznaczonymi danymi.
Po wydzieleniu domen walidacyjnych trening losowo ogranicza pozostałe przykłady
do dokładnie 50% pozytywnych i 50% negatywnych, bez powtórzeń i bez dodatkowego
ważenia klas. Wymaga obu klas w części treningowej. Walidacja zachowuje pierwotne proporcje.
Nieużyte przykłady pozostają w pliku źródłowym; wynik zależy od jakości etykiet.

Trening obu agentów dobiera próg wykrywania projektu oraz klasy `article`
crawlera na wydzielonych domenach, maksymalizując F-beta. Wspólną wartość beta
ustaw w `.env` jako `AGENT_F_BETA`; domyślnie wynosi 0,5, co daje większą wagę
precision niż recall. Zmiana wymaga ponownego
treningu obu modeli. Dla projektu uwzględnia także wymagany fragment źródłowy;
nieznane prawdopodobieństwo liczy się jako niewykrycie. Crawler dla wyników
poniżej progu wybiera najbardziej prawdopodobną spośród pozostałych kategorii.
Progi zapisywane są w checkpointach; stare modele zachowują poprzednie zachowanie.
Trening wykorzystuje pozostałe domeny, a wyświetlony F-beta służy do doboru progu,
więc nie jest niezależnym wynikiem testowym. W syntetycznym zbiorze crawlera
szablony mogą występować zarówno w treningu, jak i walidacji.
Wyniki na danych syntetycznych nie są niezależną
oceną skuteczności na rzeczywistych artykułach. Wagi modelu nie są wersjonowane.
Uruchomienie `ProjectAgent` zapisuje dwa pliki, nie zmieniając pliku wejściowego:
`results/projects.json` zawiera listę `projects` z nazwą projektu, opisem,
osobami, instytucją, fragmentami źródłowymi, adresem, `domain_tags` i `keywords`,
a `results/data.json` zawiera wszystkie
artykuły wraz z tekstem przekazanym modelowi (`analyzed_text`) i wynikiem
klasyfikacji (`project_detection`). Prawdopodobieństwo dotyczy wykrycia,
nie oceny wartości innowacji. Próg można ustawić przez `--threshold`, a ścieżki
plików przez `--output` i `--data-output`. Dla głównego pipeline'u ścieżki
można ustawić zmiennymi `PROJECTS_OUTPUT_FILE` i `PROJECT_DATA_OUTPUT_FILE`.
`--threshold` lub zmienna `PROJECT_AGENT_THRESHOLD` nadpisuje zapisany próg;
aby używać progu wyuczonego, należy usunąć tę zmienną z konfiguracji.

Model korzysta z tytułu i pełnej treści artykułu. Sieć wybiera artykuły, a dodatkowy warunek
wymaga opisu opracowania lub wdrożenia konkretnego rozwiązania. Może on pominąć
innowacje opisane innymi słowami. Pola projektu są
wyodrębniane prostymi regułami z tekstu źródłowego; nie są generowane przez sieć.
Nieznane dane pozostają puste, a gdy nie znaleziono nazwy, używany jest tytuł
źródła lub fragment tekstu. Artykuł może dać kilka rekordów, jeśli zawiera
kilka nazwanych projektów i dla każdego znaleziono fragment opisujący konkretne
rozwiązanie. Reguły przypisują opis i twórców na podstawie fragmentu tekstu,
więc mogą błędnie rozdzielić lub pominąć projekty.
W ramach jednego uruchomienia projekty o tej samej nazwie i tym samym zestawie
osób są pomijane jako duplikaty; jeśli brak osób, porównywana jest instytucja.
Porównanie ignoruje wielkość liter i nadmiarowe odstępy. Bez znanego twórcy
projekty nie są deduplikowane. Zachowywany jest pierwszy znaleziony rekord.
Plik wynikowy jest nadpisywany, a nie uzupełniany o wyniki poprzednich uruchomień.
Wyniki mogą zawierać błędy i wymagają weryfikacji.
Tagi dziedzinowe są wybierane z ograniczonej listy na podstawie słów w nazwie
i opisie projektu. Słowa kluczowe to maksymalnie 10 częstych słów z tych pól,
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
źródeł oraz maksymalnie 10 podobnych rekordów z tytułem, opisem, identyfikatorem,
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
