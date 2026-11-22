import { ChangeDetectorRef, Component, DestroyRef, OnInit } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { CatalogComponent } from '../catalog/catalog.component';
import { DetailComponent } from '../detail/detail.component';
import { DiscoveryComponent } from '../discovery/discovery.component';
import type { CatalogView } from '../../interfaces/catalog.interfaces';
import type { DetailView } from '../../interfaces/detail.interfaces';
import type { DiscoveryView } from '../../interfaces/discovery.interfaces';
import { DiscoveryStateService, RadarApiService, apiError } from '../../services/radar-api.service';

@Component({
  selector: 'app-page',
  standalone: true,
  imports: [RouterLink, CatalogComponent, DetailComponent, DiscoveryComponent],
  template: `
    @if (loading) { <div class="loading" role="status"><span class="spinner"></span>Wczytywanie…</div> }
    @if (error) { <div class="empty-state"><h1 id="page-title" tabindex="-1">Nie udało się otworzyć strony</h1><p role="alert">{{ error }}</p><a routerLink="/" class="btn btn-primary">Wróć do radaru</a></div> }
    @if (catalog; as data) { <app-catalog [view]="data"></app-catalog> }
    @if (detail; as data) { <app-detail [view]="data"></app-detail> }
    @if (discovery; as data) { <app-discovery [view]="data"></app-discovery> }
  `,
})
export class PageComponent implements OnInit {
  loading = false;
  error = '';
  catalog: CatalogView | null = null;
  detail: DetailView | null = null;
  discovery: DiscoveryView | null = null;
  private version = 0;

  constructor(
    private readonly route: ActivatedRoute,
    private readonly api: RadarApiService,
    private readonly discoveryState: DiscoveryStateService,
    private readonly changeDetector: ChangeDetectorRef,
    private readonly destroyRef: DestroyRef,
  ) {}

  ngOnInit(): void {
    this.route.paramMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(() => void this.load());
  }

  private async load(): Promise<void> {
    const version = ++this.version;
    this.loading = true;
    this.error = '';
    this.catalog = null; this.detail = null; this.discovery = null;
    try {
      const mode: unknown = this.route.snapshot.data['mode'];
      const id = this.route.snapshot.paramMap.get('id');
      let catalog: CatalogView | null = null;
      let detail: DetailView | null = null;
      let discovery: DiscoveryView | null = null;
      switch (mode) {
        case 'innovations': catalog = { kind: 'innovations', ...await this.api.catalog('innovations') }; break;
        case 'innovation-detail':
          if (!id) throw new Error('Nie podano identyfikatora innowacji.');
          detail = { kind: 'innovation', ...await this.api.innovation(id) }; break;
        case 'online': discovery = { state: this.discoveryState.state }; break;
        default: throw new Error('Nie znaleziono strony.');
      }
      if (version !== this.version || this.destroyRef.destroyed) return;
      this.catalog = catalog; this.detail = detail; this.discovery = discovery;
    } catch (error: unknown) {
      if (version !== this.version || this.destroyRef.destroyed) return;
      this.error = apiError(error);
    } finally {
      if (version === this.version && !this.destroyRef.destroyed) {
        this.loading = false;
        this.changeDetector.detectChanges();
        document.getElementById('page-title')?.focus({ preventScroll: true });
        window.scrollTo(0, 0);
      }
    }
  }
}
