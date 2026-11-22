import { afterNextRender, ChangeDetectorRef, Component, ElementRef, OnDestroy, ViewChild } from '@angular/core';

declare global {
  interface Window {
    startRadarApp(
      root: HTMLElement,
      renderShell: (current: string, crumb: string, folderName: string, warning: string) => void,
    ): () => void;
  }
}

@Component({
  selector: 'app-root',
  standalone: true,
  templateUrl: './app.component.html',
})
export class AppComponent implements OnDestroy {
  @ViewChild('page', { static: true }) private page!: ElementRef<HTMLElement>;

  readonly navigation = [
    { path: '/', icon: '▦', label: 'Pulpit' },
    { path: '/discovery', icon: '⌕', label: 'Wykrywanie w dokumentach' },
    { path: '/online', icon: '◎', label: 'Szukaj w internecie' },
    { path: '/innovations', icon: '◫', label: 'Katalog innowacji' },
    { path: '/needs', icon: '⌕', label: 'Potrzeby organizacji' },
    { path: '/innovations/new', icon: '＋', label: 'Zgłoś innowację' },
    { path: '/needs/new', icon: '＋', label: 'Zgłoś potrzebę' },
  ];
  readonly workspaceExpanded = !window.matchMedia('(max-width:760px)').matches;
  current = '/';
  crumb = 'Przegląd';
  folderName = '';
  warning = '';
  private dispose?: () => void;

  constructor(private readonly changeDetector: ChangeDetectorRef) {
    afterNextRender(() => {
      this.dispose = window.startRadarApp(this.page.nativeElement, (current, crumb, folderName, warning) => {
        this.current = current;
        this.crumb = crumb;
        this.folderName = folderName;
        this.warning = warning;
        this.changeDetector.detectChanges();
      });
    });
  }

  focusMain(event: MouseEvent): void {
    event.preventDefault();
    document.getElementById('main-content')?.focus();
  }

  ngOnDestroy(): void {
    this.dispose?.();
  }
}
