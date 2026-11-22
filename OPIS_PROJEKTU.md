# Radar Innowacji

## 1. Problem i cel

W Polsce powstają wartościowe rozwiązania technologiczne, edukacyjne i administracyjne, o których informacje są rozproszone między stronami uczelni, szkół, samorządów, instytucji i innymi źródłami. Potencjalny użytkownik lub ekspert musi samodzielnie odnaleźć materiały, sprawdzić ich wiarygodność i ocenić możliwość zastosowania rozwiązania w innym miejscu.

Radar Innowacji jest prototypem, który wspiera odkrywanie takich rozwiązań, porządkowanie informacji o nich i ich wstępną ocenę. Łączy automatyczne przeszukiwanie wybranych źródeł z katalogiem projektów i kartami zawierającymi informacje potrzebne do dalszej analizy. Ma pomóc skrócić drogę od znalezienia rozwiązania do decyzji o jego weryfikacji, rozwoju lub wdrożeniu.

Projekt powstał w odpowiedzi na wyzwanie Podkarpackiego Centrum Innowacji (PCI). Jest niezależnym prototypem konkursowym, a nie oficjalnym systemem PCI.

Zgodnie z FAQ radar koncentruje się na **odkrywaniu i analizie istniejących rozwiązań**, a nie na zgłaszaniu nowych pomysłów, crowdfundingu czy pozyskiwaniu finansowania. Podręcznik Oslo Manual 2018 wskazany w FAQ stanowi punkt odniesienia: innowacja powinna być nowym lub ulepszonym rozwiązaniem, istotnie różniącym się od wcześniejszych i udostępnionym użytkownikom albo wdrożonym w praktyce. Obecny prototyp wykrywa także kandydatów wymagających sprawdzenia — samo znalezienie projektu nie potwierdza jeszcze spełnienia tej definicji.

## 2. Dla kogo?

Z radaru mogą korzystać przedstawiciele instytucji publicznych, samorządów, szkół, uczelni i jednostek naukowych, a także przedsiębiorstwa, startupy, inwestorzy oraz indywidualni innowatorzy. Przykładowo pracownik samorządu może szukać rozwiązań przydatnych w administracji, a przedstawiciel uczelni — sprawdzać projekty związane z wybraną technologią.

Obecna wyszukiwarka pozwala znaleźć rekordy w katalogu na podstawie tekstu. Nie dopasowuje jeszcze wyników automatycznie do szczegółowych potrzeb konkretnych grup użytkowników.

## 3. Jak działa prototyp?

1. **Pozyskanie informacji.** Agent przeszukuje strony z przygotowanej listy publicznych źródeł. Domyślnie analizuje artykuły z rozpoznaną datą publikacji z ostatnich siedmiu dni; zakres można zmienić.
2. **Wykrywanie i porządkowanie.** Model klasyfikacyjny wskazuje artykuły mogące opisywać projekty, a reguły wyodrębniają dostępne informacje, m.in. nazwę, opis, instytucję, twórców, słowa kluczowe i fragmenty źródłowe. Nieznane dane mogą pozostać puste.
3. **Wstępna ocena i porównanie.** Agent przygotowuje heurystyczną ocenę potencjału i może wyszukiwać podobne publikacje, patenty lub projekty w wybranych źródłach zewnętrznych. Backend wskazuje również potencjalnie podobne rekordy z katalogu.
4. **Prezentacja i weryfikacja.** Backend udostępnia wyniki aplikacji internetowej. Użytkownik przegląda katalog, wyszukuje projekty, otwiera ich karty i sprawdza źródła, ocenę, podobieństwa oraz sugerowane następne kroki.

Agent jest uruchamiany osobno, a jego wynik jest zapisywany w pliku JSON, z którego korzysta backend. Automatyczny harmonogram cyklicznej aktualizacji oraz trwała historia zmian nie są obecnie zapewnione. Uruchomienie agenta może zastąpić poprzedni plik wynikowy.

### Lejek znajdowania projektów

System działa jak lejek: zaczyna od wielu adresów i stopniowo wybiera materiały, które mogą opisywać rozwiązania. Kolejne warstwy nie gwarantują poprawności — ograniczają liczbę materiałów wymagających uwagi.

1. **Wybór źródeł.** Punktem startowym jest lista witryn w `agent/data/sites.csv`. Crawler porusza się po ich stronach, linkach i mapach witryn, w ramach skonfigurowanego zakresu i limitów.
2. **Wybór artykułów.** Crawler klasyfikuje adresy m.in. jako artykuły, strony listujące i mapy witryn. Pobiera treść oraz metadane rozpoznanych artykułów; w razie potrzeby może skorzystać z renderowania JavaScript. Strony listujące pomagają dotrzeć do kolejnych materiałów, ale same nie są traktowane jako artykuły.
3. **Filtr aktualności.** Do analizy trafiają artykuły z rozpoznaną datą mieszczącą się w ustawionym przedziale — domyślnie z ostatnich siedmiu dni. Materiały starsze, z przyszłą lub nierozpoznaną datą są pomijane. Opcjonalny limit może dodatkowo ograniczyć liczbę artykułów.
4. **Rozpoznanie kandydatów.** `ProjectAgent` analizuje tytuł i treść za pomocą wytrenowanego polskiego modelu językowego. Dla nowych adresów kandydat przechodzi dalej, gdy wynik osiągnie próg oraz reguły znajdą w treści fragment wskazujący na rozwiązanie. Adresy z listy znanych projektów są osobną ścieżką i mogą przejść niezależnie od progu i znalezionego fragmentu. Wynik modelu dotyczy wykrycia projektu w artykule, nie jego wartości.
5. **Wyodrębnienie i ograniczenie duplikatów.** Reguły tworzą rekord z dostępnymi danymi, takimi jak nazwa, opis, instytucja, twórcy, cytaty i słowa kluczowe. Jeden artykuł może opisywać kilka projektów. W obrębie uruchomienia system pomija powtórzenia na podstawie nazwy i twórców lub, gdy ich brak, instytucji; bez tych danych duplikat może pozostać. Niektóre rozpoznane adresy są uzupełniane danymi z zestawienia referencyjnego.
6. **Ocena i kontekst.** Dla nowych rekordów powstaje heurystyczna ocena na podstawie dostępnych przesłanek; dla rozpoznanych wpisów referencyjnych mogą zostać wykorzystane zapisane w zestawieniu oceny. Opcjonalnie system szuka podobnych rekordów w źródłach zewnętrznych. To etap wzbogacania informacji, a nie potwierdzenie nowości czy odrzucanie projektu tylko ze względu na podobieństwo.
7. **Katalog i weryfikacja człowieka.** Wyniki trafiają do pliku odczytywanego przez backend i są prezentowane w aplikacji. Użytkownik może przejść od wyszukanego rekordu do źródła, sprawdzić ocenę i podobieństwa oraz zdecydować o dalszych krokach.

Lejek może zarówno pominąć wartościowy materiał, jak i przepuścić nietrafny kandydat. W szczególności filtr dat, ograniczona lista źródeł, błędy klasyfikacji lub niepełna treść wpływają na wynik. Liczba projektów nie musi maleć na każdym etapie: jeden artykuł może dać kilka rekordów. Człowiek musi sprawdzić fakty, rzeczywiste wdrożenie i zastosowanie rozwiązania.

## 4. Co już realizuje rozwiązanie?

### Odkrywanie i katalogowanie

- Automatycznie pobiera informacje z wybranych witryn i wyszukuje potencjalne projekty w artykułach.
- Porządkuje informacje dostępne w źródle oraz przypisuje słowa kluczowe i wybrane tagi dziedzinowe.
- Udostępnia katalog, wyszukiwanie tekstowe i szczegółową kartę projektu. Wyszukiwanie dotyczy zapisanych rekordów, a nie całego internetu.
- Pokazuje dostępne cytaty i odnośniki do źródeł, ułatwiając ręczną weryfikację.

Zakres źródeł jest ograniczony do skonfigurowanej listy; obecność projektu w katalogu nie oznacza potwierdzenia jego innowacyjności, aktualnego stanu wdrożenia ani przynależności do konkretnej kategorii z FAQ.

### Wstępna ocena potencjału

Agent ocenia dostępne informacje w trzech wymiarach:

| Kryterium | Waga |
| --- | ---: |
| Potencjał wdrożeniowy | 45% |
| Innowacyjność i unikalność | 35% |
| Wykonalność i dojrzałość | 20% |

Ocena wykorzystuje rozpoznane w tekście przesłanki. W zależności od dostępnych danych karta może zawierać oceny poszczególnych kryteriów, cytaty, wynik procentowy, brakujące informacje i rekomendację dalszych kroków. Wskaźnik pokrycia oznacza sumę wag ocenionych kryteriów, a nie statystyczne prawdopodobieństwo poprawności oceny. Gdy dowodów jest za mało, wynik może być niepewny lub niedostępny.

Jest to heurystyka wspierająca analizę, nie ekspertyza. Prawdopodobieństwo modelu wykrywającego projekt dotyczy klasyfikacji artykułu, a nie wartości innowacji czy szans jej wdrożenia. Model nie ma jeszcze niezależnej oceny skuteczności na dużym, ręcznie oznaczonym zbiorze rzeczywistych przypadków.

### Porównanie i dalsze kroki

Prototyp może porównywać projekty z metadanymi Crossref i katalogiem Interreg, a po konfiguracji odpowiednich dostępów również z EPO OPS i PBN. Dostępność poszczególnych źródeł może się różnić; nie wszystkie bazy wskazane w wytycznych i FAQ są obecnie przeszukiwane.

Podobieństwo jest wskazówką do sprawdzenia, nie dowodem duplikatu. Brak wyniku nie potwierdza nowości, a porównanie nie zastępuje badania patentowego ani eksperckiego. Karta proponuje następne kroki i warunki ich weryfikacji, ale system nie łączy obecnie projektów z konkretnymi odbiorcami, partnerami ani inwestorami.

### Opcjonalna analiza AI

Backend ma opcjonalny endpoint analizy wybranego rekordu przez OpenAI, uruchamiany po konfiguracji klucza. Przygotowuje pomocniczy tekst analityczny, nie zmienia zapisanej oceny projektu. Obecna karta projektu nie udostępnia tej funkcji jako przycisku w interfejsie. Korzystanie z usługi może wiązać się z kosztami oraz przekazaniem zewnętrznemu dostawcy tytułu, fragmentu opisu i pytań o brakujące informacje.

## 5. Kierunki dalszego rozwoju

Poniższe możliwości są propozycjami, a nie deklaracją funkcji już dostępnych.

### Dynamiczna ocena na podstawie tekstu

Można umożliwić użytkownikowi wklejenie opisu lub fragmentu istniejącego materiału źródłowego i uruchomienie na jego podstawie wstępnej oceny. Wynik mógłby być przeliczany po zmianie tekstu, z pokazaniem rozpoznanych przesłanek, braków, daty i źródła oraz informacji, które stwierdzenia wymagają potwierdzenia. Byłoby to narzędzie do analizy istniejących rozwiązań, a nie formularz zgłaszania nowych pomysłów. Obecne wyszukiwanie tekstowe nie wykonuje takiej oceny.

### Rozwój kryteriów oceny

Ocena może zostać rozszerzona zgodnie z FAQ o bardziej szczegółowe kryteria:

- **poziom wdrożenia** — od koncepcji i prototypu przez testy i pilotaż po stosowanie w praktyce, z zaznaczeniem, czy wdrożenie zostało potwierdzone;
- **dojrzałość technologiczna** — skala TRL 1–9 tam, gdzie ma zastosowanie, bez wymuszania jej dla każdego rozwiązania edukacyjnego lub administracyjnego;
- **nowość i ulepszenie** — porównanie z wcześniejszymi rozwiązaniami wraz z odnośnikami do dowodów;
- **potencjał zastosowania i skalowalność** — możliwość przeniesienia rozwiązania do innych organizacji lub branż, wymagane zasoby, koszty, bariery i warunki wdrożenia;
- **wiarygodność** — jakość i aktualność źródeł, dokumentacja, niezależne potwierdzenia oraz dowody rzeczywistego wykorzystania.

Warto ustalić definicje, wagi i zasady oceny z ekspertami oraz zapewnić możliwość oznaczenia braku danych zamiast domyślania się wyniku. Kryteria i ich wersje powinny być przejrzyste i powtarzalne, a fakty odróżniane od szacunków.

### Wymagania obliczeniowe i chmura

Wadą rozwiązania są zasoby potrzebne do przeszukiwania stron, uruchamiania modelu i jego treningu. Przy większej liczbie źródeł analiza może trwać dłużej i obciążać procesor, pamięć oraz sieć; renderowanie stron w przeglądarce dodatkowo zwiększa zapotrzebowanie. Dokładne wymagania i koszty nie zostały jeszcze zmierzone.

Obecnie ograniczamy obciążenie przez osobne uruchamianie agenta i zapisywanie wyników do katalogu: przeglądanie zapisanych rekordów nie wymaga ponownego analizowania stron dla każdego użytkownika. Można też ustawić m.in. limity odwiedzanych stron, analizowanych artykułów i równoległych zadań crawlera. Model korzysta z dostępnego GPU CUDA albo z CPU, co pozwala uruchomić go również bez zgodnej karty graficznej, choć czas pracy może być wtedy dłuższy.

W przyszłości agenta i zadania treningowe można uruchamiać w chmurze, dobierając moc obliczeniową, w tym GPU, do skali zadania oraz wykonując analizę w tle według harmonogramu. Pozwoliłoby to ograniczyć wymagania sprzętowe po stronie użytkownika, ale nie eliminuje kosztów ani potrzeby kontroli dostępu, ochrony danych i monitorowania. Wdrożenie chmurowe nie jest obecnie zapewnione.

### LLM i łatwiejsza analiza

Istniejący backendowy mechanizm analizy można połączyć z kartą projektu, np. poprzez przycisk wywołujący podsumowanie, listę pytań do weryfikacji i wskazanie brakujących danych. W dalszej kolejności model językowy mógłby pomagać analizować dłuższe dokumenty, porównywać opisy lub wyjaśniać wyniki w języku zrozumiałym dla różnych odbiorców.

Odpowiedzi powinny wskazywać wykorzystane źródła, oddzielać potwierdzone fakty od przypuszczeń i pozostawać pod kontrolą człowieka. Przed szerszym udostępnieniem potrzebne są m.in. kontrola dostępu, wspólne limity zapytań, zarządzanie kosztami oraz zasady dotyczące danych przesyłanych do dostawcy modelu.

### Rozwój filtrów wyszukiwania

Obecnie katalog oferuje wyszukiwanie tekstowe. W przyszłości można dodać łączone filtry, które pomogą różnym odbiorcom zawęzić wyniki według:

- obszaru i typu innowacji, np. technologicznej, edukacyjnej lub administracyjnej;
- rodzaju instytucji, lokalizacji oraz źródła informacji;
- etapu wdrożenia i poziomu dojrzałości, w tym TRL tam, gdzie ma zastosowanie;
- oceny potencjału, stopnia pokrycia kryteriów i dostępności potwierdzających źródeł;
- daty publikacji lub aktualizacji oraz potrzeb i zastosowań interesujących użytkownika.

Filtry wymagają wiarygodnych, ujednoliconych danych. Warto umożliwić uwzględnienie rekordów z brakującymi informacjami, aby nie pomijać ich bez wyraźnej decyzji użytkownika. Ocena i przypisane kategorie nadal wymagałyby weryfikacji.

### Wyszukiwanie wspierane przez RAG

W przyszłości można rozszerzyć wyszukiwarkę o RAG (Retrieval-Augmented Generation). System wyszukiwałby w katalogu projekty i fragmenty źródeł związane z pytaniem użytkownika, również pod względem znaczenia, a następnie przekazywał je modelowi językowemu do przygotowania odpowiedzi z odnośnikami do wykorzystanych materiałów. Pozwoliłoby to zadawać pytania opisujące potrzebę, a nie tylko szukać konkretnych słów. Wyszukiwanie semantyczne można połączyć z obecnym wyszukiwaniem tekstowym i planowanymi filtrami.

RAG nie jest obecnie zaimplementowany. Wymagałby aktualizowanego indeksu danych, kontroli dostępu i oceny trafności wyników. Odpowiedź powinna wskazywać źródła i informować o braku wystarczających danych; cytowanie nie gwarantuje jednak poprawności, dlatego wyniki nadal wymagają weryfikacji. Należy też uwzględnić koszty oraz zasady przekazywania danych dostawcy modelu.

### Aktualizacja, integracje i skalowanie systemu

- Rozszerzenie źródeł o kolejne polskie uczelnie, instytucje, programy i dostępne bazy wskazane w FAQ, z poszanowaniem zasad ich wykorzystania.
- Cykliczne uruchamianie pozyskiwania danych, kontrola błędów i aktualności, historia zmian oraz deduplikacja między uruchomieniami.
- Przejście z pliku JSON do bazy danych, aby wspierać większą liczbę rekordów, jednoczesnych użytkowników i organizacji.
- Integracja z systemami instytucji przez API oraz wprowadzenie bezpiecznego zarządzania dostępem, ochrony danych i monitorowania.
- Opcjonalna anonimowa analiza zainteresowań użytkowników, z uwzględnieniem RODO i odpowiednich zasad prywatności.

## 6. Walidacja i demonstracja

Prototyp można pokazać na co najmniej dwóch różnych rekordach z aktualnego katalogu: wyszukać projekt, otworzyć jego kartę, sprawdzić źródło i przesłanki oceny, porównać podobne rozwiązania oraz omówić następny krok. Należy zaznaczyć, których danych brakuje i co wymaga potwierdzenia przez człowieka.

W dalszym pilotażu warto mierzyć trafność i kompletność wykrywania na niezależnym zbiorze oznaczonym przez ekspertów, zgodność ocen ekspertów z ocenami systemu, trafność podobnych wyników oraz czas potrzebny na znalezienie i weryfikację rozwiązania. Są to proponowane mierniki — obecny prototyp nie przedstawia jeszcze ich niezależnie potwierdzonych wyników.
