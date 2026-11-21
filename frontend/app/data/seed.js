'use strict';
const seed = {
  version: 1,
  organizations: [
    { id: 'org-school-a', name: 'Szkoła Demo A', type: 'school', region: 'podkarpackie', is_demo: true, verified: false },
    { id: 'org-school-b', name: 'Szkoła Demo B', type: 'school', region: 'podkarpackie', is_demo: true, verified: false },
    { id: 'org-school-c', name: 'Szkoła Demo C', type: 'school', region: 'lubelskie', is_demo: true, verified: false },
    { id: 'org-gmina-a', name: 'Gmina Demo A', type: 'municipality', region: 'podkarpackie', is_demo: true, verified: false },
    { id: 'org-gmina-b', name: 'Gmina Demo B', type: 'municipality', region: 'małopolskie', is_demo: true, verified: false },
    { id: 'org-university', name: 'Uczelnia Demo', type: 'university', region: 'podkarpackie', is_demo: true, verified: false },
    { id: 'org-center', name: 'Centrum Demo', type: 'public_other', region: 'mazowieckie', is_demo: true, verified: false }
  ],
  innovations: [
    {
      id: 'inn-adaptive', organization_id: 'org-school-a', title: 'Adaptacyjne powtórki materiału',
      problem: 'Uczniowie mają zaległości w nauce i trudno dobrać powtórki do ich indywidualnych potrzeb.',
      solution: 'Nauczyciel stosuje krótkie diagnozy i adaptacyjne powtórki materiału na podstawie potrzeb każdego ucznia.',
      domain_tags: ['edukacja', 'nauka'], target_groups: ['uczniowie', 'nauczyciele'], innovation_type: 'educational', stage: 'pilot',
      claimed_impact: 'Autorzy zakładają zmniejszenie zaległości; nie przedstawiono niezależnej ewaluacji.',
      requirements: 'Nauczyciel prowadzący, czas na diagnozę i zgoda szkoły na pilotaż.',
      keywords: ['zaległości', 'uczniowie', 'nauczanie', 'powtórki', 'edukacja'],
      assessment_grades: { impact: 3, transfer: 3, readiness: 2, evidence: 1, distinctiveness: 2 },
      is_demo: true, source_mode: 'form', review_status: 'reviewed'
    },
    {
      id: 'inn-mobile-lab', organization_id: 'org-school-c', title: 'Mobilne laboratorium szkolne',
      problem: 'Szkoły z małymi pracowniami mają ograniczony dostęp do praktycznych eksperymentów naukowych.',
      solution: 'Przenośne zestawy laboratoryjne i lekcje eksperymentalne współdzielone przez kilka szkół.',
      domain_tags: ['edukacja', 'nauka'], target_groups: ['uczniowie', 'nauczyciele'], innovation_type: 'educational', stage: 'prototype',
      claimed_impact: 'Potencjalne zwiększenie dostępu do doświadczeń STEM bez budowy nowej pracowni.',
      requirements: 'Transport zestawów, instrukcje bezpieczeństwa, harmonogram między szkołami.',
      keywords: ['laboratorium', 'eksperymenty', 'stem', 'szkoły', 'nauka'],
      assessment_grades: { impact: 2, transfer: 3, readiness: 2, evidence: 1, distinctiveness: null },
      is_demo: true, source_mode: 'form', review_status: 'reviewed'
    },
    {
      id: 'inn-waste-routes', organization_id: 'org-gmina-a', title: 'Inteligentne trasy odbioru odpadów',
      problem: 'Stałe trasy odbioru odpadów powodują niepotrzebne przejazdy pojazdów i koszty transportu.',
      solution: 'Planowanie tras odbioru odpadów na podstawie zgłoszeń z rejonów i danych o napełnieniu pojemników.',
      domain_tags: ['samorząd', 'środowisko', 'logistyka'], target_groups: ['mieszkańcy', 'samorządy'], innovation_type: 'process', stage: 'pilot',
      claimed_impact: 'Możliwość ograniczenia liczby przejazdów; brak zweryfikowanych wyników finansowych.',
      requirements: 'Dane o trasach i pojemnikach, współpraca operatora odbioru odpadów.',
      keywords: ['odpady', 'trasy', 'pojazdy', 'transport', 'pojemniki'],
      assessment_grades: { impact: 3, transfer: 3, readiness: 2, evidence: 1, distinctiveness: 2 },
      is_demo: true, source_mode: 'form', review_status: 'reviewed'
    },
    {
      id: 'inn-digital-queue', organization_id: 'org-gmina-b', title: 'Cyfrowa kolejka w urzędzie',
      problem: 'Mieszkańcy długo czekają na obsługę spraw urzędowych bez informacji o przewidywanym terminie.',
      solution: 'Prosty system umawiania wizyt i kolejkowania spraw z powiadomieniami dla mieszkańców.',
      domain_tags: ['samorząd', 'usługi publiczne', 'cyfryzacja'], target_groups: ['mieszkańcy', 'urzędnicy'], innovation_type: 'organizational', stage: 'prototype',
      claimed_impact: 'Deklarowana poprawa organizacji kolejek, bez pomiaru czasu obsługi.',
      requirements: 'Zgoda urzędu, dostęp do harmonogramów, zasady przetwarzania danych.',
      keywords: ['kolejka', 'urząd', 'wizyty', 'obsługa', 'mieszkańcy'],
      assessment_grades: { impact: 2, transfer: 3, readiness: 2, evidence: null, distinctiveness: 1 },
      is_demo: true, source_mode: 'form', review_status: 'reviewed'
    },
    {
      id: 'inn-air-quality', organization_id: 'org-university', title: 'Szkolna sieć czujników jakości powietrza',
      problem: 'Szkoły nie mają lokalnych danych o jakości powietrza przy budynkach.',
      solution: 'Niskokosztowe czujniki i panel pomiarów pyłów dla otoczenia szkoły oraz lekcji ekologii.',
      domain_tags: ['środowisko', 'edukacja', 'iot'], target_groups: ['szkoły', 'uczniowie', 'mieszkańcy'], innovation_type: 'technical', stage: 'prototype',
      claimed_impact: 'Możliwość lepszego informowania o warunkach, bez potwierdzonego efektu zdrowotnego.',
      requirements: 'Zasilanie, kalibracja czujników i interpretacja jakości pomiarów.',
      keywords: ['powietrze', 'czujniki', 'pyły', 'szkoły', 'środowisko'],
      assessment_grades: { impact: 2, transfer: 2, readiness: 2, evidence: 1, distinctiveness: null },
      is_demo: true, source_mode: 'form', review_status: 'reviewed'
    },
    {
      id: 'inn-energy', organization_id: 'org-university', title: 'Monitor energii budynków publicznych',
      problem: 'Placówki publiczne nie widzą, kiedy i gdzie powstają nadmierne zużycia energii.',
      solution: 'Tablica zużycia energii w budynkach z prostym wykrywaniem odchyleń i raportem dla zarządcy.',
      domain_tags: ['energia', 'samorząd', 'środowisko'], target_groups: ['samorządy', 'zarządcy'], innovation_type: 'technical', stage: 'pilot',
      claimed_impact: 'Potencjalna oszczędność energii nie została jeszcze potwierdzona pomiarem.',
      requirements: 'Dostęp do liczników i zgoda zarządcy budynku.',
      keywords: ['energia', 'budynki', 'liczniki', 'zużycie', 'oszczędność'],
      assessment_grades: { impact: 3, transfer: 3, readiness: 2, evidence: 1, distinctiveness: 2 },
      is_demo: true, source_mode: 'form', review_status: 'reviewed'
    },
    {
      id: 'inn-volunteers', organization_id: 'org-center', title: 'Lokalna sieć pomocy sąsiedzkiej',
      problem: 'Osoby starsze mają trudność w otrzymaniu drobnej pomocy od wolontariuszy.',
      solution: 'Koordynacja dyżurów wolontariuszy przez bibliotekę lub centrum aktywności lokalnej.',
      domain_tags: ['społeczeństwo', 'pomoc'], target_groups: ['seniorzy', 'wolontariusze'], innovation_type: 'social', stage: 'implemented',
      claimed_impact: 'Model działania opisany przez organizatorów, bez niezależnych wskaźników.',
      requirements: 'Koordynator i zgody uczestników; bezpieczeństwo kontaktów.',
      keywords: ['seniorzy', 'pomoc', 'wolontariusze', 'sąsiedzi'],
      assessment_grades: { impact: 2, transfer: 2, readiness: 3, evidence: 1, distinctiveness: null },
      is_demo: true, source_mode: 'form', review_status: 'reviewed'
    },
    {
      id: 'inn-procurement', organization_id: 'org-gmina-b', title: 'Jednolity formularz zakupów publicznych',
      problem: 'Pracownicy urzędu wielokrotnie uzupełniają te same dane w dokumentach zamówień.',
      solution: 'Ujednolicony formularz wniosków i baza powtarzalnych pól administracyjnych.',
      domain_tags: ['samorząd', 'administracja'], target_groups: ['urzędnicy'], innovation_type: 'process', stage: 'implemented',
      claimed_impact: 'Hipoteza oszczędności czasu pracowników bez porównania przed i po.',
      requirements: 'Uzgodnienie procedur w urzędzie; weryfikacja zgodności prawnej.',
      keywords: ['formularz', 'zakupy', 'urząd', 'dokumenty', 'administracja'],
      assessment_grades: { impact: 2, transfer: 3, readiness: 3, evidence: 1, distinctiveness: 1 },
      is_demo: true, source_mode: 'form', review_status: 'reviewed'
    },
    {
      id: 'inn-history', organization_id: 'org-center', title: 'Cyfrowa mapa lokalnego dziedzictwa',
      problem: 'Materiały o lokalnej historii są rozproszone i mało dostępne dla uczniów oraz mieszkańców.',
      solution: 'Mapa ze zdjęciami archiwalnymi i opisami miejsc przygotowywana przez uczniów i bibliotekarzy.',
      domain_tags: ['kultura', 'edukacja'], target_groups: ['uczniowie', 'mieszkańcy'], innovation_type: 'social', stage: 'prototype',
      claimed_impact: 'Możliwy wzrost udziału mieszkańców w projektach kultury; brak pomiaru.',
      requirements: 'Prawa do zdjęć i zgody autorów opisów.',
      keywords: ['historia', 'mapa', 'kultura', 'zdjęcia', 'dziedzictwo'],
      assessment_grades: { impact: 2, transfer: 3, readiness: 2, evidence: null, distinctiveness: null },
      is_demo: true, source_mode: 'form', review_status: 'reviewed'
    },
    {
      id: 'inn-health', organization_id: 'org-school-c', title: 'Warsztaty higieny cyfrowej',
      problem: 'Uczniowie nie znają sposobów ograniczania rozproszeń podczas nauki z urządzeniami.',
      solution: 'Warsztaty planowania czasu ekranowego i refleksji nad nawykami cyfrowymi bez zbierania danych o zdrowiu.',
      domain_tags: ['edukacja', 'społeczeństwo'], target_groups: ['uczniowie', 'nauczyciele'], innovation_type: 'educational', stage: 'concept',
      claimed_impact: 'Zakładana poprawa koncentracji wymaga przyszłej weryfikacji.',
      requirements: 'Przeszkolenie prowadzącego, materiały dydaktyczne.',
      keywords: ['uczniowie', 'czas', 'ekran', 'warsztaty', 'edukacja'],
      assessment_grades: { impact: 2, transfer: 3, readiness: 1, evidence: null, distinctiveness: null },
      is_demo: true, source_mode: 'form', review_status: 'reviewed'
    }
  ],
  needs: [
    { id: 'need-learning', organization_id: 'org-school-b', title: 'Ograniczenie zaległości w nauce', problem: 'Uczniowie mają zaległości w nauce i potrzebują dopasowanych powtórek materiału.', context: 'Szkoła podstawowa; mały pilotaż w jednej klasie.', domain_tags: ['edukacja', 'nauka'], target_groups: ['uczniowie', 'nauczyciele'], constraints: 'Pilotaż bez wymiany danych osobowych.', desired_outcome: 'Lepsze wyniki nauczania i mniej zaległości uczniów.', minimum_stage: 'concept', keywords: ['zaległości', 'nauka', 'powtórki', 'uczniowie'], is_demo: true, verified: false },
    { id: 'need-waste', organization_id: 'org-gmina-b', title: 'Ograniczenie kosztów odbioru odpadów', problem: 'Samorząd chce usprawnić trasy odbioru odpadów i ograniczyć zbędne przejazdy pojazdów.', context: 'Obszar kilku osiedli; lokalne dane do pilotażu wymagają zgody operatora.', domain_tags: ['samorząd', 'środowisko', 'logistyka'], target_groups: ['mieszkańcy', 'samorządy'], constraints: 'Dane o pojemnikach oraz trasy wymagają potwierdzenia.', desired_outcome: 'Mniej przejazdów i lepszy harmonogram odbioru odpadów.', minimum_stage: 'prototype', keywords: ['odpady', 'trasy', 'transport', 'pojazdy'], is_demo: true, verified: false },
    { id: 'need-air', organization_id: 'org-school-b', title: 'Lokalny pomiar jakości powietrza', problem: 'Szkoła chce znać poziom pyłów i jakość powietrza w pobliżu budynku.', context: 'Zajęcia przyrodnicze i informowanie szkolnej społeczności.', domain_tags: ['edukacja', 'środowisko', 'iot'], target_groups: ['szkoły', 'uczniowie'], constraints: 'Wymagana kalibracja czujników przed wyciąganiem wniosków.', desired_outcome: 'Czytelne pomiary jakości powietrza.', minimum_stage: 'prototype', keywords: ['powietrze', 'czujniki', 'pyły', 'szkoły'], is_demo: true, verified: false },
    { id: 'need-energy', organization_id: 'org-gmina-a', title: 'Kontrola zużycia energii w szkołach', problem: 'Gmina chce ograniczyć zużycie energii w budynkach publicznych przez analizę liczników.', context: 'Kilka budynków szkolnych; analiza po uzyskaniu dostępu do odczytów.', domain_tags: ['samorząd', 'środowisko', 'energia'], target_groups: ['samorządy', 'zarządcy'], constraints: 'Odczyty liczników i zgoda zarządcy są wymagane.', desired_outcome: 'Wskazanie godzin i obszarów nadmiernego zużycia energii.', minimum_stage: 'prototype', keywords: ['energia', 'budynki', 'liczniki', 'zużycie'], is_demo: true, verified: false },
    { id: 'need-services', organization_id: 'org-gmina-a', title: 'Mniej kolejek do urzędu', problem: 'Mieszkańcy potrzebują przewidywalnego terminu wizyt w urzędzie bez długich kolejek.', context: 'Punkt obsługi mieszkańców z podstawowym systemem rezerwacji.', domain_tags: ['samorząd', 'usługi publiczne', 'cyfryzacja'], target_groups: ['mieszkańcy', 'urzędnicy'], constraints: 'Nie wolno publikować informacji o sprawach mieszkańców.', desired_outcome: 'Krótsza kolejka i sprawniejsza obsługa wizyt.', minimum_stage: 'prototype', keywords: ['kolejka', 'urząd', 'wizyty', 'obsługa'], is_demo: true, verified: false },
    { id: 'need-stem', organization_id: 'org-school-b', title: 'Eksperymenty STEM bez stałej pracowni', problem: 'Uczniowie potrzebują dostępu do eksperymentów naukowych i laboratorium w małej szkole.', context: 'Zajęcia w szkole bez pełnego laboratorium.', domain_tags: ['edukacja', 'nauka'], target_groups: ['uczniowie', 'nauczyciele'], constraints: 'Zestawy muszą spełniać szkolne zasady bezpieczeństwa.', desired_outcome: 'Praktyczne zajęcia i eksperymenty naukowe.', minimum_stage: 'prototype', keywords: ['laboratorium', 'eksperymenty', 'stem', 'szkoły'], is_demo: true, verified: false }
  ]
};

window.RadarSeed = seed;
