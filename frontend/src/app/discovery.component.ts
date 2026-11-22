import { ChangeDetectorRef, Component, DestroyRef, Input } from '@angular/core';
import { Router } from '@angular/router';
import { DraftState } from './entry-form.component';
import { RadarApiService, apiError } from './radar-api.service';

interface CandidateFields {
  title: string;
  problem: string;
  solution: string;
  is_demo: boolean;
  domain_tags: string[];
  keywords: string[];
  source_url?: string;
  source_provider?: string;
  source_identifier?: string;
  source_published_at?: string;
  source_retrieved_at?: string;
}
interface Evidence { field: string; source_name: string; line_number?: number; quote: string; source_url?: string; }
interface Candidate {
  fields: CandidateFields;
  source_name: string;
  evidence: Evidence[];
  warnings: string[];
  assessment: {
    score: number | null; coverage: number; disclaimer: string;
    dimensions: { label: string; grade: number | null; reason: string }[];
  };
  matches: { need: { title: string }; match_score: number | null; reasons: string[]; matched_keywords?: string[]; risks?: string[] }[];
  similar: unknown[];
  actions: { title: string; success_check: string }[];
}
interface OnlineCandidate extends Candidate {
  record: { url: string; source_label: string; source_type: string; record_type: string; published_at: string; title: string;
    organization_name: string; problem: string; description: string; notice: string };
}
export interface DiscoveryReport {
  candidates: Candidate[]; warnings: string[]; documents_count: number; method: string; disclaimer: string;
}
export interface OnlineReport {
  query: string; candidates: OnlineCandidate[]; duplicates_count: number; disclaimer: string;
  sources: { name: string; count: number; live: boolean }[];
  errors: { source_id: string; message: string }[];
}
export interface DiscoveryState extends DraftState {
  discovery: DiscoveryReport | null;
  online: OnlineReport | null;
  onlineQuery: string;
  onlineSource: string;
  onlineLimit: number;
}
export interface DiscoveryView { kind: 'documents' | 'online'; state: DiscoveryState; }

@Component({
  selector: 'app-discovery',
  standalone: true,
  templateUrl: './discovery.component.html',
})
export class DiscoveryComponent {
  @Input({ required: true }) view!: DiscoveryView;
  loading = false;
  error = '';
  readonly round = Math.round;
  readonly limits = [5, 8, 10, 15, 20];

  constructor(private readonly changeDetector: ChangeDetectorRef, private readonly destroyRef: DestroyRef, private readonly api: RadarApiService, private readonly router: Router) {}

  async analyze(files: FileList | null, text: string): Promise<void> {
    const selected = Array.from(files || []);
    const pasted = text.trim();
    if (!selected.length && !pasted) { this.error = 'Wybierz dokumenty lub wklej tekst.'; return; }
    if (selected.length + (pasted ? 1 : 0) > 15) { this.error = 'Można przeanalizować maksymalnie 15 dokumentów.'; return; }
    await this.run(async () => {
      for (const file of selected) {
        if (file.size > 10_000_000) throw new Error('Plik ' + file.name + ' przekracza 10 MB.');
        const pdf = /\.pdf$/i.test(file.name);
        if (!pdf && !/\.(txt|md)$/i.test(file.name)) throw new Error('Nieobsługiwany format: ' + file.name);
      }
      this.view.state.discovery = await this.api.analyze(selected, pasted);
    });
  }

  async online(event: Event, query: string, source: string, limit: string): Promise<void> {
    event.preventDefault();
    await this.run(async () => {
      const state = this.view.state;
      state.onlineQuery = query.trim();
      state.onlineSource = source;
      state.onlineLimit = Number(limit);
      state.online = await this.api.online(state.onlineQuery, source, state.onlineLimit);
    });
  }

  use(item: Candidate, online: boolean): void {
    const state = this.view.state;
    state.draft = {};
    for (const [key, value] of Object.entries(item.fields)) {
      if (typeof value === 'string' || (Array.isArray(value) && value.every((part) => typeof part === 'string'))) state.draft[key] = value;
    }
    state.sourceEvidence = item.evidence;
    state.sourceName = item.source_name;
    state.isDemo = online ? false : Boolean(item.fields.is_demo);
    state.sourceMode = online ? 'online' : 'discovery';
    state.sourceMeta = online ? {
      source_url: item.fields.source_url || '', source_provider: item.fields.source_provider || '',
      source_identifier: item.fields.source_identifier || '', source_published_at: item.fields.source_published_at || '',
      source_retrieved_at: item.fields.source_retrieved_at || '',
    } : {};
    state.extracted = null;
    void this.router.navigateByUrl('/innovations/new');
  }

  safeHttps(value: string | undefined): boolean {
    if (!value) return false;
    try { return new URL(value).protocol === 'https:'; } catch { return false; }
  }

  excerpt(value: string, length: number): string {
    return value.length > length ? value.slice(0, length).trim() + '…' : value;
  }

  private async run(action: () => Promise<void>): Promise<void> {
    this.loading = true;
    this.error = '';
    try { await action(); }
    catch (error: unknown) { this.error = apiError(error); }
    finally {
      this.loading = false;
      if (!this.destroyRef.destroyed) this.changeDetector.detectChanges();
    }
  }
}
