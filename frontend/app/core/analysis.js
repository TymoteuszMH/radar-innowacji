'use strict';
(() => {
const FIELD_PATTERNS = {
  title: /(?:tytuł|nazwa projektu|title)\s*[:–-]\s*(.+)/i,
  problem: /(?:problem|wyzwanie)\s*[:–-]\s*(.+)/i,
  solution: /(?:rozwiązanie|proponowane rozwiązanie|opis pomysłu)\s*[:–-]\s*(.+)/i,
  claimed_impact: /(?:efekt|rezultat|wpływ)\s*[:–-]\s*(.+)/i,
  requirements: /(?:wymagania|warunki wdrożenia)\s*[:–-]\s*(.+)/i
};
function previewExtract(text, filename = '') {
  const normalized = String(text ?? '').replace(/\r/g, '').trim();
  const lines = normalized.split('\n').map((line) => line.trim()).filter(Boolean);
  const fields = {};
  const traces = {};
  for (const [key, pattern] of Object.entries(FIELD_PATTERNS)) {
    const match = lines.find((line) => pattern.test(line))?.match(pattern);
    if (match) { fields[key] = match[1].slice(0, 1200); traces[key] = 'Fragment przesłanego dokumentu'; }
  }
  if (!fields.title) {
    fields.title = lines.find((line) => line.length > 5 && line.length < 130)?.slice(0, 110) ?? filename.replace(/\.pdf$/i, '') ?? '';
    traces.title = 'Pierwsza linia tekstu — wymaga sprawdzenia';
  }
  // Avoid pretending arbitrary prose is a verified problem statement.
  if (!fields.problem && normalized.length > 40) {
    fields.problem = normalized.slice(0, 650);
    traces.problem = 'Fragment początkowy — ręcznie zweryfikuj';
  }
  return {
    fields,
    traces,
    source: filename ? 'uploaded_pdf' : 'plain_text',
    method: 'deterministic_fallback',
    warnings: [
      'Tryb offline: ekstrakcja oparta na nagłówkach i strukturze tekstu. Nie użyto modelu AI.',
      'Wszystkie rozpoznane pola trzeba zweryfikować przed zapisaniem.',
      ...(normalized.length < 40 ? ['Za mało tekstu do ekstrakcji; użyj formularza ręcznego.'] : [])
    ],
    extracted_characters: normalized.length
  };
}

window.RadarAnalysis = Object.freeze({ previewExtract });
})();
