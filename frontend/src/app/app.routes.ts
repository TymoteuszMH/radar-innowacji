import { Routes } from '@angular/router';
import { PageComponent } from './components/page/page.component';

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
    path: 'online',
    component: PageComponent,
    data: { mode: 'online', crumb: 'Wyszukaj innowacje', current: '/online' },
  },
  { path: '**', component: PageComponent, data: { mode: 'not-found', crumb: 'Błąd', current: '' } },
];
