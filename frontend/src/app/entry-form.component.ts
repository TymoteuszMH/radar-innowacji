import { ChangeDetectorRef, Component, DestroyRef, Input } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { RadarApiService, apiError } from './radar-api.service';

type FieldValue = string | string[] | undefined;
export interface Extracted {
  extracted_characters: number;
  warnings: string[];
  fields: Record<string, FieldValue>;
}
export interface DraftState {
  draft: Record<string, FieldValue>;
  extracted: Extracted | null;
  sourceMode: 'form' | 'pdf' | 'discovery' | 'online';
  sourceEvidence: unknown[];
  sourceName: string;
  sourceMeta: Record<string, string>;
  isDemo: boolean;
}
export interface EntryFormView {
  kind: 'innovation' | 'need';
  state: DraftState;
}
interface Field {
  name: string;
  label: string;
  placeholder?: string;
  required?: boolean;
  minlength?: number;
  textarea?: boolean;
  options?: { value: string; label: string }[];
  full?: boolean;
}

const stages = [
  { value: 'concept', label: 'Koncepcja' }, { value: 'prototype', label: 'Prototyp' },
  { value: 'pilot', label: 'Pilotaż' }, { value: 'implemented', label: 'Wdrożone' },
];
const types = [
  { value: 'technical', label: 'Technologiczna' }, { value: 'organizational', label: 'Organizacyjna' },
  { value: 'educational', label: 'Edukacyjna' }, { value: 'social', label: 'Społeczna' },
  { value: 'process', label: 'Procesowa' },
];

@Component({
  selector: 'app-entry-form',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './entry-form.component.html',
})
export class EntryFormComponent {
  constructor(private readonly changeDetector: ChangeDetectorRef, private readonly destroyRef: DestroyRef, private readonly api: RadarApiService, private readonly router: Router) {}
  @Input({ required: true }) view!: EntryFormView;
  error = '';
  extracting = false;
  saving = false;
  readonly innovationFields: Field[] = [
    { name: 'title', label: 'Tytuł innowacji', required: true, minlength: 6, full: true, placeholder: 'np. Adaptacyjny plan powtórek' },
    { name: 'organization_name', label: 'Nazwa organizacji', required: true, minlength: 3, full: true, placeholder: 'np. Szkoła Demo D' },
    { name: 'problem', label: 'Jaki problem rozwiązuje?', required: true, minlength: 20, textarea: true, full: true, placeholder: 'Opisz problem oraz odbiorców' },
    { name: 'solution', label: 'Na czym polega rozwiązanie?', required: true, minlength: 20, textarea: true, full: true, placeholder: 'Opisz proces, narzędzie lub technologię' },
    { name: 'innovation_type', label: 'Rodzaj innowacji', options: types },
    { name: 'stage', label: 'Etap rozwoju', options: stages },
    { name: 'domain_tags', label: 'Obszary (po przecinku)', full: true, placeholder: 'edukacja, nauka' },
    { name: 'target_groups', label: 'Grupy docelowe (po przecinku)', full: true, placeholder: 'uczniowie, nauczyciele' },
    { name: 'claimed_impact', label: 'Zakładany wpływ', full: true, textarea: true, placeholder: 'Jaka zmiana jest spodziewana? Bez niepotwierdzonych liczb.' },
    { name: 'requirements', label: 'Warunki przeniesienia', full: true, textarea: true, placeholder: 'Co będzie wymagane w innej organizacji?' },
    { name: 'keywords', label: 'Słowa kluczowe (po przecinku)', full: true, placeholder: 'np. powtórki, uczniowie, nauka' },
  ];
  readonly needFields: Field[] = [
    { name: 'title', label: 'Nazwa potrzeby', required: true, minlength: 6, full: true, placeholder: 'np. Mniej zużytej energii w szkołach' },
    { name: 'organization_name', label: 'Nazwa organizacji', required: true, minlength: 3, full: true },
    { name: 'problem', label: 'Opis problemu', required: true, minlength: 20, textarea: true, full: true },
    { name: 'context', label: 'Kontekst wdrożenia', textarea: true, full: true },
    { name: 'desired_outcome', label: 'Oczekiwany wynik', textarea: true, full: true },
    { name: 'constraints', label: 'Wymagania i ograniczenia', textarea: true, full: true },
    { name: 'domain_tags', label: 'Obszary (po przecinku)', full: true, placeholder: 'samorząd, energia' },
    { name: 'target_groups', label: 'Odbiorcy (po przecinku)', full: true, placeholder: 'samorządy, zarządcy' },
    { name: 'keywords', label: 'Słowa kluczowe (po przecinku)', full: true },
    { name: 'minimum_stage', label: 'Minimalny etap rozwoju', options: stages },
  ];

  value(name: string): string {
    const value = this.view.kind === 'innovation' ? this.view.state.draft[name] : undefined;
    if (Array.isArray(value)) return value.join(',');
    return value || (name === 'innovation_type' ? 'educational' : name === 'stage' || name === 'minimum_stage' ? 'concept' : '');
  }

  safeHttps(value: string | undefined): boolean {
    if (!value) return false;
    try { return new URL(value).protocol === 'https:'; }
    catch { return false; }
  }

  async extract(form: HTMLFormElement, file: File | undefined, text: string): Promise<void> {
    if (!file && !text.trim()) { this.error = 'Wybierz PDF lub wpisz tekst.'; return; }
    this.error = '';
    this.extracting = true;
    this.view.state.draft = this.formValues(form);
    try {
      if (file && file.size > 10_000_000) throw new Error('PDF może mieć maksymalnie 10 MB.');
      const result = await this.api.extract(file, text);
      if (!this.isExtracted(result)) throw new Error('Niepoprawny wynik analizy dokumentu.');
      const state = this.view.state;
      state.sourceMode = file ? 'pdf' : 'form';
      state.extracted = result;
      state.sourceEvidence = [];
      state.sourceName = '';
      state.isDemo = false;
      state.draft = { ...state.draft, ...result.fields };
    } catch (error: unknown) {
      this.error = apiError(error);
    } finally {
      this.extracting = false;
      if (!this.destroyRef.destroyed) this.changeDetector.detectChanges();
    }
  }

  async save(event: Event, form: HTMLFormElement): Promise<void> {
    event.preventDefault();
    this.error = '';
    this.saving = true;
    try {
      const values = this.formValues(form);
      const payload: Record<string, unknown> = { ...values };
      for (const key of ['domain_tags', 'target_groups', 'keywords']) {
        payload[key] = String(values[key] || '').split(',').map((part) => part.trim()).filter(Boolean);
      }
      const state = this.view.state;
      if (this.view.kind === 'innovation') {
        payload['source_mode'] = state.sourceMode;
        if (state.sourceMode === 'discovery' || state.sourceMode === 'online') {
          payload['source_evidence'] = state.sourceEvidence;
          payload['source_name'] = state.sourceName;
          payload['is_demo'] = state.isDemo;
        }
        if (state.sourceMode === 'online') Object.assign(payload, state.sourceMeta);
      }
      const kind = this.view.kind === 'innovation' ? 'innovations' : 'needs';
      const response = this.view.kind === 'innovation' ? await this.api.saveInnovation(payload) : await this.api.saveNeed(payload);
      const id = this.responseId(response, this.view.kind);
      if (!id) throw new Error('Niepoprawna odpowiedź po zapisaniu danych.');
      if (this.view.kind === 'innovation') {
        state.draft = {}; state.extracted = null; state.sourceMode = 'form'; state.sourceEvidence = [];
        state.sourceName = ''; state.sourceMeta = {}; state.isDemo = false;
      }
      await this.router.navigate(['/', kind, id]);
    } catch (error: unknown) {
      this.error = apiError(error);
    } finally {
      this.saving = false;
      if (!this.destroyRef.destroyed) this.changeDetector.detectChanges();
    }
  }

  private formValues(form: HTMLFormElement): Record<string, string> {
    const result: Record<string, string> = {};
    new FormData(form).forEach((value, key) => {
      if (typeof value === 'string') result[key] = value;
    });
    return result;
  }

  private isExtracted(value: unknown): value is Extracted {
    return typeof value === 'object' && value !== null && 'fields' in value && 'warnings' in value && 'extracted_characters' in value;
  }

  private responseId(value: unknown, kind: 'innovation' | 'need'): string | undefined {
    if (typeof value !== 'object' || value === null || !(kind in value)) return undefined;
    const record = (value as Record<string, unknown>)[kind];
    if (typeof record !== 'object' || record === null || !('id' in record) || typeof record.id !== 'string') return undefined;
    return record.id;
  }
}
