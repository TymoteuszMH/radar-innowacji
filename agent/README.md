# Agent

Główny pipeline uruchamia `main.py`: crawler pobiera strony z `data/sites.csv`,
a `LocalAgent` analizuje zapisane treści i tworzy `results/results.json`.
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

Skrypt generuje dane treningowe w katalogu tymczasowym, trenuje oba modele i
usuwa te dane również w przypadku błędu. Trening nadpisuje checkpointy w
`models`. Oba skrypty BAT korzystają z `.venv`, jeśli istnieje, a w przeciwnym
razie z Pythona dostępnego w `PATH`.

## Struktura

- `crawler/` pobiera strony i klasyfikuje adresy.
- `agents/local_agent.py` klasyfikuje i analizuje treść lokalnie.
- `agents/content_utils.py` wyodrębnia główną treść HTML.
- `logging_utils.py` konfiguruje logowanie aktywnych modułów.
- `data/archive/` przechowuje historyczne wagi nieużywane przez aktualny pipeline.
