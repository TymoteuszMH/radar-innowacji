# Innovation Radar — frontend Angular

Frontend używa komponentów Angulara, Angular Router i `HttpClient`. Dane i analiza wymagają backendu; aplikacja nie zawiera lokalnego silnika ani danych demonstracyjnych.

## Uruchomienie

W katalogu `frontend` uruchom `npm install`, a następnie `npm start`. `npm run build` tworzy wersję produkcyjną. Adres backendu jest ustawiony w [environment.development.ts](src/environments/environment.development.ts) dla developmentu oraz w [environment.ts](src/environments/environment.ts) dla produkcji. Domyślnie development łączy się bezpośrednio z `http://127.0.0.1:3000`, a produkcja używa tego samego hosta co frontend. Dla różnych hostów backend musi zezwalać na żądania CORS.

Wyszukiwanie i katalog innowacji korzystają z projektów w `agent/results/projects.json`.

## Kontrakt backendu

Klient i typy odpowiedzi znajdują się w [radar-api.service.ts](src/app/services/radar-api.service.ts), a szczegółowe typy danych w odpowiednich komponentach. Wszystkie odpowiedzi są JSON-em.

| Metoda i ścieżka                     | Żądanie        | Odpowiedź                                                 |
| ------------------------------------ | -------------- | --------------------------------------------------------- |
| `GET /api/innovations`               | opcjonalne `q` | `CatalogData`: `items`, `organizations`, `total`          |
| `GET /api/innovations/:id`           | —              | dane szczegółów innowacji z `DetailView`, bez pola `kind` |
| `GET /api/projects/search`           | `q`            | tablica `{ project, matchedTerms }`                       |
| `POST /api/innovations/:id/analysis` | —              | `{ "analysis": "..." }`                                   |

Identyfikatory projektów są generowane z treści rekordu, dlatego zmiana rekordu zmienia jego adres. Zapisywanie danych nie jest obsługiwane.

Opcjonalna analiza AI wymaga konfiguracji backendu i przesyła tytuł, opis oraz brakujące obszary do OpenAI. Szczegóły znajdują się w [dokumentacji backendu](../backend/README.md).

Nie należy przesyłać danych poufnych ani osobowych bez odpowiednich zabezpieczeń.
