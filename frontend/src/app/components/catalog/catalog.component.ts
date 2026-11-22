import { ChangeDetectorRef, Component, DestroyRef, Input, OnChanges } from '@angular/core';
import { RouterLink } from '@angular/router';
import { RadarApiService, apiError } from '../../services/radar-api.service';
import type { CatalogData, CatalogView } from '../../interfaces/catalog.interfaces';

@Component({
  selector: 'app-catalog',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './catalog.component.html',
})
export class CatalogComponent implements OnChanges {
  readonly round = Math.round;
  constructor(private readonly changeDetector: ChangeDetectorRef, private readonly destroyRef: DestroyRef, private readonly api: RadarApiService) {}
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
      const data = await this.api.catalog(this.view.kind, query);
      if (version === this.searchVersion) this.data = data;
    } catch (error: unknown) {
      if (version === this.searchVersion) {
        this.error = apiError(error);
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

  assessmentStatus(status: string): string {
    return ({ uncertain: 'Niepewna ocena', high: 'Wysoki potencjał',
      development: 'Potencjał rozwojowy', low: 'Niski potencjał / Duplikat' } as Record<string, string>)[status] || 'Brak oceny';
  }

  typeName(type: string | undefined): string {
    return this.typeNames[type || ''] || '';
  }

  excerpt(text: string | null | undefined): string {
    const value = String(text ?? '');
    return value.length > 180 ? value.slice(0, 180).trim() + '…' : value;
  }
}
