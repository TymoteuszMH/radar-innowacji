import { ChangeDetectorRef, Component, DestroyRef, Input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { RadarApiService, apiError } from '../../services/radar-api.service';
import type { SearchView } from '../../interfaces/search.interfaces';

/** Ekran wyszukiwania zindeksowanych projektow i linkow do zrodel. */
@Component({
  selector: 'app-search',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './search.component.html',
})
export class SearchComponent {
  @Input({ required: true }) view!: SearchView;
  readonly round = Math.round;
  loading = false;
  error = '';

  constructor(private readonly changeDetector: ChangeDetectorRef, private readonly destroyRef: DestroyRef, private readonly api: RadarApiService) {}

  async search(event: Event, query: string): Promise<void> {
    event.preventDefault();
    const phrase = query.trim();
    if (!phrase || !/[\p{L}\p{N}]/u.test(phrase)) { this.error = 'Podaj frazę do wyszukania.'; return; }
    await this.run(async () => {
      const state = this.view.state;
      state.query = phrase;
      state.results = null;
      state.results = await this.api.searchProjects(phrase);
    });
  }

  safeHttps(value: string | undefined): boolean {
    if (!value) return false;
    try { return new URL(value).protocol === 'https:'; } catch { return false; }
  }

  safeEmail(value: string): boolean {
    return /^[^\s@?&#]+@[^\s@?&#]+\.[^\s@?&#]+$/.test(value);
  }

  assessmentStatus(status: string): string {
    return ({ uncertain: 'Niepewna ocena', high: 'Wysoki potencjał',
      development: 'Potencjał rozwojowy', low: 'Niski potencjał / Duplikat' } as Record<string, string>)[status] || 'Brak oceny';
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