import { Routes } from '@angular/router';
import { PageComponent } from './page.component';

export const routes: Routes = [
  { path: '', redirectTo: 'innovations', pathMatch: 'full' },
  { path: 'innovations', component: PageComponent, data: { mode: 'innovations', crumb: 'Innowacje', current: '/innovations' } },
  { path: 'innovations/new', component: PageComponent, data: { mode: 'innovation-form', crumb: 'Dodaj innowację', current: '/innovations/new' } },
  { path: 'innovations/:id', component: PageComponent, data: { mode: 'innovation-detail', crumb: 'Szczegóły innowacji', current: '/innovations' } },
  { path: 'needs', component: PageComponent, data: { mode: 'needs', crumb: 'Potrzeby', current: '/needs' } },
  { path: 'needs/new', component: PageComponent, data: { mode: 'need-form', crumb: 'Zgłoś potrzebę', current: '/needs/new' } },
  { path: 'needs/:id', component: PageComponent, data: { mode: 'need-detail', crumb: 'Szczegóły potrzeby', current: '/needs' } },
  { path: 'online', component: PageComponent, data: { mode: 'online', crumb: 'Wyszukiwanie online', current: '/online' } },
  { path: '**', component: PageComponent, data: { mode: 'not-found', crumb: 'Błąd', current: '' } },
];
