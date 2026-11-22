# Innovation Radar — frontend Angular

Frontend używa komponentów Angulara, Angular Router i `HttpClient`. Dane, analiza oraz import i eksport wymagają backendu; aplikacja nie zawiera lokalnego silnika ani danych demonstracyjnych.

## Uruchomienie

W katalogu `frontend` uruchom `npm install`, a następnie `npm start`. `npm run build` tworzy wersję produkcyjną. Serwer deweloperski przekazuje żądania `/api/**` do `http://127.0.0.1:3000` przez [proxy.conf.json](proxy.conf.json). W produkcji serwer musi kierować `/api` do backendu.

**Backend nie implementuje jeszcze poniższego kontraktu.** Obecnie oferuje tylko `GET /projects/search` i `POST /assessment` o innych formatach. Do czasu rozbudowy backendu widoki wymagające danych pokażą błąd HTTP; nie są podstawiane fikcyjne dane. Backend nie został zmieniony w ramach migracji.

## Proponowany kontrakt backendu

Klient i typy odpowiedzi znajdują się w [radar-api.service.ts](src/app/radar-api.service.ts), a szczegółowe typy danych w odpowiednich komponentach. Wszystkie odpowiedzi, poza eksportem pliku, są JSON-em.

| Metoda i ścieżka | Żądanie | Odpowiedź |
| --- | --- | --- |
| `GET /api/dashboard` | — | `DashboardData`: `counts`, `featured`, `recent`, `organizations` |
| `GET /api/innovations`, `GET /api/needs` | opcjonalne `q` | `CatalogData`: `items`, `organizations`, `total` |
| `GET /api/innovations/:id` | — | dane szczegółów innowacji z `DetailView`, bez pola `kind` |
| `GET /api/needs/:id` | — | dane szczegółów potrzeby z `DetailView`, bez pola `kind` |
| `POST /api/innovations` | pola formularza, tagi jako tablice, opcjonalne metadane źródła | `{ "innovation": { "id": "..." } }` |
| `POST /api/needs` | pola formularza, tagi jako tablice | `{ "need": { "id": "..." } }` |
| `POST /api/innovations/extract` | JSON `{ "text": "..." }` albo `multipart/form-data` z polem `file` | `Extracted`: `fields`, `warnings`, `extracted_characters` |
| `POST /api/discovery/analyze` | `multipart/form-data`: powtarzane `files`, opcjonalne `text` | `DiscoveryReport`: `candidates`, `warnings`, `documents_count`, `method`, `disclaimer` |
| `GET /api/discovery/online` | `query`, `source` (`both`, `openalex`, `ncbr`), `limit` | `OnlineReport`: `query`, `sources`, `candidates`, `duplicates_count`, `errors`, `disclaimer` |
| `GET /api/workspace/export` | — | plik kopii JSON |
| `POST /api/workspace/import` | zawartość kopii JSON | odpowiedź sukcesu; import może zastąpić dane backendu |

Identyfikatory są dostarczane przez backend i przekazywane w adresach tras. API powinno zwracać odpowiednie kody HTTP i czytelne błędy. Frontend nie zakłada, że istniejący format projektów backendu odpowiada tym modelom.

Dokumenty oraz tekst do analizy są przesyłane do backendu. Nie należy przesyłać danych poufnych ani osobowych bez odpowiednich zabezpieczeń.
