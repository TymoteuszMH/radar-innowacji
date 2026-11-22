# Backend — NestJS

Backend udostepnia JSON API dla frontendu Angular i czyta wynik agenta Python z `agent/results/projects.json`. Nie tworzy ani nie edytuje rekordow.

## Uruchomienie

Wymagany jest Node.js 20 lub nowszy. Z katalogu `backend`:

```bash
npm install
npm run start:dev
```

`npm run build` kompiluje TypeScript, `npm start` uruchamia skompilowany serwer, a `npm test` buduje projekt i uruchamia testy Node.js. Domyslny port to `3000`; zmien go przez `PORT`.

## Dane i architektura

Plik musi zawierac obiekt `{"projects": [...]}` w formacie generowanym przez [agenta](../agent/README.md). Backend odczytuje plik przy kazdym zadaniu; `PROJECTS_FILE` moze wskazac inna lokalizacje. Nie ma bazy danych, uwierzytelniania ani zapisu przez API.

`ProjectsController` waliduje HTTP i deleguje prace do `ProjectsService`. Serwis mapuje rekordy agenta na kontrakt frontendowy, generuje stabilne dla danego rekordu identyfikatory i dostarcza tekstowe wyszukiwanie. Zmiana tresci rekordu moze zmienic jego identyfikator.

## Endpointy

| Metoda i sciezka | Zachowanie |
| --- | --- |
| `GET /api/innovations?q=...` | Katalog; opcjonalne filtrowanie tekstowe; zwraca `items`, `organizations`, `total` |
| `GET /api/innovations/:id` | Szczegoly innowacji, ocena, cytaty, podobne rekordy i dalsze kroki |
| `GET /api/projects/search?q=...&keywords=...` | Wyszukiwanie tekstowe; zwraca `{ project, matchedTerms }[]` |
| `GET /projects/search` | Alias zgodnosci wstecznej dla wyszukiwania |
| `GET /api/needs` | Pusta lista: brak danych o potrzebach organizacji |
| `GET /api/needs/:id` | `404`: rekordy potrzeb nie sa dostepne |
| `POST /api/innovations/:id/analysis` | Opcjonalna analiza AI; nie zmienia zapisanej oceny |
| `POST /assessment` | Placeholder: `criteria_not_configured`; nie liczy ani nie zapisuje oceny |

Wyszukiwanie ignoruje wielkosc liter i polskie znaki, dopasowuje fragmenty slow w polach projektu i ogranicza zapytanie `q` do 180 znakow, a `keywords` do 500. Co najmniej jedno slowo musi byc podane. `matchedTerms` jest lista dopasowan, a nie wynikiem trafnosci.

## Podobienstwa i kolejne kroki

Szczegoly porownuja projekt z innymi rekordami po wspolnych obszarach, slowach kluczowych i terminach tytulu. Zwracaja do pieciu kandydatow z wynikiem heurystycznym i powodami. Nie jest to dowod duplikatu ani potwierdzenie relacji partnerskiej. `actions` powstaje z brakujacych pytan oceny i jej statusu; kazdy krok zawiera warunek weryfikacji.

Nie ma zrodel potrzeb organizacji, wiec backend nie dopasowuje projektow do konkretnych odbiorcow, partnerow ani inwestorow. Oceny i podobienstwa wymagaja recznej weryfikacji.

## Konfiguracja i bezpieczenstwo

| Zmienna | Domyslnie | Znaczenie |
| --- | --- | --- |
| `PORT` | `3000` | Port HTTP |
| `PROJECTS_FILE` | `agent/results/projects.json` | Plik wejsciowy projektow |
| `CORS_ORIGINS` | `http://localhost:4200,http://127.0.0.1:4200` | Dozwolone originy przegladarki, rozdzielane przecinkami |
| `OPENAI_API_KEY` | brak | Wlacza endpoint analizy AI |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model OpenAI dla analizy |

Analiza AI jest ograniczona do 10 zapytan na adres IP w ciagu 10 minut. Licznik jest lokalny dla procesu i nie wystarcza dla wielu instancji. Przed publicznym wdrozeniem dodaj uwierzytelnianie oraz limit wspoldzielony na bramie API. Odpowiedz OpenAI moze generowac koszty i nie zastapia oceny eksperckiej.

## Testy

```bash
npm test
```
