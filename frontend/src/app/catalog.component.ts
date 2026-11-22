import { ChangeDetectorRef, Component, DestroyRef, Input, OnChanges } from '@angular/core';

interface Organization {
  id: string;
  name: string;
}

interface CatalogItem {
  id: string;
  organization_id: string;
  title: string;
  problem?: string | null;
  is_demo: boolean;
  domain_tags?: string[];
  stage?: string;
  innovation_type?: string;
}

interface CatalogData {
  items: CatalogItem[];
  organizations: Organization[];
  total: number;
}

export interface CatalogView extends CatalogData {
  kind: 'innovations' | 'needs';
}

declare global {
  interface Window {
    RadarLocalApi: {
      request(endpoint: string): Promise<CatalogData>;
      request(endpoint: string, options: { method: string; body: string | Blob; headers?: Record<string, string> }): Promise<unknown>;
    };
  }
}

@Component({
  selector: 'app-catalog',
  standalone: true,
  templateUrl: './catalog.component.html',
})
export class CatalogComponent implements OnChanges {
  constructor(private readonly changeDetector: ChangeDetectorRef, private readonly destroyRef: DestroyRef) {}
  @Input({ required: true }) view!: CatalogView;
  data!: CatalogData;
  query = '';
  error = '';
  loading = false;
  private searchVersion = 0;

  private readonly stageNames: Record<string, string> = {
    concept: 'Koncepcja', prototype: 'Prototyp', pilot: 'Pilotaż', implemented: 'Wdrożone',
  };
  private readonly typeNames: Record<string, string> = {
    technical: 'Technologiczna', organizational: 'Organizacyjna', educational: 'Edukacyjna',
    social: 'Społeczna', process: 'Procesowa',
  };

  ngOnChanges(): void {
    this.searchVersion++;
    this.data = this.view;
    this.query = '';
    this.error = '';
    this.loading = false;
  }

  async search(event: Event, query: string): Promise<void> {
    event.preventDefault();
    const version = ++this.searchVersion;
    this.query = query;
    this.error = '';
    this.loading = true;
    try {
      const suffix = query ? `?q=${encodeURIComponent(query)}` : '';
      const data = await window.RadarLocalApi.request(`/api/${this.view.kind}${suffix}`);
      if (version === this.searchVersion) this.data = data;
    } catch (error: unknown) {
      if (version === this.searchVersion) {
        this.error = error instanceof Error ? error.message : 'Nie udało się wyszukać danych.';
      }
    } finally {
      if (version === this.searchVersion) {
        this.loading = false;
        if (!this.destroyRef.destroyed) this.changeDetector.detectChanges();
      }
    }
  }

  organizationName(id: string): string {
    return this.data.organizations.find((organization) => organization.id === id)?.name || 'Organizacja nieznana';
  }

  stageName(stage: string | undefined): string {
    return this.stageNames[stage || ''] || stage || '';
  }

  typeName(type: string | undefined): string {
    return this.typeNames[type || ''] || '';
  }

  excerpt(text: string | null | undefined): string {
    const value = String(text ?? '');
    return value.length > 180 ? value.slice(0, 180).trim() + '…' : value;
  }
}
