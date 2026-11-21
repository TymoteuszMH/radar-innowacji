'use strict';
(() => {
const STOP = new Set('i oraz dla tego która które jest są przez przy do od w na nie ale jako pod nad więc czy oraz lub o po ze za się już tylko ich mają ma wśród taka takim potrzeba rozwiązanie system szkoła gmina organizacja można musi zgodnie przed dane forma czasu jeden jedna gdzie jak'.split(' '));
const PL = { ą:'a', ć:'c', ę:'e', ł:'l', ń:'n', ó:'o', ś:'s', ź:'z', ż:'z' };
const STAGES = { concept: 0, prototype: 1, pilot: 2, implemented: 3 };
function fold(str) { return String(str ?? '').toLowerCase().replace(/[ąćęłńóśźż]/g, (c) => PL[c] ?? c); }
function stem(token) { return token.length > 7 ? token.slice(0, 6) : token.length > 5 ? token.slice(0, 5) : token; }
function tokenize(value) {
  return new Set(fold(value).match(/[a-z0-9]+/g)?.filter((t) => t.length > 3 && !STOP.has(t)).map(stem) ?? []);
}
function intersection(a, b) { return [...a].filter((s) => b.has(s)); }
function similarity(a, b) {
  if (!a.size || !b.size) return 0;
  const common = intersection(a, b).length;
  return 0.45 * (common / (a.size + b.size - common)) + 0.55 * Math.min(1, common / Math.min(5, b.size));
}
function fractionShared(a = [], b = []) {
  if (!a.length || !b.length) return 0;
  const left = new Set(a.map(fold));
  const right = new Set(b.map(fold));
  return intersection(left, right).length / Math.max(1, Math.min(left.size, right.size));
}
function describeOverlap(a = [], b = []) {
  const lookup = new Set(b.map(fold));
  return a.filter((x) => lookup.has(fold(x)));
}
function wordsForInnovation(i) { return tokenize([i.problem, i.solution, ...(i.keywords ?? [])].join(' ')); }
function wordsForNeed(n) { return tokenize([n.problem, n.desired_outcome, ...(n.keywords ?? [])].join(' ')); }
function compareInnovationToNeed(innovation, need) {
  const domainOverlap = describeOverlap(innovation.domain_tags, need.domain_tags);
  const groupOverlap = describeOverlap(innovation.target_groups, need.target_groups);
  const sharedWords = intersection(wordsForInnovation(innovation), wordsForNeed(need));
  const rawSemantic = similarity(wordsForInnovation(innovation), wordsForNeed(need));
  // Semantics here are lexical, not embedding similarity; the model never claims otherwise.
  const semantic = Math.min(1, rawSemantic * 1.5);
  const domain = 0.7 * fractionShared(innovation.domain_tags, need.domain_tags) +
    0.3 * fractionShared(innovation.target_groups, need.target_groups);
  const constraints = innovation.requirements?.trim() && need.constraints?.trim() ? 0.65 : null;
  const readiness = innovation.stage && need.minimum_stage && STAGES[innovation.stage] !== undefined && STAGES[need.minimum_stage] !== undefined
    ? (STAGES[innovation.stage] >= STAGES[need.minimum_stage] ? 1 : 0.25)
    : null;
  const keywordOverlap = intersection(
    tokenize((innovation.keywords ?? []).join(' ')),
    tokenize((need.keywords ?? []).join(' '))
  ).length;
  const hasCuratedTerms = (innovation.keywords?.length ?? 0) > 0 && (need.keywords?.length ?? 0) > 0;
  const focusedRelevance = hasCuratedTerms
    ? keywordOverlap >= 2
    : sharedWords.length >= 3 && rawSemantic >= 0.15;
  const unsupported = !focusedRelevance || (semantic < 0.10 && domain < 0.20);
  const compatible = !(Array.isArray(need.blocked_types) && need.blocked_types.includes(innovation.innovation_type));
  const unknowns = ['Deklaracja zainteresowania organizacji nie została potwierdzona.'];
  if (constraints === null) unknowns.push('Warunki wdrożenia wymagają uzupełnienia.');
  else unknowns.push('Koszty i wymogi wdrożenia wymagają weryfikacji.');
  if (readiness === null) unknowns.push('Gotowość rozwiązania lub minimalne wymagania są nieznane.');
  if (readiness === 0.25) unknowns.push('Etap rozwoju jest niższy niż oczekiwany przez organizację.');
  const sufficient = constraints !== null && readiness !== null && compatible;
  const score = !unsupported && sufficient
    ? Math.round(100 * (0.45 * semantic + 0.25 * domain + 0.20 * constraints + 0.10 * readiness))
    : null;
  const risks = [];
  if(!compatible) risks.push('Rodzaj innowacji jest wykluczony przez potrzebę.');
  if(readiness===0.25) risks.push('Etap rozwiązania jest niższy od wymaganego.');
  if(constraints===null) risks.push('Brak danych o warunkach wdrożenia.');
  const reasons = [];
  if (domainOverlap.length) reasons.push(`Wspólne obszary: ${domainOverlap.join(', ')}.`);
  if (groupOverlap.length) reasons.push(`Podobna grupa odbiorców: ${groupOverlap.join(', ')}.`);
  if (sharedWords.length) reasons.push('Opis rozwiązania i potrzeby zawierają pokrewne zagadnienia.');
  if (reasons.length === 0) reasons.push('Brak mocnego uzasadnienia zgodności na podstawie dostępnych danych.');
  return {
    innovation_id: innovation.id,
    need_id: need.id,
    match_score: score,
    matched: !unsupported && compatible,
    needs_review: true,
    reasons,
    unknowns,
    shared_terms: sharedWords.slice(0, 5),
    matched_keywords: intersection(tokenize((innovation.keywords??[]).join(' ')),tokenize((need.keywords??[]).join(' '))).slice(0,8),
    matched_domains:domainOverlap,matched_groups:groupOverlap,risks,
    components: { lexical:semantic, domain, constraints, readiness },
    engine_version: 'lexical-explainable-v0.4',
    next_step: 'Zweryfikuj warunki wdrożenia i przeprowadź mały pilotaż.',
    provenance: 'Porównanie tekstu i tagów offline; brak potwierdzenia zainteresowania organizacji.'
  };
}
function getMatchesForInnovation(innovation, needs, limit = 5) {
  return needs.map((need) => ({ ...compareInnovationToNeed(innovation, need), need }))
    .filter((m) => m.matched)
    .sort((a, b) => (b.match_score ?? -1) - (a.match_score ?? -1))
    .slice(0, limit);
}
function getMatchesForNeed(need, innovations, limit = 5) {
  return innovations.map((innovation) => ({ ...compareInnovationToNeed(innovation, need), innovation }))
    .filter((m) => m.matched)
    .sort((a, b) => (b.match_score ?? -1) - (a.match_score ?? -1))
    .slice(0, limit);
}
function findSimilarInnovations(innovation, innovations, limit = 3) {
  return innovations.filter((i) => i.id !== innovation.id).map((candidate) => {
    const topics = describeOverlap(innovation.domain_tags, candidate.domain_tags);
    const groups = describeOverlap(innovation.target_groups, candidate.target_groups);
    const lex = similarity(wordsForInnovation(innovation), wordsForInnovation(candidate));
    const score = Math.round(100 * (0.65 * lex + 0.25 * fractionShared(innovation.domain_tags, candidate.domain_tags) + 0.1 * fractionShared(innovation.target_groups, candidate.target_groups)));
    return { innovation: candidate, similarity_score: score, reasons: [topics.length ? `Wspólne obszary: ${topics.join(', ')}.` : null, groups.length ? `Podobni odbiorcy: ${groups.join(', ')}.` : null].filter(Boolean), label: 'Możliwie podobny projekt — niepotwierdzony duplikat' };
  }).filter((r) => r.similarity_score >= 16).sort((a,b) => b.similarity_score-a.similarity_score).slice(0,limit);
}

window.RadarMatching = Object.freeze({ tokenize, compareInnovationToNeed, getMatchesForInnovation, getMatchesForNeed, findSimilarInnovations });
})();
