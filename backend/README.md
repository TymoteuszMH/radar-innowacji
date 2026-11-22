# Backend NestJS

Wymagany Node.js 20 lub nowszy.

```bash
cd backend
npm install
npm run build
npm start
```

Serwer dziala domyslnie na porcie 3000 (zmienna `PORT`). Dane sa odczytywane przy kazdym wyszukiwaniu z `agent/results/projects.json`. Opcjonalnie `PROJECTS_FILE` wskazuje inny plik w tym samym formacie.

## Katalog

`GET /api/innovations` zwraca katalog projektow, a opcjonalne `q` filtruje go wedlug slow wystepujacych w projekcie. `GET /api/innovations/:id` zwraca szczegoly i fragmenty zrodlowe. Identyfikator jest skrotem tresci rekordu i zmienia sie po jego zmianie; identyczne rekordy sa wyswietlane raz.

Katalog i szczegoly zwracaja `domain_tags` oraz `keywords` zapisane przez agenta;
starsze rekordy bez tych pol otrzymuja puste listy. Oba pola sa przeszukiwane.

`GET /api/needs` zwraca pusta liste, a `GET /api/needs/:id` zwraca 404, poniewaz plik nie zawiera potrzeb. Katalog i szczegoly przekazuja ocene oraz wyniki porownania zapisane przez agenta; starsze rekordy moga ich nie zawierac. Dopasowania i zapisywanie projektow ani potrzeb nie sa obslugiwane.

## Asystent AI

Opcjonalna analiza na karcie projektu wymaga ustawienia `OPENAI_API_KEY` w
srodowisku backendu oraz ponownego uruchomienia serwera. Opcjonalny
`OPENAI_MODEL` wybiera model (domyslnie `gpt-4o-mini`).
`POST /api/innovations/:id/analysis` przesyla tytul, opis i brakujace obszary do
OpenAI; korzystanie z API moze generowac koszty. Bez klucza lub w razie bledu
dostawcy zwracany jest HTTP 503. Odpowiedz AI wymaga weryfikacji i nie zmienia
oceny projektu. Endpoint nie ma uwierzytelniania ani limitu zapytan: przed
udostepnieniem backendu publicznie nalezy zabezpieczyc go i ograniczyc koszty.

## Wyszukiwanie

`GET /api/projects/search?q=szkola&keywords=technologie,edukacja` (dostepny rowniez pod `/projects/search`)

Wymagane jest co najmniej jedno slowo w `q` lub `keywords`. Wyszukiwanie ignoruje wielkosc liter i polskie znaki, dopasowuje fragmenty slow w tytule, opisie, faktach, dowodach i pozostalych kluczowych polach. Zwraca projekty z co najmniej jednym pasujacym slowem, uporzadkowane wedlug liczby dopasowanych slow; przy remisie pierwszenstwo maja dopasowania w `keywords` agenta. Odpowiedz to tablica obiektow `{ "project": ..., "matchedTerms": [...] }`. Jest to wyszukiwanie tekstowe, nie ocena projektu.

## Ocena

`POST /assessment` z naglowkiem `Content-Type: application/json` i trescia np. `{"parameters":{"budget":100}}`.

Ten niezalezny endpoint nadal zwraca `status: "criteria_not_configured"` i nie
oblicza oceny; ocena projektow jest tworzona przez agenta na podstawie zrodla.

Testy: `npm test`.
