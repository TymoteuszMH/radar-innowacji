import { ChangeDetectorRef, Component, DestroyRef, OnInit } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { merge } from 'rxjs';
import { CatalogComponent, CatalogView } from './catalog.component';
import { DetailComponent, DetailView } from './detail.component';
import { DiscoveryComponent, DiscoveryView } from './discovery.component';
import { EntryFormComponent, EntryFormView } from './entry-form.component';
import { DraftService, RadarApiService, apiError } from './radar-api.service';

@Component({
  selector: 'app-page',
  standalone: true,
  imports: [RouterLink, CatalogComponent, DetailComponent, DiscoveryComponent, EntryFormComponent],
  template: `
    @if (loading) { <div class="loading" role="status"><span class="spinner"></span>Wczytywanie…</div> }
    @if (error) { <div class="empty-state"><h1 id="page-title" tabindex="-1">Nie udało się otworzyć strony</h1><p role="alert">{{ error }}</p><a routerLink="/" class="btn btn-primary">Wróć do radaru</a></div> }
    @if (catalog; as data) { <app-catalog [view]="data"></app-catalog> }
    @if (detail; as data) { <app-detail [view]="data"></app-detail> }
    @if (form; as data) { <app-entry-form [view]="data"></app-entry-form> }
    @if (discovery; as data) { <app-discovery [view]="data"></app-discovery> }
  `,
})
export class PageComponent implements OnInit {
  loading = false;
  error = '';
  catalog: CatalogView | null = null;
  detail: DetailView | null = null;
  form: EntryFormView | null = null;
  discovery: DiscoveryView | null = null;
  private version = 0;

  constructor(
    private readonly route: ActivatedRoute,
    private readonly api: RadarApiService,
    private readonly drafts: DraftService,
    private readonly changeDetector: ChangeDetectorRef,
    private readonly destroyRef: DestroyRef,
  ) {}

  ngOnInit(): void {
    merge(this.route.paramMap, this.api.refresh$).pipe(takeUntilDestroyed(this.destroyRef)).subscribe(() => void this.load());
  }

  private async load(): Promise<void> {
    const version = ++this.version;
    this.loading = true;
    this.error = '';
    this.catalog = null; this.detail = null; this.form = null; this.discovery = null;
    try {
      const mode: unknown = this.route.snapshot.data['mode'];
      const id = this.route.snapshot.paramMap.get('id');
      let catalog: CatalogView | null = null;
      let detail: DetailView | null = null;
      let form: EntryFormView | null = null;
      let discovery: DiscoveryView | null = null;
      switch (mode) {
        case 'innovations': catalog = { kind: 'innovations', ...await this.api.catalog('innovations') }; break;
        case 'needs': catalog = { kind: 'needs', ...await this.api.catalog('needs') }; break;
        case 'innovation-detail':
          if (!id) throw new Error('Nie podano identyfikatora innowacji.');
          detail = { kind: 'innovation', ...await this.api.innovation(id) }; break;
        case 'need-detail':
          if (!id) throw new Error('Nie podano identyfikatora potrzeby.');
          detail = { kind: 'need', ...await this.api.need(id) }; break;
        case 'innovation-form': form = { kind: 'innovation', state: this.drafts.state }; break;
        case 'need-form': form = { kind: 'need', state: this.drafts.state }; break;
        case 'online': discovery = { kind: 'online', state: this.drafts.state }; break;
        default: throw new Error('Nie znaleziono strony.');
      }
      if (version !== this.version || this.destroyRef.destroyed) return;
      this.catalog = catalog; this.detail = detail; this.form = form; this.discovery = discovery;
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
