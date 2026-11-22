import { HttpClient, HttpErrorResponse, HttpParams } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../environments/environment';
import type { CatalogData } from '../interfaces/catalog.interfaces';
import type { DetailView } from '../interfaces/detail.interfaces';
import type { ProjectSearchResult, SearchState } from '../interfaces/search.interfaces';

/** Adapter HTTP do endpointow JSON backendu. */
@Injectable({ providedIn: 'root' })
export class RadarApiService {
  private readonly base = `${environment.backendUrl}/api`;
  constructor(private readonly http: HttpClient) {}

  /** Pobiera katalog przez GET /api/innovations. */
  catalog(kind: 'innovations', query = ''): Promise<CatalogData> {
    const params = query ? new HttpParams().set('q', query) : undefined;
    return firstValueFrom(this.http.get<CatalogData>(`${this.base}/${kind}`, { params }));
  }

  /** Pobiera innowacje wraz z ocena, dowodami i podobnymi rekordami. */
  innovation(id: string): Promise<Omit<Extract<DetailView, { kind: 'innovation' }>, 'kind'>> {
    return firstValueFrom(
      this.http.get<Omit<Extract<DetailView, { kind: 'innovation' }>, 'kind'>>(
        `${this.base}/innovations/${encodeURIComponent(id)}`,
      ),
    );
  }

  /** Wyszukuje rekordy; matchedTerms to dopasowane slowa, a nie wynik trafnosci. */
  async searchProjects(query: string): Promise<ProjectSearchResult[]> {
    const params = new HttpParams().set('q', query);
    const results = await firstValueFrom(
      this.http.get<unknown>(`${this.base}/projects/search`, { params }),
    );
    if (results === null) return [];
    if (!Array.isArray(results)) throw new Error('Nie udało się pobrać wyników wyszukiwania.');
    return results.map((result: unknown) => {
      if (
        !result || typeof result !== 'object' || !('project' in result) ||
        !result.project || typeof result.project !== 'object' || Array.isArray(result.project) ||
        !('matchedTerms' in result) || !Array.isArray(result.matchedTerms)
      ) {
        throw new Error('Nie udało się odczytać wyników wyszukiwania.');
      }
      const project = result.project as Record<string, unknown>;
      const text = (value: unknown): string => typeof value === 'string' ? value : '';
      const strings = (value: unknown): string[] => Array.isArray(value)
        ? value.filter((item): item is string => typeof item === 'string')
        : [];
      const assessment = project['assessment'];
      const assessmentData = assessment && typeof assessment === 'object' && !Array.isArray(assessment)
        ? assessment as Record<string, unknown> : null;
      const number = (value: unknown): number | null =>
        typeof value === 'number' && Number.isFinite(value) ? value : null;
      return {
        project: {
          uuid: text(project['uuid']),
          project_title: text(project['project_title']),
          summary: text(project['summary']),
          source_title: text(project['source_title']),
          url: text(project['url']),
          contact_email: text(project['contact_email']) || text(project['contact']),
          tags: [...new Set([...strings(project['tags']), ...strings(project['domain_tags'])])],
          assessment: assessmentData ? {
            score: number(assessmentData['score']),
            coverage: number(assessmentData['coverage']),
            status: text(assessmentData['status']),
          } : null,
        },
        matchedTerms: strings(result.matchedTerms),
      };
    });
  }

}

/** Zachowuje zapytanie i wyniki podczas przechodzenia miedzy trasami. */
@Injectable({ providedIn: 'root' })
export class SearchStateService {
  readonly state: SearchState = {
    results: null,
    query: '',
  };
}

export function apiError(error: unknown): string {
  if (error instanceof HttpErrorResponse) {
    if (error.status === 0) return 'Nie można połączyć się z backendem.';
    if (error.status >= 200 && error.status < 300) return 'Nie udało się odczytać danych z backendu.';
    const body: unknown = error.error;
    if (typeof body === 'object' && body !== null && 'message' in body && typeof body.message === 'string') {
      return `Błąd backendu (${error.status}): ${body.message}`;
    }
    return `Błąd backendu (HTTP ${error.status}). Funkcja może nie być jeszcze obsługiwana przez API.`;
  }
  return error instanceof Error ? error.message : 'Operacja nie powiodła się.';
}
