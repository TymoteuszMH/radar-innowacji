import { Routes } from '@angular/router';
import { PageComponent } from './components/page/page.component';

/** Trasy aplikacji uzywaja zwyklych sciezek; dawne /online przekierowuje na /search. */
export const routes: Routes = [
  { path: '', redirectTo: 'innovations', pathMatch: 'full' },
  {
    path: 'innovations',
    component: PageComponent,
    data: { mode: 'innovations', crumb: 'Innowacje', current: '/innovations' },
  },
  { path: 'innovations/new', redirectTo: 'innovations', pathMatch: 'full' },
  {
    path: 'innovations/:id',
    component: PageComponent,
    data: { mode: 'innovation-detail', crumb: 'Szczegóły innowacji', current: '/innovations' },
  },
  { path: 'needs', redirectTo: 'innovations', pathMatch: 'full' },
  { path: 'needs/:id', redirectTo: 'innovations', pathMatch: 'full' },
  {
    path: 'search',
    component: PageComponent,
    data: { mode: 'search', crumb: 'Wyszukaj innowacje', current: '/search' },
  },
  { path: 'online', redirectTo: 'search', pathMatch: 'full' },
  { path: '**', component: PageComponent, data: { mode: 'not-found', crumb: 'Błąd', current: '' } },
];
