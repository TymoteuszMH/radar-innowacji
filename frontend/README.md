# Innovation Radar v0.5 — Online Discovery + offline Core Engine

Static, gov.pl-inspired institutional prototype for the HackNation 2026 **Radar innowacji** challenge. Independent contest project, not an official government service.

## Start

Run `npm install` once, then `npm start` from the `frontend` directory and open the URL reported by Angular. Use `npm run build` for a production build. **Internet is needed only for the live OpenAlex search.**

The Angular application provides the outer layout, dashboard, catalog lists, detail pages and entry forms without an iframe. The discovery views and offline engine still use the legacy scripts in `app/`; the migration to Angular components and services is not yet complete. The original standalone `app/index.html` is also available.

## Online Discovery (new)

1. Open **Szukaj w internecie**.
2. Type a Polish or English search phrase (e.g. `edukacja`, `adaptive learning`).
3. Select **OpenAlex — API na żywo** for actual web search, **NCBR — lokalna próbka** for three curated real gov.pl projects, or both.
4. Inspect the source links, preliminary assessment, local matches and next steps. Review fields manually before saving.
5. If OpenAlex cannot be contacted (network, CORS, API rate limits), an error is shown. Offline documents and the NCBR sample remain functional.

**Source honesty:** OpenAlex is a live API adapter, but live network access could not be exercised from the development sandbox. The OpenAlex response format and browser UI were tested using mocked real-shaped JSON. NCBR is explicitly a *static curated snapshot* based on three verified official project pages, **not** an automated API/scraper. See `control_cases/`.

**No invented facts:** an OpenAlex article is *not* automatically a validated innovation. If its abstract is missing, saving is disabled. Missing problem, maturity, impact and evidence must be checked manually; preliminary score may remain blank. No LLM is integrated.

## Offline mode

All v0.4 functionality remains: batch analysis of local TXT, MD and text-PDF documents, reviewable citations, assessment, lexical matching, and recommendations. Offline data, including the starter synthetic examples, are distinguishable from real public source records.

## Local data and safety

The archive intentionally contains **no** `data/workspace.json`. When updating, save the existing folder and export your data first. Local backup format stays `version: 2`; online records use additional optional fields. Queries sent to OpenAlex leave the browser. No API keys are stored; the public site and local data should not hold sensitive information.

## Tests (optional Node.js 20+)

```sh
node tests/core.test.cjs
node tests/engine.test.cjs
node tests/online.test.cjs
node tests/ui.test.cjs
node tests/folder.test.cjs
```

See `README_RU.md` for Russian instructions. The existing `LICENSE` contains an EUPL-1.2 notice, not its full legal text — resolve before public publication.
