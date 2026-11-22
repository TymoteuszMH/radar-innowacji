# Innovation Radar — frontend

Angular 20 SPA do przeglądania katalogu innowacji, wyszukiwania projektów i analizy szczegółów. Frontend nie przechowuje rekordów ani nie implementuje własnego silnika oceny; pobiera dane z API backendu.

## Uruchomienie

Wymagany jest Node.js zgodny z Angular CLI 20.

```bash
npm install
npm start
```

`npm start` uruchamia Angular dev server domyślnie pod `http://localhost:4200`. Backend uruchom w drugim terminalu poleceniem `npm --prefix backend run start:dev` z katalogu głównego repozytorium. `npm run build` tworzy produkcyjny build w `dist/innovation-radar-angular`.

Development używa `http://127.0.0.1:3000` jako adresu backendu, zgodnie z [environment.development.ts](src/environments/environment.development.ts). Produkcyjne [environment.ts](src/environments/environment.ts) ma pusty `backendUrl`, więc żądania API są same-origin. Dla różnych originów backend musi mieć odpowiednią listę `CORS_ORIGINS`.

## Routing

Router używa zwykłych ścieżek bez hash-location:

| Ścieżka | Widok |
| --- | --- |
| `/innovations` | Katalog innowacji |
| `/innovations/:id` | Szczegóły innowacji |
| `/search` | Wyszukiwanie projektów zindeksowanych przez agenta |
| `/online` | Przekierowanie zgodności wstecznej do `/search` |
| `/needs` i `/needs/:id` | Przekierowanie do katalogu; API nie ma danych o potrzebach |

Hosting produkcyjny musi kierować bezpośrednie żądania nieznanych ścieżek aplikacji do `index.html`.

## Podział odpowiedzialności

- [app.routes.ts](src/app/app.routes.ts) definiuje adresy i tryby widoków.
- [page.component.ts](src/app/components/page/page.component.ts) wybiera ekran i pobiera jego dane.
- [search.component.ts](src/app/components/search/search.component.ts) obsługuje wyszukiwanie i prezentuje wyniki.
- [radar-api.service.ts](src/app/services/radar-api.service.ts) jest adapterem HTTP i mapuje odpowiedź wyszukiwania na typy UI.
- Interfejsy API są w [interfaces](src/app/interfaces).

## API

Wszystkie odpowiedzi są JSON-em. Frontend korzysta z:

| Metoda i ścieżka | Odpowiedź |
| --- | --- |
| `GET /api/innovations?q=...` | `{ items, organizations, total }` |
| `GET /api/innovations/:id` | Innowacja, ocena, podobne rekordy, działania i dowody |
| `GET /api/projects/search?q=...` | Tablica `{ project, matchedTerms }` |
| `POST /api/innovations/:id/analysis` | `{ analysis }`; opcjonalna analiza AI |

`matchedTerms` to dopasowane słowa, nie wynik trafności. Podobieństwa w szczegółach są heurystycznymi kandydatami i wymagają weryfikacji. Zapisywanie ani edycja rekordów nie są dostępne. Szczegóły konfiguracji i ograniczeń API: [README backendu](../backend/README.md).

## Walidacja

```bash
npm run build
```

Nie przesyłaj danych poufnych ani osobowych do niezabezpieczonego środowiska demonstracyjnego.
