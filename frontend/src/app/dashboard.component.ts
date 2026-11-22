import { Component, Input } from '@angular/core';

interface Organization {
  id: string;
  name: string;
}

interface Innovation {
  id: string;
  organization_id: string;
  title: string;
  problem?: string | null;
  is_demo: boolean;
  stage: string;
  domain_tags?: string[];
}

interface FeaturedMatch {
  match_score: number | null;
  need: { title: string };
  reasons: string[];
}

export interface DashboardData {
  counts: { innovations: number; needs: number; organizations: number };
  featured: { innovation: Innovation; matches: FeaturedMatch[] }[];
  recent: Innovation[];
  organizations: Organization[];
}

@Component({
  selector: 'app-dashboard',
  standalone: true,
  templateUrl: './dashboard.component.html',
})
export class DashboardComponent {
  @Input({ required: true }) data!: DashboardData;

  private readonly stageNames: Record<string, string> = {
    concept: 'Koncepcja',
    prototype: 'Prototyp',
    pilot: 'Pilotaż',
    implemented: 'Wdrożone',
  };

  organizationName(id: string): string {
    return this.data.organizations.find((organization) => organization.id === id)?.name || 'Organizacja nieznana';
  }

  stageName(stage: string): string {
    return this.stageNames[stage] || 'Brak etapu';
  }

  excerpt(text: string | null | undefined, length: number): string {
    const value = String(text ?? '');
    return value.length > length ? value.slice(0, length).trim() + '…' : value;
  }
}
