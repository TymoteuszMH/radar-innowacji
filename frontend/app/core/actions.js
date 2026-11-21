'use strict';
(() => {
function nextSteps(innovation, assessment, matches = [], similar = []) {
  const tasks = [];
  if (assessment.score === null || assessment.dimensions.some((d) => d.key === 'evidence' && (d.grade ?? -1) <= 1)) {
    tasks.push({ title: 'Zbierz mierzalne dowody', reason: 'Weryfikacja efektu jest niepełna lub opiera się na deklaracji autora.', success_check: 'Zapisane wskaźniki bazowe i wynik małego pilotażu.', owner_type: 'twórca' });
  }
  if (similar.length) tasks.push({ title: 'Porównaj podobne rozwiązania', reason: 'Katalog zawiera potencjalnie podobne projekty.', success_check: 'Udokumentowane różnice i wspólne możliwości.', owner_type: 'koordynator' });
  if (innovation.stage==='concept') tasks.push({ title: 'Zweryfikuj wykonalność prototypu', reason: 'Opis wskazuje etap koncepcji; do transferu potrzebna jest praktyczna weryfikacja.', success_check: 'Opis prostego prototypu, harmonogram i kryteria testu.', owner_type:'twórca' });
  if (matches.some(m=>m.risks?.length)) tasks.push({title:'Sprawdź bariery dopasowania',reason:'Niektóre potrzeby wymagają innej gotowości lub szczególnych warunków.',success_check:'Spisana lista warunków i decyzja o możliwości małego pilotażu.',owner_type:'koordynator'});
  if (matches.length) tasks.push({ title: 'Przygotuj pilotaż z potencjalnym odbiorcą', reason: 'W katalogu demonstracyjnym wykryto podobne potrzeby.', success_check: 'Opis zakresu i kryteriów pilotażu bez deklarowania zgody partnera.', owner_type: 'koordynator' });
  tasks.push({ title: 'Sprawdź prawa i warunki transferu', reason: 'Autorstwo, dane i możliwość ponownego użycia wymagają odrębnej oceny.', success_check: 'Lista wymaganych zgód i warunków wdrożenia.', owner_type: 'ekspert' });
  return tasks;
}

window.RadarActions = Object.freeze({ nextSteps });
})();
