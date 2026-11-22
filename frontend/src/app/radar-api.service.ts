import { HttpClient, HttpErrorResponse, HttpParams } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { firstValueFrom, Subject } from 'rxjs';
import type { CatalogData } from './catalog.component';
import type { DetailView } from './detail.component';
import type { DraftState, Extracted } from './entry-form.component';
import type { DiscoveryReport, DiscoveryState, OnlineReport } from './discovery.component';

@Injectable({ providedIn: 'root' })
export class RadarApiService {
  private readonly base = '/api';
  private readonly refreshSubject = new Subject<void>();
  readonly refresh$ = this.refreshSubject.asObservable();

  constructor(private readonly http: HttpClient) {}

  catalog(kind: 'innovations' | 'needs', query = ''): Promise<CatalogData> {
    const params = query ? new HttpParams().set('q', query) : undefined;
    return firstValueFrom(this.http.get<CatalogData>(`${this.base}/${kind}`, { params }));
  }

  innovation(id: string): Promise<Omit<Extract<DetailView, { kind: 'innovation' }>, 'kind'>> {
    return firstValueFrom(this.http.get<Omit<Extract<DetailView, { kind: 'innovation' }>, 'kind'>>(`${this.base}/innovations/${encodeURIComponent(id)}`));
  }

  need(id: string): Promise<Omit<Extract<DetailView, { kind: 'need' }>, 'kind'>> {
    return firstValueFrom(this.http.get<Omit<Extract<DetailView, { kind: 'need' }>, 'kind'>>(`${this.base}/needs/${encodeURIComponent(id)}`));
  }

  saveInnovation(payload: Record<string, unknown>): Promise<{ innovation: { id: string } }> {
    return firstValueFrom(this.http.post<{ innovation: { id: string } }>(`${this.base}/innovations`, payload));
  }

  saveNeed(payload: Record<string, unknown>): Promise<{ need: { id: string } }> {
    return firstValueFrom(this.http.post<{ need: { id: string } }>(`${this.base}/needs`, payload));
  }

  extract(file: File | undefined, text: string): Promise<Extracted> {
    if (file) {
      const body = new FormData();
      body.append('file', file);
      return firstValueFrom(this.http.post<Extracted>(`${this.base}/innovations/extract`, body));
    }
    return firstValueFrom(this.http.post<Extracted>(`${this.base}/innovations/extract`, { text }));
  }

  analyze(files: File[], text: string): Promise<DiscoveryReport> {
    const body = new FormData();
    for (const file of files) body.append('files', file);
    if (text) body.append('text', text);
    return firstValueFrom(this.http.post<DiscoveryReport>(`${this.base}/discovery/analyze`, body));
  }

  online(query: string, source: string, limit: number): Promise<OnlineReport> {
    const params = new HttpParams().set('query', query).set('source', source).set('limit', limit);
    return firstValueFrom(this.http.get<OnlineReport>(`${this.base}/discovery/online`, { params }));
  }

  refresh(): void {
    this.refreshSubject.next();
  }
}

@Injectable({ providedIn: 'root' })
export class DraftService {
  readonly state: DiscoveryState & DraftState = {
    draft: {}, extracted: null, sourceMode: 'form', sourceEvidence: [], sourceName: '', sourceMeta: {}, isDemo: false,
    discovery: null, online: null, onlineQuery: 'edukacja', onlineSource: 'both', onlineLimit: 8,
  };
}

export function apiError(error: unknown): string {
  if (error instanceof HttpErrorResponse) {
    if (error.status === 0) return 'Nie można połączyć się z backendem.';
    if (error.status >= 200 && error.status < 300) return 'Backend zwrócił niepoprawny format odpowiedzi.';
    const body: unknown = error.error;
    if (typeof body === 'object' && body !== null && 'message' in body && typeof body.message === 'string') {
      return `Błąd backendu (${error.status}): ${body.message}`;
    }
    return `Błąd backendu (HTTP ${error.status}). Funkcja może nie być jeszcze obsługiwana przez API.`;
  }
  return error instanceof Error ? error.message : 'Operacja nie powiodła się.';
}
