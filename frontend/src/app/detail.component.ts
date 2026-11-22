import { Component, Input } from '@angular/core';
import { NgTemplateOutlet } from '@angular/common';
import { RouterLink } from '@angular/router';

interface Organization { id: string; name: string; }
interface Entity {
  id: string;
  title: string;
  organization_id: string;
  problem: string;
  is_demo: boolean;
  domain_tags?: string[];
}
interface Innovation extends Entity {
  solution: string;
  stage: string;
  target_groups?: string[];
  claimed_impact?: string;
  requirements?: string;
  source_mode?: string;
  source_url?: string;
  source_provider?: string;
  source_published_at?: string;
  source_retrieved_at?: string;
}
interface Need extends Entity {
  desired_outcome?: string;
  context?: string;
  constraints?: string;
}
interface Match<T> {
  need?: T;
  innovation?: T;
  match_score: number | null;
  reasons: string[];
  matched_keywords?: string[];
  risks?: string[];
  unknowns: string[];
}
interface Action { title: string; reason: string; success_check: string; }
interface Assessment {
  score: number | null;
  coverage: number;
  status: string;
  disclaimer: string;
  missing_questions: string[];
  dimensions: { label: string; weight: number; grade: number | null; reason: string }[];
}
interface Evidence {
  field: string;
  source_name: string;
  line_number?: number;
  quote: string;
  source_url?: string;
}
export type DetailView = {
  kind: 'innovation';
  innovation: Innovation;
  organizations: Organization[];
  assessment: Assessment;
  similar: { innovation: Innovation; similarity_score: number; reasons: string[] }[];
  matches: Match<Need>[];
  actions: Action[];
  evidence: { records: Evidence[]; disclaimer: string };
} | {
  kind: 'need';
  need: Need;
  organizations: Organization[];
  matches: Match<Innovation>[];
};

@Component({
  selector: 'app-detail',
  standalone: true,
  imports: [NgTemplateOutlet, RouterLink],
  templateUrl: './detail.component.html',
})
export class DetailComponent {
  @Input({ required: true }) view!: DetailView;
  readonly round = Math.round;
  private readonly stageNames: Record<string, string> = {
    concept: 'Koncepcja', prototype: 'Prototyp', pilot: 'Pilotaż', implemented: 'Wdrożone',
  };

  organizationName(id: string): string {
    return this.view.organizations.find((organization) => organization.id === id)?.name || 'Organizacja nieznana';
  }

  stageName(stage: string): string {
    return this.stageNames[stage] || '';
  }

  sourceName(mode: string | undefined): string {
    if (mode === 'online') return 'Weryfikowany rekord z internetowego źródła';
    if (mode === 'discovery') return 'Wykrycie z dokumentu, zatwierdzone ręcznie';
    if (mode === 'pdf') return 'Wprowadzenie po analizie pliku PDF';
    return 'Wprowadzenie ręczne';
  }

  safeHttps(value: string | undefined): boolean {
    if (!value) return false;
    try { return new URL(value).protocol === 'https:'; }
    catch { return false; }
  }
}
