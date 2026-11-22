# Backend NestJS

Wymagany Node.js 20 lub nowszy.

```bash
cd backend
npm install
npm run build
npm start
```

Serwer dziala domyslnie na porcie 3000 (zmienna `PORT`). Dane sa odczytywane przy kazdym wyszukiwaniu z `agent/results/projects.json`. Opcjonalnie `PROJECTS_FILE` wskazuje inny plik w tym samym formacie.

## Wyszukiwanie

`GET /projects/search?q=szkola&keywords=technologie,edukacja`

Wymagane jest co najmniej jedno slowo w `q` lub `keywords`. Wyszukiwanie ignoruje wielkosc liter i polskie znaki, dopasowuje fragmenty slow w tytule, opisie, faktach, dowodach i pozostalych kluczowych polach. Zwraca projekty z co najmniej jednym pasujacym slowem, uporzadkowane wedlug liczby dopasowanych slow. Odpowiedz to tablica obiektow `{ "project": ..., "matchedTerms": [...] }`. Jest to wyszukiwanie tekstowe, nie ocena projektu.

## Ocena

`POST /assessment` z naglowkiem `Content-Type: application/json` i trescia np. `{"parameters":{"budget":100}}`.

Do czasu ustalenia kryteriow odpowiedz zawiera `status: "criteria_not_configured"`, `score: null` oraz otrzymane parametry. Kryteria nalezy zaimplementowac w `src/assessment.service.ts`.

Testy: `npm test`.
