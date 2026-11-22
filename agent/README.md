# Agent

Główny pipeline uruchamia `main.py`: crawler pobiera strony z `data/sites.csv`,
a `RawDataFormatter` formatuje zapisane treści do `results/results.json` bez
klasyfikacji i analizy projektów. Każdy artykuł zawiera domenę, URL, tytuł
źródła i pełną treść otrzymaną od crawlera.
Domyślnie po zakończeniu usuwany jest katalog danych crawlera; ustaw
`DELETE_SCRAPPED_AFTER_RUN=0` w `.env`, aby go zachować.

## Uruchomienie

Polecenia poniżej wykonuj w katalogu `agent`:

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
.\run.bat
```

Chromium jest potrzebny do pobierania stron wymagających JavaScriptu.
Konfiguracja znajduje się w `.env`; ścieżki względne odnoszą się do katalogu
`agent`. Uruchomienie pipeline'u korzysta z sieci i może nadpisać wynik analizy.

```powershell
.\train.bat
```

Skrypt trenuje modele crawlera i `ProjectAgent`, nadpisując ich checkpointy w
`models`. Dane crawlera generuje w katalogu tymczasowym i usuwa również w razie
błędu. Jeśli brakuje `data/project_dataset.json`, tworzy go na podstawie
`results/results.json`; istniejącego zbioru nie nadpisuje. `RawDataFormatter` tylko
formatuje dane i nie wymaga treningu. Oba skrypty BAT
korzystają z `.venv`, jeśli istnieje, a w przeciwnym razie z Pythona w `PATH`.

Ścieżki danych i modelu projektów można ustawić zmiennymi
`PROJECT_AGENT_DATASET_PATH` i `PROJECT_AGENT_MODEL_PATH`, a liczbę epok przez
`PROJECT_AGENT_TRAIN_EPOCHS`. Bezpośrednie uruchomienie `models/train_models.py`
wymaga istniejącego zbioru crawlera; brakujący zbiór projektów tworzy z
`ANALYSIS_OUTPUT_FILE` lub domyślnego `results/results.json`.

## Niezależne wykrywanie projektów

`ProjectAgent` to osobna sieć PyTorch, która klasyfikuje zapisane artykuły,
nie uruchamiając crawlera ani `RawDataFormatter`. Można go trenować razem z crawlerem
przez `train.bat` albo osobno i użyć na gotowych wynikach:

```powershell
python data/build_project_dataset.py
python models/train_project_agent.py
python -m agents.project_agent
```

Pierwsze polecenie tworzy `data/project_dataset.json` na podstawie listy
`articles` w `results/results.json`. Reguły przypisują etykiety 1 (potencjalny
projekt) i 0 (pozostały artykuł); niejednoznaczne przykłady znajdują się w
`unlabeled`. Etykiety są automatyczne i mogą być błędne, dlatego przed użyciem
w praktyce należy je ręcznie zweryfikować i uzupełnić. Ponowne generowanie
nadpisuje zbiór, w tym ręczne poprawki. Parametry `--input` i `--output`
pozwalają wskazać inne pliki.

Trening zapisuje `models/project_agent.pt` i wyświetla precision oraz recall na
wydzielonych domenach. Są to wyniki względem etykiet bootstrapowych, a nie
niezależna ocena rzeczywistej skuteczności. Wagi modelu nie są wersjonowane.
Ostatnie polecenie zapisuje dwa pliki, nie zmieniając pliku wejściowego:
`results/projects.json` zawiera listę `projects` z domeną, adresem i tytułem
źródła dla znalezionych kandydatów, a `results/data.json` zawiera wszystkie
artykuły wraz z tekstem przekazanym modelowi (`analyzed_text`) i wynikiem
klasyfikacji (`project_detection`). Prawdopodobieństwo dotyczy wykrycia,
nie oceny wartości innowacji. Próg można ustawić przez `--threshold`, a ścieżki
plików przez `--output` i `--data-output`.

Model korzysta z tytułu i pełnej treści w nowych wynikach. W starszych wynikach
korzysta z tytułu, streszczenia, faktów i fragmentów, ponieważ nie zawierają
pełnej treści. Po zmianie formatu warto ponownie przygotować i zweryfikować dane
treningowe oraz wytrenować model. Model wykrywa rekordy kandydatów, nie wyodrębnia
gotowych danych projektu, nie rozdziela kilku projektów opisanych w jednym
artykule ani nie generuje nowych opisów. Tytuł źródła nie musi być nazwą projektu.

## Struktura

- `crawler/` pobiera strony i klasyfikuje adresy.
- `crawler/raw_data_formatter.py` formatuje dane crawlera jako artykuły.
- `agents/project_agent.py` wykrywa potencjalne projekty w zapisanych wynikach.
- `data/build_project_dataset.py` przygotowuje dane bootstrapowe dla ProjectAgent.
- `models/train_project_agent.py` trenuje niezależny model ProjectAgent.
- `agents/content_utils.py` wyodrębnia główną treść HTML.
- `logging_utils.py` konfiguruje logowanie aktywnych modułów.
- `data/archive/` przechowuje historyczne wagi nieużywane przez aktualny pipeline.
