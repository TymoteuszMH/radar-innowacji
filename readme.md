# Radar innowacji

> Ukryte innowacje - jak odnaleźć pomysły, które mogą zmieniać świat?

Radar innowacji to prototyp wspierający wczesne wykrywanie, porządkowanie i wstępną ocenę projektów opisywanych w publicznych źródłach. Powstał w kontekście wyzwania Podkarpackiego Centrum Innowacji (PCI), które łączy świat nauki, biznesu i administracji oraz wspiera rozwój innowacji w regionie. Wyzwanie zwraca uwagę na rozwiązania tworzone w szkołach, uczelniach, samorządach i innych instytucjach publicznych, które często pozostają znane tylko lokalnie.

PCI wspiera merytorycznie i finansowo projekty badawczo-rozwojowe uczelni i firm, prowadzi programy akceleracyjne oraz udostępnia laboratoria i narzędzia do prototypowania. Wskazywane obszary obejmują m.in. motoryzację, jakość życia, ICT, lotnictwo i sektor kosmiczny; infrastruktura wspiera młodych innowatorów w wieku 16-30 lat.

Prototyp ma pokazać drogę od publicznego opisu projektu do katalogu, wstępnej oceny, porównania z innymi rozwiązaniami i wskazania następnych kroków. Innowacja może być technologiczna, edukacyjna, organizacyjna, społeczna lub procesowa. To niezależny prototyp konkursowy, a nie oficjalny system PCI.

## Co działa

- Agent Python pobiera strony z listy źródeł, filtruje artykuły według daty i wykrywa potencjalne projekty.
- Agent porządkuje dostępne informacje: nazwę, opis, instytucje, twórców, cytaty, adres źródła, tagi i słowa kluczowe.
- Projekt otrzymuje wstępną ocenę w trzech wymiarach: potencjał wdrożeniowy (45%), innowacyjność i unikalność (35%) oraz wykonalność i dojrzałość (20%). Ocena może zawierać cytaty, wskazać braki i zaproponować dalsze kroki.
- Agent porównuje wykryte projekty z wybranymi źródłami zewnętrznymi. Backend dodatkowo wskazuje heurystycznie podobne rekordy z katalogu.
- Backend udostępnia katalog, szczegóły, tekstowe wyszukiwanie i opcjonalną analizę AI. Frontend pokazuje katalog pod `/innovations`, szczegóły pod `/innovations/:id` i wyszukiwarkę pod `/search`.

Wyszukiwanie w aplikacji obejmuje rekordy, które agent już zapisał. Nie jest to wyszukiwarka całego internetu ani formularz zgłaszania pomysłów.

## Jak przepływają dane

```mermaid
flowchart LR
	S[Wybrane publiczne strony] --> C[Crawler]
	C --> F[Filtr dat i formatowanie]
	F --> A[ProjectAgent: wykrywanie i ekstrakcja]
	A --> R[agent/results/projects.json]
	A --> P[Porównanie z bazami zewnętrznymi]
	R --> B[Backend NestJS]
	B --> U[Frontend Angular]
	U --> H[Weryfikacja człowieka i dalsze kroki]
```

Szczegółowy pipeline uruchamia się w katalogu `agent`. Agent domyślnie analizuje artykuły z rozpoznaną datą publikacji z ostatnich 7 dni; zakres można zmienić przez `ARTICLE_MAX_AGE_DAYS`. Lista punktów startowych znajduje się w [agent/data/sites.csv](agent/data/sites.csv). Obecna lista obejmuje wybrane witryny z całej Polski, nie tylko województwo podkarpackie.

Backend czyta `agent/results/projects.json` przy każdym zadaniu. Plik może zostać zastąpiony przez `PROJECTS_FILE`. Identyfikator rekordu jest wyliczany z jego UUID lub treści; zmiana treści rekordu bez UUID może zmienić adres szczegółów.

## Ocena i porównania

Ocena potencjału jest ostrożna i heurystyczna. Rozpoznaje wybrane fakty z tekstu i podaje wynik oraz pokrycie rozpoznanych kryteriów. Prawdopodobieństwo klasyfikatora `ProjectAgent` dotyczy wykrycia projektu w artykule, a nie jego wartości ani szans wdrożenia. Oba wyniki wymagają weryfikacji źródeł i ekspertów.

### Metodologia oceny w systemie „Radar innowacji”

Ocena ma charakter wstępnej selekcji merytorycznej. Algorytm odrzuca relacje z wydarzeń, takie jak wycieczki czy apele, i wyodrębnia opisane rozwiązania technologiczne, procesowe, organizacyjne, edukacyjne lub społeczne. Z relacji o konkursie studenckim zostaje zatem wyciągnięty tylko opis konkretnego prototypu lub metody badawczej.

Ocena opiera się wyłącznie na faktach zawartych w źródle. Brak danych o wdrożeniu nie powoduje sztucznego zaniżenia punktacji. Sformułowania oceniające, takie jak „nowatorski”, oraz nagrody w lokalnych konkursach nie podwyższają punktacji. Ocena marketingowa nie zastępuje weryfikacji nowości i dojrzałości projektu.

Każde kryterium ocenia się w skali od 1 do 5 punktów i ma następującą wagę:

| Kryterium | Waga | Przedmiot oceny | Przykłady punktacji |
| --- | ---: | --- | --- |
| Potencjał wdrożeniowy | 45% | Możliwość skalowania i transferu rozwiązania do innych organizacji lub firm oraz obecność ścieżki odbioru. | **1 pkt:** działanie jednorazowe, możliwe wyłącznie w jednej placówce.<br>**3 pkt:** ustandaryzowany schemat możliwy do przeniesienia po adaptacji.<br>**5 pkt:** gotowy do powielenia model ze wskazanym partnerem lub sektorem odbiorców. |
| Innowacyjność i unikalność | 35% | Obiektywna nowość weryfikowana w bazach patentowych UPRP i EPO, naukowych PBN oraz projektowych NCBiR i Interreg, aby eliminować dublowanie prac. | **1 pkt:** identyczne rozwiązanie jest już w rejestrze patentowym lub bazie projektów.<br>**3 pkt:** adaptacja istniejącej technologii o nową zmienną lub lokalny surowiec.<br>**5 pkt:** brak bezpośrednich odpowiedników w bazach patentowych i naukowych. |
| Wykonalność i dojrzałość | 20% | Aktualny etap prac (koncepcja, prototyp, pilotaż) oraz realność zasobów potrzebnych do uruchomienia rozwiązania. | **1 pkt:** ogólnikowe hasło bez opisanej mechaniki działania.<br>**3 pkt:** ustrukturyzowana koncepcja, np. wynik hackathonu, wymagająca walidacji.<br>**5 pkt:** działający prototyp, przetestowany pilotaż lub udokumentowana procedura gotowa do wdrożenia. |

W przypadku niepełnego opisu system publikuje dwa niezależne wskaźniki:

- **Wynik potencjału (%)** — średnia ważona wyliczona wyłącznie z kryteriów potwierdzonych faktami w tekście.
- **Pewność oceny (%)** — suma wag kryteriów, dla których źródło zawiera twarde dane.

Gdy pewność jest niższa niż 70%, rekord otrzymuje etykietę `Niepewna ocena`, wskazanie brakującego obszaru oraz dwie możliwe akcje:

1. wstępna analiza tematu z Asystentem AI;
2. bezpośredni kontakt ze wskazanymi w tekście twórcami lub jednostką.

Przykład: artykuł opisuje cel projektu badawczego, ale pomija sposób jego komercjalizacji. Pewność oceny wynosi 55%, dlatego karta pokazuje ostrzeżenie i umożliwia szybki kontakt z wydziałem uczelni.

| Wynik potencjału | Pewność | Status na karcie | Rekomendowane działanie |
| --- | ---: | --- | --- |
| 75%–100% | co najmniej 70% | Wysoki potencjał | Przekazanie do programów akceleracyjnych, transferu lub bezpośrednich rozmów z partnerami wdrożeniowymi. |
| 50%–74% | co najmniej 70% | Potencjał rozwojowy | Skierowanie na mentoring, do laboratoriów prototypowania lub doprecyzowanie założeń. |
| Dowolny wynik | poniżej 70% | Niepewna ocena | Weryfikacja tematu z Asystentem Ai lub bezpośredni kontakt z autorami rozwiązania. |
| Poniżej 50% | co najmniej 70% | Niski potencjał / Duplikat | Weryfikacja podobnych projektów wskazanych przez system w bazach, np. Interreg i NCBiR, w celu współpracy zamiast powielania prac. |

Porównanie zewnętrzne może korzystać z:

| Źródło                                    | Stan                                                    |
| ----------------------------------------- | ------------------------------------------------------- |
| Crossref                                  | Publiczne metadane publikacji                           |
| Interreg                                  | Katalog projektów pobierany z serwisu Interreg Polska   |
| Epo Ops                                   | Wymaga `EPO_OPS_KEY` i `EPO_OPS_SECRET`                 |
| Pbn                                       | Wymaga `PBN_APP_ID` i `PBN_APP_TOKEN`                   |
| UPRP, PPM, biblioteki PAN i BazTOL, NCBiR | Nie są bezpośrednio przeszukiwane przez obecny pipeline |

Brak znalezionego podobieństwa nie potwierdza nowości. Porównania tekstowe nie zastępują badania stanu techniki, analizy zastrzeżeń patentowych ani ustalenia, czy dwa wpisy opisują ten sam projekt. Zapytania do źródeł zewnętrznych mogą przekazywać fragmenty tytułu i opisu.

## Dane referencyjne i walidacja

`agent/data/projects_example.json` zawiera datowane zestawienie referencyjne z 22 listopada 2026 r.: 33 wpisy, z czego 23 oznaczono jako zgodne z kryteriami PCI, a 10 jako niezgodne lub do odrzucenia. Plik jest wykorzystywany przy budowie przykładów treningowych. Nie jest to liczba rekordów w aktywnym katalogu API ani niezależny test skuteczności modelu.

Zbiór treningowy łączy przykłady syntetyczne, opisy znanych projektów i ręcznie oznaczone negatywne wyniki crawlera. Trening dobiera progi na wydzielonych domenach, ale ten wynik nie jest niezaleznym pomiarem skuteczności na nowych, rzeczywistych danych. Do wiarygodnej oceny potrzebny jest większy, ręcznie oznaczony zbiór testowy.

Backend testuje kontrakt API, wyszukiwanie, podobieństwa i ograniczenia zapytań. Frontend jest budowany przez Angular CLI. Testy automatyczne nie dowodzą poprawności ekstrakcji ani trafności rekomendacji na rzeczywistych przypadkach.

### Scenariusz demonstracyjny

1. Wyszukaj projekt w `/search` albo otwórz katalog `/innovations`.
2. Przejdź do szczegółów i sprawdź opis, autorów, instytucje, cytaty oraz źródło.
3. Omów ocenę, jej pokrycie, brakujące informacje i uzasadnienia poszczególnych kryteriow.
4. Pokaż wewnętrzne podobieństwa i wyniki porównania zewnętrznego, podkreślając ich ograniczenia.
5. Zakończ proponowanym następnym krokiem i warunkiem jego weryfikacji.

Demonstracje nalezy przeprowadzić na co najmniej dwóch rekordach z aktualnego `agent/results/projects.json`. Zestaw `projects_example.json` może dostarczyć przykładów referencyjnych, ale nie jest automatycznie katalogiem serwowanym przez Api.

### Mierniki do walidacji

Model nie ma jeszcze niezależnych wyników skuteczności na rzeczywistym, oznaczonym zbiorze. W pilocie warto mierzyć precision i recall wykrywania, odsetek rekordów z wystarczającymi dowodami do oceny, zgodność ocen ekspertów oraz trafność pierwszych wyników podobieństwa. Czas od wykrycia projektu do decyzji o dalszym kroku może mierzyć sprawność procesu. Te mierniki wymagają zebrania i oznaczenia przypadków; obecne testy automatyczne ich nie zastąpiły.

## Ograniczenia i dalszy rozwój

- Nie ma formularza zgłaszania innowacji, edycji rekordów, kont użytkowników ani zapisu przez API.
- API potrzeb organizacji zwraca pustą listę. Nie ma wiarygodnego dopasowania projektu do konkretnego odbiorcy, partnera ani inwestora.
- Podobieństwo w katalogu jest heurystyką opartą na wspólnych obszarach, słowach kluczowych i terminach tytułu. Nie potwierdza duplikatu ani relacji partnerskiej.
- Dane są przechowywane jako wynikowy plik JSON, bez wielodostępowej bazy danych. Nie jest to gotowy system produkcyjny dla wielu organizacji.
- Endpoint AI jest opcjonalny, może generować koszty, ma limit w pamięci pojedynczego procesu i nie ma uwierzytelniania. Przed publicznym wdrożeniem wymagane są m.in. uwierzytelnianie, współdzielone limity, polityka danych i bezpieczna konfiguracja hostingu.

Najważniejszym kolejnym krokiem jest uzupełnienie katalogu potrzeb instytucji i danych o potencjalnych użytkownikach, a następnie walidacja na oznaczonych przypadkach z kilku typów organizacji. Przy wdrożeniu należy zachować jasne kryteria oceny, wskazać źródła danych, zapewnić ochronę danych i możliwość integracji z systemami instytucji.

## Uruchomienie

Wymagania: Node.js 20 lub nowszy dla backendu, Node.js zgodny z Angular CLI 20 oraz Python opisany w [README agenta](agent/README.md).

Zainstaluj zależności osobno:

```powershell
npm --prefix backend install
npm --prefix frontend install
```

Uruchom backend i frontend w dwóch terminalach z katalogu głównego:

```powershell
npm --prefix backend run start:dev
```

```powershell
npm --prefix frontend start
```

Backend domyślnie działa na `http://localhost:3000`, frontend na `http://localhost:4200`. Development frontendu łączy się z backendem przez `http://127.0.0.1:3000`; domyślne `CORS_ORIGINS` backendu dopuszcza lokalne originy na porcie 4200. Produkcyjny frontend uzywa same-origin Api i wymaga, aby serwer zwracał `index.html` dla tras Angulara.

Do uruchomienia pipeline'u agenta przejdź do katalogu `agent`. Przed pierwszym uruchomieniem lub po zmianie modelu wytrenuj checkpointy, a następnie uruchom crawler:

```powershell
cd agent
& (Join-Path $Pwd 'train.bat')
& (Join-Path $Pwd 'run.bat')
```

Agent korzysta z sieci, a jego uruchomienie może nadpisać pliki w `agent/results/`. Wymaga zależności z `agent/requirements.txt` oraz Chromium Playwright; pełna instrukcja i zmienne konfiguracyjne są w [README agenta](agent/README.md).

## Testy i build

```powershell
npm --prefix backend test
npm --prefix frontend run build
```

Testy agenta uruchom z katalogu `agent`:

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

## Struktura repozytorium

| Ścieżka                            | Rola                                                                                    |
| ---------------------------------- | --------------------------------------------------------------------------------------- |
| `agent/`                           | Crawler, formatowanie, wykrywanie projektów, ocena, źródła porównawcze i trening modeli |
| `backend/`                         | NestJS API, mapowanie katalogu, wyszukiwanie i analiza AI                               |
| `frontend/`                        | Angular SPA: katalog, karta projektu i wyszukiwarka                                     |
| `agent/data/sites.csv`             | Punkty startowe crawlera                                                                |
| `agent/data/projects_example.json` | Zestaw referencyjny do przygotowania przykładów treningowych                            |
| `agent/results/`                   | Wyniki pipeline'u czytane przez backend                                                 |

## Kontekst konkursowy

Wyzwanie dotyczy wczesnego odnajdywania rozwiązań tworzonych m.in. w szkołach, uczelniach i samorządach, ich wstępnej oceny oraz kierowania do dalszego rozwoju, transferu, komercjalizacji lub wdrożenia. Docelowymi użytkownikami są przedstawiciele instytucji publicznych oraz podmioty poszukujące rozwiązań.

Kryteria oceny konkursowej: zgodność z wyzwaniem, oryginalność, użyteczność i UX, kompletność prototypu oraz potencjał wdrożeniowy i skalowalność - po 20% każde. To osobne kryteria od wewnętrznej, heurystycznej oceny potencjału innowacji opisanej wyżej.

Zgłoszenie formalne wymaga osobnej prezentacji PDF do 10 slajdów oraz filmu do 3 minut udostępnionego pod publicznym linkiem. Ten README opisuje repozytorium i nie zastępuje tych materiałów.

Kontakt do wyzwania PCI: Kacper Moczarny, [k.moczarny@pcinn.org](mailto:k.moczarny@pcinn.org).

Szczegóły techniczne: [frontend](frontend/README.md), [backend](backend/README.md), [agent](agent/README.md).
