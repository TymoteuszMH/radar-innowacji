import { Component, Input } from '@angular/core';
import { RouterLink } from '@angular/router';
import type { DetailView } from '../../interfaces/detail.interfaces';

@Component({
  selector: 'app-detail',
  standalone: true,
  imports: [RouterLink],
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

  assessmentStatus(status: string): string {
    return ({ uncertain: 'Niepewna ocena', high: 'Wysoki potencjał',
      development: 'Potencjał rozwojowy', low: 'Niski potencjał / Duplikat',
      unavailable: 'Brak oceny' } as Record<string, string>)[status] || 'Brak oceny';
  }

  sourceName(mode: string | undefined): string {
    if (mode === 'online') return 'Rekord z internetowego źródła, wymaga weryfikacji';
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
