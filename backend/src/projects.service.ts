import { Injectable, ServiceUnavailableException } from '@nestjs/common';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';

type Project = Record<string, unknown>;

const SEARCH_FIELDS = [
  'project_title', 'source_title', 'summary', 'facts', 'evidence',
  'project_type', 'stage', 'organization', 'people', 'domain',
];

function normalize(value: string): string {
  return value.toLocaleLowerCase('pl').normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '').replace(/ł/g, 'l');
}

function words(value: string): string[] {
  return normalize(value).match(/[\p{L}\p{N}]+/gu) ?? [];
}

@Injectable()
export class ProjectsService {
  async search(query: string, keywords: string[]): Promise<Array<{ project: Project; matchedTerms: string[] }>> {
    const terms = [...new Set(words([query, ...keywords].join(' ')))];
    const file = process.env.PROJECTS_FILE
      ? resolve(process.env.PROJECTS_FILE)
      : resolve(__dirname, '../../agent/results/projects.json');
    let projects: Project[];

    try {
      const data: unknown = JSON.parse(await readFile(file, 'utf8'));
      if (!data || typeof data !== 'object' || !('projects' in data) || !Array.isArray(data.projects)) {
        throw new Error('Invalid projects file');
      }
      projects = data.projects.filter((project: unknown): project is Project =>
        project !== null && typeof project === 'object' && !Array.isArray(project));
    } catch {
      throw new ServiceUnavailableException('Nie mozna odczytac danych projektow.');
    }

    return projects.map((project) => {
      const text = normalize(SEARCH_FIELDS.flatMap((field) => {
        const value = project[field];
        if (typeof value === 'string') return [value];
        return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
      }).join(' '));
      const matchedTerms = terms.filter((term) => text.includes(term));
      return { project, matchedTerms };
    }).filter((result) => result.matchedTerms.length > 0)
      .sort((left, right) => right.matchedTerms.length - left.matchedTerms.length);
  }
}