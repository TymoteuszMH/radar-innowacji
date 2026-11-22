import { Component, DestroyRef, OnInit } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Title } from '@angular/platform-browser';
import { ActivatedRoute, NavigationEnd, Router, RouterLink, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterLink, RouterOutlet],
  templateUrl: './app.component.html',
})
export class AppComponent implements OnInit {
  readonly navigation = [
    { path: '/online', icon: '◎', label: 'Wyszukaj innowacje' },
    { path: '/innovations', icon: '◫', label: 'Katalog innowacji' },
  ];
  current = '/';
  crumb = 'Przegląd';

  constructor(
    private readonly router: Router,
    private readonly route: ActivatedRoute,
    private readonly title: Title,
    private readonly destroyRef: DestroyRef,
  ) {}

  ngOnInit(): void {
    this.router.events
      .pipe(
        filter((event) => event instanceof NavigationEnd),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe(() => {
        const data = this.route.firstChild?.snapshot.data;
        this.current = typeof data?.['current'] === 'string' ? data['current'] : '';
        this.crumb = typeof data?.['crumb'] === 'string' ? data['crumb'] : 'Przegląd';
        this.title.setTitle(`${this.crumb} · Innovation Radar`);
      });
  }

  focusMain(event: MouseEvent): void {
    event.preventDefault();
    document.getElementById('main-content')?.focus();
  }
}
