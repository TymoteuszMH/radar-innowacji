# Changelog

## v0.5 — Online Discovery (21.11.2026)

- Added an optional **Szukaj w internecie** screen (Polish institutional UI).
- Implemented a live OpenAlex Works API adapter with query limits, timeout, network/CORS and HTTP error messages, abstract reconstruction and source provenance.
- Added a **clearly labeled offline curated snapshot** of three real NCBR project pages (verified from official Gov.pl URLs). This is not live NCBR search.
- Added normalization, DOI/title de-duplication in search results, and reuse of v0.4 assessment, matching, similar-project search and next-step planning.
- Search stays read-only; saving requires manual field review and retains HTTPS source URL, provider, external ID and retrieval/publication dates.
- Added online metadata evidence without invented PDF line numbers. Modified claims lose mismatched source evidence.
- Preserved static app boot, `file://`-compatible local scripts, offline document workflow, synthetic seed labels, and workspace backup format **version 2**.
- Added integration tests with mocked OpenAlex responses and verified real NCBR control cases.

**Limits:** live external API was not reachable from the automated build environment; live search on the user's browser and its CORS behavior remain unverified. A research paper is not automatically an innovation, nor an independent impact study. No generative AI, generic web crawler, real-time NCBR API, or verified partner interest.


## v0.4 — Offline Core Engine (21.11.2026)

- Introduced source-aware `discovery.js` (local batch TXT/MD/text-PDF candidates) and `evidence.js` (field-level source quotes and line numbers).
- Discovery results now include provisional assessment, matching to local needs, similar entries, verification warnings, and next steps **before** the user decides to create a record.
- Added a Polish discovery page and two explicitly synthetic sample documents; a manual review form remains mandatory before saving.
- Updated local `assessment.js`, `matching.js`, and `actions.js` for clearer provenance and deployment-readiness caveats.
- Kept legacy routes, existing seed data, static module architecture, local backup format **v2**, and folder persistence unchanged.
- Added two TXT demonstration files alongside the original PDFs.
- Expanded tests: discovery, PDF extraction, false positive guard, multi-section splitting, source retention, modified quote removal, backward compatibility and offline Chromium UI checks.

**Constraints:** no real AI, semantic embeddings, internet crawling, OCR, external validation or confirmation of institutional interest. Direct `file://` launch remains to be checked by the user; the automated environment blocks file navigation.

## v0.3 — gov.pl-inspired institutional UI (21.11.2026)

- Kept the static Asset Factory-style architecture: `app/index.html` plus ordinary linked CSS and JavaScript.
- Redesigned shell, masthead, sidebar, workspace controls, page headers, lists, forms, assessment and matching details.
- New dashboard introduction, clear explanation of the process and two demo story entry points.
- Added official-affiliation disclaimer; removed SaaS-like green accents and decorative radar illustration.
- Added keyboard skip link, active navigation markers, focus management on route change, explicit required-field markers and progress meter labels.
- Kept all offline core logic and seed datasets intact; no service calls or external fonts.
- Fixed small-screen navigation and file-control visibility; local file panel starts collapsed on mobile.
- Confirmed 19 logic assertions, seven route rendering checks, folder save test and desktop/mobile Chromium rendering through inlined source assets.

**Not tested:** direct `file://` navigation via automated Chromium (blocked by execution policy). Full WCAG or production security certification is not claimed.

**Licensing:** current `LICENSE` is an EUPL-1.2 notice, not the full text. Complete this before public publication and check copyright/attribution.
