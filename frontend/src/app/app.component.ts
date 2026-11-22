import { Component } from '@angular/core';

@Component({
  selector: 'app-root',
  standalone: true,
  template: '<iframe class="radar-frame" src="/app/index.html" title="Innovation Radar"></iframe>',
  styles: [
    `
      :host {
        display: block;
        width: 100%;
        min-height: 100dvh;
      }

      .radar-frame {
        display: block;
        width: 100%;
        height: 100dvh;
        min-height: 560px;
        border: 0;
        background: #f5f7f9;
      }
    `,
  ],
})
export class AppComponent {}