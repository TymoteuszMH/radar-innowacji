'use strict';
(() => {
const RUBRIC = Object.freeze([
  { key: 'impact', label: 'Potencjalny wpływ', weight: 0.25, question: 'Czy rozwiązanie odpowiada na konkretny problem?' },
  { key: 'transfer', label: 'Możliwość transferu', weight: 0.25, question: 'Czy można zastosować je w innej organizacji?' },
  { key: 'readiness', label: 'Gotowość', weight: 0.20, question: 'Na jakim etapie rozwoju jest rozwiązanie?' },
  { key: 'evidence', label: 'Jakość dowodów', weight: 0.20, question: 'Jak dobrze potwierdzono deklarowane efekty?' },
  { key: 'distinctiveness', label: 'Odróżnienie od analogów', weight: 0.10, question: 'Czym rozwiązanie różni się od podobnych?' }
]);

const STAGE_GRADE = { concept: 1, prototype: 2, pilot: 2, implemented: 3 };
const QUESTIONS = {
  impact: 'Jakie są mierzalne korzyści i dla kogo?',
  transfer: 'Jakie warunki musi spełnić nowa organizacja?',
  readiness: 'Czy istnieje działający przykład lub pilotaż?',
  evidence: 'Czy przedstawiono pomiary lub niezależną ewaluację?',
  distinctiveness: 'Czym projekt różni się od opisanych analogów?'
};
const REASONS = {
  impact: 'Ocena oparta na opisie problemu i deklarowanych korzyściach; efekty nie zostały niezależnie zweryfikowane.',
  transfer: 'Ocena na podstawie opisanych wymagań przeniesienia; rzeczywiste koszty i bariery należy sprawdzić.',
  readiness: 'Ocena na podstawie etapu zadeklarowanego przez autora.',
  evidence: 'Ocena wyłącznie na podstawie informacji przekazanych w karcie; nie potwierdza wyników.',
  distinctiveness: 'Wstępna ocena demonstracyjna; nie stanowi badania stanu techniki.'
};

function calculateAssessment(innovation, overrideGrades = null) {
  const sourced = window.RadarEvidence ? window.RadarEvidence.summarize(innovation).records : [];
  const admittedNoEvidence = sourced.some(r=>r.field==='claimed_impact') && /nie zosta[łl].*potwierdz|brak (?:pomiar|danych|ewaluacj)|hipotez[aą]|nie (?:ma|przedstawiono) [^.]{0,70}(?:wynik|pomiar|ewaluacj|dowod|potwierdz)|bez (?:pomiar|potwierdz|niezależn|niezalezn|weryfikacj|ocen)/i.test(innovation.claimed_impact||'');
  const manual = overrideGrades ?? innovation.assessment_grades ?? {};
  const estimated = {
    impact: innovation.problem?.trim() && innovation.claimed_impact?.trim() ? 2 : null,
    transfer: innovation.requirements?.trim() && innovation.target_groups?.length ? 2 : null,
    readiness: STAGE_GRADE[innovation.stage] ?? null,
    evidence: admittedNoEvidence ? 0 : null,
    distinctiveness: null
  };
  const dimensions = RUBRIC.map((dimension) => {
    const declared = Object.prototype.hasOwnProperty.call(manual, dimension.key);
    const grade = declared ? manual[dimension.key] : estimated[dimension.key];
    if (grade !== null && grade !== undefined && (!Number.isInteger(grade) || grade < 0 || grade > 4)) {
      throw new RangeError(`Nieprawidłowa ocena dla ${dimension.key}`);
    }
    const lookup = {impact:['problem','claimed_impact'], transfer:['requirements','solution'], readiness:[], evidence:['claimed_impact'], distinctiveness:[]};
    const refs=sourced.filter(r=>lookup[dimension.key].includes(r.field));
    return {
      ...dimension,
      grade: grade ?? null,
      reason: grade == null ? 'Brak wystarczających informacji do oceny.' : (dimension.key==='evidence' && admittedNoEvidence && !declared ? 'W materiale podano brak potwierdzenia efektu. Ocena 0 oznacza brak dostarczonych dowodów, nie negatywny wynik badania.' : REASONS[dimension.key]),
      verification_status: refs.length ? 'source_mentioned_not_verified' : 'unverified',
      evidence_refs: refs,
      origin: declared ? 'deklaracja demonstracyjna' : 'reguła heurystyczna'
    };
  });
  const known = dimensions.filter((d) => d.grade !== null);
  const coverage = Number(known.reduce((sum, d) => sum + d.weight, 0).toFixed(4));
  const score = coverage >= 0.8
    ? Number((100 * known.reduce((sum, d) => sum + (d.weight * d.grade / 4), 0) / coverage).toFixed(2))
    : null;
  return {
    innovation_id: innovation.id,
    rubric_version: 'v1.1-offline',
    score,
    coverage,
    status: score === null ? 'insufficient_data' : 'provisional',
    dimensions,
    missing_questions: dimensions.filter((d) => d.grade === null).map((d) => QUESTIONS[d.key]),
    disclaimer: 'Ocena wstępna z reguł i deklaracji. Obecność cytatu nie potwierdza prawdziwości efektów; nie jest prognozą sukcesu ani oceną patentowalności.'
  };
}

window.RadarAssessment = Object.freeze({ RUBRIC, calculateAssessment });
})();
