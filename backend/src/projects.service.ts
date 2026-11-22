import { Injectable, NotFoundException, ServiceUnavailableException } from '@nestjs/common';
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';

type Project = Record<string, unknown>;

const SEARCH_FIELDS = [
  'uuid', 'title', 'tags', 'authors', 'flags',
  'project_title', 'source_title', 'summary', 'facts', 'evidence',
  'project_type', 'stage', 'organization', 'people', 'domain', 'domain_tags', 'keywords',
];

function normalize(value: string): string {
  return value.toLocaleLowerCase('pl').normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '').replace(/ł/g, 'l');
}

function words(value: string): string[] {
  return normalize(value).match(/[\p{L}\p{N}]+/gu) ?? [];
}

function identifier(value: string): string {
  return createHash('sha256').update(value).digest('hex');
}

function text(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function searchableText(project: Project): string {
  return normalize(SEARCH_FIELDS.flatMap((field) => {
    const value = project[field];
    if (typeof value === 'string') return [value];
    if (!Array.isArray(value)) return [];
    if (field === 'people') {
      return value.flatMap((person: unknown) => {
        if (typeof person === 'string') return [person];
        if (person && typeof person === 'object' && 'name' in person && typeof person.name === 'string') {
          return [person.name];
        }
        return [];
      });
    }
    return value.filter((item): item is string => typeof item === 'string');
  }).join(' '));
}

function rankProjects(projects: Project[], terms: string[]) {
  return projects.map((project) => {
    const searchable = searchableText(project);
    const keywords = Array.isArray(project.keywords)
      ? project.keywords.filter((value): value is string => typeof value === 'string').map(normalize)
      : [];
    const matchedTerms = terms.filter((term) => searchable.includes(term));
    const keywordMatches = terms.filter((term) => keywords.some((keyword) => keyword.includes(term))).length;
    return { project, matchedTerms, keywordMatches };
  }).filter((result) => terms.length === 0 || result.matchedTerms.length > 0)
    .sort((left, right) => right.matchedTerms.length - left.matchedTerms.length || right.keywordMatches - left.keywordMatches);
}

function innovation(project: Project) {
  const organization = text(project.organization);
  return {
    id: text(project.uuid) || identifier(JSON.stringify(project)),
    uuid: text(project.uuid) || '',
    organization_id: organization ? identifier(organization) : '',
    title: text(project.project_title) || text(project.source_title) || 'Projekt bez tytułu',
    problem: text(project.problem),
    solution: text(project.summary),
    is_demo: false,
    stage: text(project.stage),
    domain_tags: Array.isArray(project.domain_tags) ? project.domain_tags.filter((value): value is string => typeof value === 'string') : [],
    tags: Array.isArray(project.tags) ? project.tags.filter((value): value is string => typeof value === 'string') : [],
    keywords: Array.isArray(project.keywords) ? project.keywords.filter((value): value is string => typeof value === 'string') : [],
    target_groups: stringValues(project, ['target_groups']),
    claimed_impact: text(project.claimed_impact),
    requirements: text(project.requirements),
    source_mode: 'online',
    source_url: text(project.url),
    source_provider: text(project.source_title) || text(project.domain),
    prior_art: project.prior_art ?? null,
    assessment: project.assessment ?? null,
    people: Array.isArray(project.people) ? project.people : [],
    authors: Array.isArray(project.authors) ? project.authors : [],
    flags: project.flags && typeof project.flags === 'object' ? project.flags : {},
    contact_email: text(project.contact_email),
  };
}

function organizations(projects: Project[]) {
  const names = new Set(projects.map((project) => text(project.organization)).filter(Boolean));
  return [...names].map((name) => ({ id: identifier(name), name }));
}

function stringValues(project: Project, fields: string[]): string[] {
  return fields.flatMap((field) => {
    const value = project[field];
    if (typeof value === 'string') return value ? [value] : [];
    return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
  });
}

function overlap(left: Set<string>, right: Set<string>): string[] {
  return [...left].filter((value) => right.has(value));
}

function similarity(left: Project, right: Project) {
  const leftDomains = new Set(stringValues(left, ['domain_tags', 'tags', 'innovation_type']).map(normalize));
  const rightDomains = new Set(stringValues(right, ['domain_tags', 'tags', 'innovation_type']).map(normalize));
  const sharedDomains = overlap(leftDomains, rightDomains);
  const leftKeywords = new Set(stringValues(left, ['keywords']).map(normalize));
  const rightKeywords = new Set(stringValues(right, ['keywords']).map(normalize));
  const sharedKeywords = overlap(leftKeywords, rightKeywords);
  const titleTerms = overlap(
    new Set(words(text(left.project_title) || text(left.source_title)).filter((word) => word.length > 3)),
    new Set(words(text(right.project_title) || text(right.source_title)).filter((word) => word.length > 3)),
  );

  if (!sharedDomains.length && !sharedKeywords.length && titleTerms.length < 2) return null;

  const domainScore = sharedDomains.length / Math.max(1, new Set([...leftDomains, ...rightDomains]).size);
  const keywordScore = sharedKeywords.length / Math.max(1, new Set([...leftKeywords, ...rightKeywords]).size);
  const titleScore = titleTerms.length / Math.max(1, new Set([
    ...words(text(left.project_title) || text(left.source_title)).filter((word) => word.length > 3),
    ...words(text(right.project_title) || text(right.source_title)).filter((word) => word.length > 3),
  ]).size);
  const reasons = [
    ...sharedDomains.map((value) => `Wspólny obszar: ${value}`),
    ...sharedKeywords.slice(0, 3).map((value) => `Wspólne słowo kluczowe: ${value}`),
    ...(titleTerms.length ? [`Wspólne terminy w tytułach: ${titleTerms.slice(0, 3).join(', ')}`] : []),
  ];
  return { score: Math.round((domainScore * 0.5 + keywordScore * 0.35 + titleScore * 0.15) * 100), reasons };
}

/** Buduje propozycje dalszych krokow na podstawie brakow i statusu oceny. */
function nextActions(project: Project): Array<{ title: string; reason: string; success_check: string }> {
  const assessment = project.assessment && typeof project.assessment === 'object'
    ? project.assessment as Record<string, unknown> : {};
  const missing = Array.isArray(assessment.missing_questions)
    ? assessment.missing_questions.filter((value): value is string => typeof value === 'string') : [];
  const actions = missing.slice(0, 3).map((question) => ({
    title: `Uzupełnij: ${question}`,
    reason: 'Brakuje informacji potrzebnej do rzetelnej oceny potencjału.',
    success_check: `W opisie lub źródle znajduje się potwierdzona odpowiedź na pytanie: ${question}`,
  }));

  actions.push({
    title: 'Zweryfikuj informacje u źródła',
    reason: 'Rekord powstał na podstawie publicznego materiału i może zawierać niepełne lub błędnie przypisane dane.',
    success_check: 'Twórca lub instytucja potwierdza opis rozwiązania, etap prac i możliwość kontaktu.',
  });
  if (text(assessment.status) === 'high' || text(assessment.status) === 'development') {
    actions.push({
      title: 'Sprawdź możliwość pilotażu',
      reason: 'Po potwierdzeniu informacji warto sprawdzić rozwiązanie w środowisku potencjalnego użytkownika.',
      success_check: 'Wskazano użytkownika pilotażowego, zakres testu i mierzalny rezultat.',
    });
  }
  return actions;
}

/** Czyta katalog JSON agenta i mapuje go na kontrakt API frontendu. */
@Injectable()
export class ProjectsService {
  /** Odczytuje plik dla kazdego zadania, aby nowe wyniki agenta byly widoczne bez restartu. */
  private async readProjects(): Promise<Project[]> {
    const file = process.env.PROJECTS_FILE
      ? resolve(process.env.PROJECTS_FILE)
      : resolve(__dirname, '../../agent/results/projects.json');
    try {
      const data: unknown = JSON.parse(await readFile(file, 'utf8'));
      if (!data || typeof data !== 'object' || !('projects' in data) || !Array.isArray(data.projects)) {
        throw new Error('Invalid projects file');
      }
      return data.projects.filter((project: unknown): project is Project =>
        project !== null && typeof project === 'object' && !Array.isArray(project));
    } catch {
      throw new ServiceUnavailableException('Nie mozna odczytac danych projektow.');
    }

  }

  /** Wyszukuje pola projektu i slowa kluczowe po normalizacji tekstu. */
  async search(query: string, keywords: string[]): Promise<Array<{ project: Project; matchedTerms: string[] }>> {
    const terms = [...new Set(words([query, ...keywords].join(' ')))];
    if (terms.length === 0) return [];
    return rankProjects(await this.readProjects(), terms)
      .map(({ project, matchedTerms }) => ({ project, matchedTerms }));
  }

  /** Zwraca unikalne rekordy katalogu i reprezentowane w nich organizacje. */
  async catalog(query: string) {
    const terms = [...new Set(words(query))];
    const projects = rankProjects(await this.readProjects(), terms).map(({ project }) => project);
    const unique = new Map(projects.map((project) => [text(project.uuid) || identifier(JSON.stringify(project)), project]));
    const records = [...unique.values()];
    return { items: records.map(innovation), organizations: organizations(records), total: records.length };
  }

  /** Mapuje rekord zrodla i oblicza heurystycznych kandydatow na podobne projekty. */
  async detail(id: string) {
    const projects = await this.readProjects();
    const project = projects.find((item) => (text(item.uuid) || identifier(JSON.stringify(item))) === id);
    if (!project) throw new NotFoundException('Nie znaleziono innowacji.');
    const similar = projects.flatMap((candidate) => {
      if (candidate === project) return [];
      const result = similarity(project, candidate);
      return result ? [{ innovation: innovation(candidate), similarity_score: result.score, reasons: result.reasons }] : [];
    }).sort((left, right) => right.similarity_score - left.similarity_score).slice(0, 5);
    const evidence = Array.isArray(project.evidence)
      ? project.evidence.filter((value): value is string => typeof value === 'string')
      : [];
    return {
      innovation: innovation(project),
      organizations: organizations(projects),
      assessment: project.assessment ?? {
        score: null, coverage: 0, status: 'unavailable',
        disclaimer: 'Brak danych do oceny potencjału.', missing_questions: [], dimensions: [],
      },
      similar,
      matches: [],
      actions: nextActions(project),
      evidence: {
        records: evidence.map((quote) => ({
          field: 'Opis', source_name: text(project.source_title) || text(project.domain) || 'Źródło',
          quote, source_url: text(project.url),
        })),
        disclaimer: 'Fragmenty pochodzą ze źródła i wymagają weryfikacji.',
      },
    };
  }
}