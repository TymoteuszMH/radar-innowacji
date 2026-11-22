import { Routes } from '@angular/router';
import { PageComponent } from './components/page/page.component';

/** Trasy aplikacji. */
export const routes: Routes = [
  { path: '', redirectTo: 'innovations', pathMatch: 'full' },
  {
    path: 'innovations',
    component: PageComponent,
    data: { mode: 'innovations', crumb: 'Innowacje', current: '/innovations' },
  },
  {
    path: 'innovations/:id',
    component: PageComponent,
    data: { mode: 'innovation-detail', crumb: 'Szczegóły innowacji', current: '/innovations' },
  },
  {
    path: 'search',
    component: PageComponent,
    data: { mode: 'search', crumb: 'Wyszukaj innowacje', current: '/search' },
  },
  { path: '**', component: PageComponent, data: { mode: 'not-found', crumb: 'Błąd', current: '' } },
];
