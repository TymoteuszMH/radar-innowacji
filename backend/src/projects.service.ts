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
    problem: '',
    solution: text(project.summary),
    is_demo: false,
    stage: text(project.stage),
    domain_tags: Array.isArray(project.domain_tags) ? project.domain_tags.filter((value): value is string => typeof value === 'string') : [],
    tags: Array.isArray(project.tags) ? project.tags.filter((value): value is string => typeof value === 'string') : [],
    keywords: Array.isArray(project.keywords) ? project.keywords.filter((value): value is string => typeof value === 'string') : [],
    target_groups: [],
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

@Injectable()
export class ProjectsService {
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

  async search(query: string, keywords: string[]): Promise<Array<{ project: Project; matchedTerms: string[] }>> {
    const terms = [...new Set(words([query, ...keywords].join(' ')))];
    if (terms.length === 0) return [];
    return rankProjects(await this.readProjects(), terms)
      .map(({ project, matchedTerms }) => ({ project, matchedTerms }));
  }

  async catalog(query: string) {
    const terms = [...new Set(words(query))];
    const projects = rankProjects(await this.readProjects(), terms).map(({ project }) => project);
    const unique = new Map(projects.map((project) => [text(project.uuid) || identifier(JSON.stringify(project)), project]));
    const records = [...unique.values()];
    return { items: records.map(innovation), organizations: organizations(records), total: records.length };
  }

  async detail(id: string) {
    const projects = await this.readProjects();
    const project = projects.find((item) => (text(item.uuid) || identifier(JSON.stringify(item))) === id);
    if (!project) throw new NotFoundException('Nie znaleziono innowacji.');
    const evidence = Array.isArray(project.evidence)
      ? project.evidence.filter((value): value is string => typeof value === 'string')
      : [];
    return {
      innovation: innovation(project),
      organizations: organizations([project]),
      assessment: project.assessment ?? {
        score: null, coverage: 0, status: 'unavailable',
        disclaimer: 'Brak danych do oceny potencjału.', missing_questions: [], dimensions: [],
      },
      similar: [], matches: [], actions: [],
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