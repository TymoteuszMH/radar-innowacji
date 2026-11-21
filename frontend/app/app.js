/* Innovation Radar v0.5. Offline core + optional public internet search. No AI API. */
const root = document.querySelector('#app');
const state = { draft:{}, extracted:null, sourceMode:'form', q:'', discovery:null, online:null, onlineQuery:'edukacja', onlineSource:'both', onlineLimit:8, sourceEvidence:[], sourceName:'', sourceMeta:{}, isDemo:false };
const stageNames = { concept:'Koncepcja',prototype:'Prototyp',pilot:'Pilotaż',implemented:'Wdrożone' };
const typeNames = { technical:'Technologiczna',organizational:'Organizacyjna',educational:'Edukacyjna',social:'Społeczna',process:'Procesowa' };
const e = (input) => String(input ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const cut = (text, len=160) => String(text ?? '').length>len ? String(text).slice(0,len).trim()+'…' : String(text ?? '');
const orgName = (id, orgs=[]) => orgs.find((o)=>o.id===id)?.name || 'Organizacja nieznana';
const demoTag = (isDemo) => isDemo ? '<span class="tag tag-demo">DANE DEMONSTRACYJNE</span>' : '<span class="tag tag-slate">Dane niezweryfikowane</span>';
const tags = (arr=[], max=3) => (arr||[]).slice(0,max).map((t)=>`<span class="tag">${e(t)}</span>`).join('');
async function api(url, options={}) {
  return window.RadarLocalApi.request(url, options);
}
const href = (route, content, klass='') => `<a href="#${e(route)}" data-nav="${e(route)}" class="${klass}">${content}</a>`;
const sideItem = (path, icon, label, active) => href(path, `<span class="nav-glyph" aria-hidden="true">${icon}</span><span>${label}</span>`, 'nav-link '+(active?'active':'')).replace('class="nav-link '+(active?'active':'')+'"', 'class="nav-link '+(active?'active':'')+'"'+(active?' aria-current="page"':''));
function shell(content, current='/', crumb='Przegląd') {
  const active = (route) => route==='/' ? current==='/' : route==='/innovations' ? current==='/innovations' : route==='/needs' ? current==='/needs' : current===route;
  const folderLabel = window.RadarStore.folderName ? 'Połączono: '+window.RadarStore.folderName : 'Nie wybrano folderu';
  const workspaceExpanded = !window.matchMedia?.('(max-width:760px)')?.matches;
  root.innerHTML = `<a class="skip-link" href="#main-content">Przejdź do treści</a>
  <div class="portal"><header class="site-header"><div class="site-header-inner">
    ${href('/','<span class="brand-mark" aria-hidden="true">IR</span><span class="brand-copy"><strong>Innovation Radar</strong><small>System identyfikacji i transferu innowacji</small></span>','brand-link')}
    <div class="header-right"><span class="header-label">HackNation 2026</span><span class="header-badge">Prototyp konkursowy</span></div>
  </div></header><div class="app-shell"><aside class="sidebar" aria-label="Panel nawigacji">
    <nav aria-label="Nawigacja główna"><div class="nav-caption">PRZEJDŹ DO</div><div class="nav-menu">
      ${sideItem('/','▦','Pulpit',active('/'))}
      ${sideItem('/discovery','⌕','Wykrywanie w dokumentach',active('/discovery'))}
      ${sideItem('/online','◎','Szukaj w internecie',active('/online'))}
      ${sideItem('/innovations','◫','Katalog innowacji',active('/innovations'))}
      ${sideItem('/needs','⌕','Potrzeby organizacji',active('/needs'))}
      ${sideItem('/innovations/new','＋','Zgłoś innowację',active('/innovations/new'))}
      ${sideItem('/needs/new','＋','Zgłoś potrzebę',active('/needs/new'))}
    </div></nav>
    <div class="sidebar-bottom"><details class="workspace-details" ${workspaceExpanded?'open':''}><summary>Pliki i zapis lokalny</summary>
      <div class="local-workspace"><p class="workspace-status">${e(folderLabel)}</p>
        <button type="button" class="workspace-btn" data-action="open-folder">Wybierz folder</button>
        <div class="workspace-actions"><button type="button" class="workspace-btn" data-action="export">Eksport JSON</button><button type="button" class="workspace-btn" data-action="import">Import JSON</button></div>
        <input id="json-import" type="file" accept=".json,application/json" hidden>
        <small>${e(window.RadarStore.storageWarning || 'Dane pozostają lokalnie. Po wybraniu folderu zapis do data/workspace.json.')}</small>
      </div></details>
      <div class="side-demo"><strong>Informacja o danych</strong><p>Dane startowe są fikcyjne. Rekordy z internetu są oznaczone oddzielnie. Oceny i dopasowania wymagają weryfikacji.</p></div>
    </div>
  </aside><main id="main-content" class="content-area" tabindex="-1"><div class="topbar"><div class="breadcrumbs"><span>Innovation Radar</span><span class="chevron" aria-hidden="true">/</span><b>${e(crumb)}</b></div><div class="status-line"><span class="status-dot" aria-hidden="true"></span> Silnik lokalny · internet opcjonalnie</div></div>
  <div class="page">${content}</div><footer class="footer"><span>Innovation Radar · HackNation 2026 · wersja demonstracyjna v0.5</span><span>Niezależny prototyp. Nie jest oficjalnym serwisem administracji publicznej.</span></footer></main></div></div>`;
  document.title = `${crumb} · Innovation Radar`;
}
function heading(kicker, title, desc, actions='') {return `<div class="page-heading"><div><div class="eyebrow">${e(kicker)}</div><h1 id="page-title" tabindex="-1">${e(title)}</h1>${desc?`<p>${e(desc)}</p>`:''}</div>${actions?`<div class="buttons">${actions}</div>`:''}</div>`;}
function pageError(err) { shell(`<div class="empty-state"><h2>Nie udało się otworzyć strony</h2><p>${e(err.message)}</p>${href('/','Wróć do radaru','btn btn-primary')}</div>`,'/','Błąd'); }
function matchCard(row, orgs) {
  const need = row.need;
  return `<article class="card"><div class="card-head">${demoTag(need.is_demo)}<div class="score">${row.match_score===null?'—':e(row.match_score)}<span> / 100*</span></div></div>
    <h3>${href('/needs/'+need.id,e(need.title))}</h3><p>${e(cut(need.problem,135))}</p>
    <div class="card-meta">${tags(need.domain_tags,3)}</div><div class="card-footer"><div><div class="small-note">${e(orgName(need.organization_id,orgs))}</div><div class="small-note">*Zgodność heurystyczna, nie prawdopodobieństwo</div></div>${href('/needs/'+need.id,'Zobacz →','link-subtle')}</div></article>`;
}
function innovationCard(inn, orgs) {
  return `<article class="card"><div class="card-head">${demoTag(inn.is_demo)}<span class="tag tag-slate">${e(stageNames[inn.stage]||'Brak etapu')}</span></div>
    <h3>${href('/innovations/'+inn.id,e(inn.title))}</h3><p>${e(cut(inn.problem,175))}</p><div class="card-meta">${tags(inn.domain_tags,3)}</div>
    <div class="card-footer"><span class="small-note">${e(orgName(inn.organization_id,orgs))}</span>${href('/innovations/'+inn.id,'Analizuj →','link-subtle')}</div></article>`;
}
async function dashboard() {
  const d = await api('/api/dashboard');
  const features = d.featured.map((pair)=>({ innovation:pair.innovation, top:pair.matches[0] }));
  const main = `<section class="hero" aria-labelledby="page-title">
    <div class="hero-copy"><div class="eyebrow">RADAR INNOWACJI · SYSTEM DEMONSTRACYJNY</div>
      <h1 id="page-title" tabindex="-1">Odkrywaj innowacje.<br><span>Łącz je z potrzebami.</span></h1>
      <p>Znajduj wartościowe pomysły ze szkół, uczelni i samorządów. Sprawdzaj ich potencjał oraz możliwe zastosowania w innych organizacjach.</p>
      <div class="buttons">${href('/online','Szukaj w internecie','btn btn-primary')}${href('/discovery','Wykryj w dokumentach','btn btn-secondary')}</div>
    </div>
    <div class="hero-guide"><div class="guide-title">Jak działa system?</div>
      <ol class="guide-steps"><li><span>01</span><div><strong>Wykryj lub zgłoś pomysł</strong><small>Przeszukaj OpenAlex lub przejrzyj lokalne dokumenty.</small></div></li>
      <li><span>02</span><div><strong>Sprawdź potencjał</strong><small>Poznaj kryteria, podobieństwa i ograniczenia.</small></div></li>
      <li><span>03</span><div><strong>Wybierz następny krok</strong><small>Znajdź pasujące potrzeby i plan weryfikacji.</small></div></li></ol>
      <span class="guide-note">Dopasowanie to hipoteza, nie potwierdzona współpraca.</span>
    </div></section>
    <div class="metric-grid" aria-label="Statystyki katalogu">
      <div class="metric-card"><span class="metric-label">Innowacje w katalogu</span><strong class="metric-num">${d.counts.innovations}</strong><span class="small-note">wpisy lokalne i demonstracyjne</span></div>
      <div class="metric-card"><span class="metric-label">Potrzeby organizacji</span><strong class="metric-num">${d.counts.needs}</strong><span class="small-note">zgłoszenia i fikcyjne przykłady</span></div>
      <div class="metric-card"><span class="metric-label">Organizacje</span><strong class="metric-num">${d.counts.organizations}</strong><span class="small-note">rekordy w lokalnej bazie</span></div>
    </div>
    <section class="demo-scenarios"><div class="section-head"><div><div class="eyebrow">PRZETESTUJ PROTOTYP</div><h2>Dwa scenariusze demonstracyjne</h2><p>Przykłady pokazują oba kierunki wyszukiwania. Dane i instytucje są fikcyjne.</p></div></div>
      <div class="scenario-grid">
        <article class="scenario-card"><div class="scenario-type">SCENARIUSZ 01 · OD INNOWACJI</div><h3>Pomysł ze szkoły</h3><p>Sprawdź ocenę rozwiązania edukacyjnego, podobne projekty i potrzeby innych placówek.</p>${href('/innovations/inn-adaptive','Przejdź do analizy innowacji →','text-link')}</article>
        <article class="scenario-card"><div class="scenario-type">SCENARIUSZ 02 · OD POTRZEBY</div><h3>Problem samorządu</h3><p>Rozpocznij od potrzeby ograniczenia kosztów odbioru odpadów i znajdź możliwe rozwiązania.</p>${href('/needs/need-waste','Znajdź innowacje dla gminy →','text-link')}</article>
      </div></section>
    <section><div class="section-head"><div><h2>Potencjalne dopasowania</h2><p>Przykładowe pary innowacja → potrzeba. Wyniki są wyłącznie orientacyjne.</p></div>${href('/innovations','Wszystkie innowacje →','text-link')}</div>
      <div class="cards-grid">${features.map((item)=>`<article class="card"><div class="card-head"><span class="tag tag-good">WSTĘPNE DOPASOWANIE</span><span class="score">${item.top.match_score===null?'—':item.top.match_score}<span> / 100*</span></span></div><h3>${href('/innovations/'+item.innovation.id,e(item.innovation.title))}</h3><div class="small-note">${e(orgName(item.innovation.organization_id,d.organizations))}</div><div class="divider"></div><div class="card-meta"><span class="pair-arrow" aria-hidden="true">↓</span><strong class="pair-need">${e(item.top.need.title)}</strong></div><p>${e(item.top.reasons[0]||'Dopasowanie wymaga oceny człowieka.')}</p><div class="card-footer"><span class="small-note">*Ocena heurystyczna</span>${href('/innovations/'+item.innovation.id,'Szczegóły →','link-subtle')}</div></article>`).join('')||'<div class="empty">Brak dopasowań w bazie.</div>'}</div></section>
    <section><div class="section-head"><div><h2>Ostatnio dodane innowacje</h2><p>Przeglądaj pomysły i oceniaj kolejne kroki.</p></div>${href('/innovations','Otwórz katalog →','text-link')}</div><div class="cards-grid">${d.recent.slice(0,4).map((i)=>innovationCard(i,d.organizations)).join('')}</div></section>
    <div class="notice" role="note"><strong>Ważne:</strong> 10 przykładowych innowacji i 6 potrzeb to fikcyjne scenariusze. Ocena nie oznacza potwierdzenia skuteczności, zainteresowania organizacji ani gotowości do wdrożenia.</div>`;
  shell(main,'/','Radar');
}
async function innovationsList(query='') {
  const d = await api('/api/innovations'+(query?`?q=${encodeURIComponent(query)}`:''));
  const content = heading('KATALOG POMYSŁÓW','Odkryj innowacje','Przeglądaj pomysły z różnych typów instytucji i sprawdź ich potencjał.',href('/innovations/new','＋ Dodaj innowację','btn btn-primary')) +
  `<form data-form="search-innovations" class="search-row"><div class="search-field"><span class="search-icon">⌕</span><input name="q" aria-label="Szukaj innowacji" value="${e(query)}" placeholder="Szukaj po problemie, rozwiązaniu lub obszarze..."></div><button type="submit" class="btn">Szukaj</button></form><div class="section-head"><h2>Innowacje <span class="counter">${d.total}</span></h2><span class="small-note">Oceny nie są zweryfikowane</span></div><div class="list-cards">${d.items.map((inn)=>`<article class="list-row"><div><div class="meta">${demoTag(inn.is_demo)} ${tags(inn.domain_tags,2)} <span class="tag tag-outline">${e(stageNames[inn.stage]||inn.stage)}</span></div><h3>${href('/innovations/'+inn.id,e(inn.title))}</h3><p>${e(cut(inn.problem,180))}</p><div class="small-note" style="margin-top:9px">${e(orgName(inn.organization_id,d.organizations))} · ${e(typeNames[inn.innovation_type]||'')}</div></div><div class="side">${href('/innovations/'+inn.id,'Otwórz →','btn btn-sm')}</div></article>`).join('')||'<div class="empty">Brak wyników. Spróbuj innego hasła.</div>'}</div>`;
  shell(content,'/innovations','Innowacje');
}
async function needsList(query='') {
  const d = await api('/api/needs'+(query?`?q=${encodeURIComponent(query)}`:''));
  const content = heading('OD PROBLEMU DO ROZWIĄZANIA','Potrzeby organizacji','Zacznij od konkretnej potrzeby, aby wyszukać możliwe innowacje.',href('/needs/new','＋ Zgłoś potrzebę','btn btn-primary')) +
  `<form data-form="search-needs" class="search-row"><div class="search-field"><span class="search-icon">⌕</span><input name="q" aria-label="Szukaj potrzeb" value="${e(query)}" placeholder="Jaką potrzebę chcesz rozwiązać?"></div><button type="submit" class="btn">Szukaj</button></form><div class="section-head"><h2>Zgłoszone potrzeby <span class="counter">${d.total}</span></h2><span class="small-note">Prywatne dane lokalne i przykłady</span></div><div class="list-cards">${d.items.map((n)=>`<article class="list-row"><div><div class="meta">${demoTag(n.is_demo)} ${tags(n.domain_tags,2)}</div><h3>${href('/needs/'+n.id,e(n.title))}</h3><p>${e(cut(n.problem,180))}</p><div class="small-note" style="margin-top:9px">${e(orgName(n.organization_id,d.organizations))}</div></div><div class="side">${href('/needs/'+n.id,'Szukaj rozwiązań →','btn btn-sm')}</div></article>`).join('')||'<div class="empty">Brak potrzeb dla tego hasła.</div>'}</div>`;
  shell(content,'/needs','Potrzeby');
}
function matchBlock(match, organizations, target) {
  const entity = target==='need' ? match.need : match.innovation;
  const url = target==='need' ? `/needs/${entity.id}` : `/innovations/${entity.id}`;
  return `<div class="match-row"><div class="match-title">${href(url,e(entity.title))}<span class="tag tag-good">${match.match_score==null?'Brak oceny':match.match_score+' / 100*'}</span></div>
    <div class="small-note">${e(orgName(entity.organization_id,organizations))}</div><p class="match-reason">${match.reasons.map(e).join(' ')}</p><p class="small-note">${match.matched_keywords?.length?'Wspólne frazy: '+e(match.matched_keywords.join(', '))+'. ':''}${match.risks?.length?'Uwaga: '+e(match.risks.join(' ')):''}</p>
    <div class="card-meta">${tags(entity.domain_tags,3)}</div><p class="small-note">Do weryfikacji: ${e(match.unknowns[0])} ${href(url,'Szczegóły →','link-subtle')}</p></div>`;
}
async function innovationDetail(id) {
  const d = await api('/api/innovations/'+id), i=d.innovation, a=d.assessment;
  const actions = d.actions.map((step,j)=>`<div class="step"><div class="step-num">${j+1}</div><div><div class="step-title">${e(step.title)}</div><p class="step-p">${e(step.reason)}</p><p class="step-p"><b>Kryterium:</b> ${e(step.success_check)}</p></div></div>`).join('');
  const assessments = a.dimensions.map((r)=>`<div class="assessment-row"><div class="assessment-top"><div class="assessment-name">${e(r.label)} <span class="small-note">${Math.round(r.weight*100)}%</span></div><span class="assessment-score">${r.grade===null?'Brak danych':r.grade+' / 4'}</span></div><div class="progress" role="meter" aria-label="${e(r.label)}" aria-valuemin="0" aria-valuemax="4" aria-valuenow="${r.grade===null?0:r.grade}"><div style="width:${r.grade===null?0:r.grade/4*100}%"></div></div><div class="assessment-note">${e(r.reason)}</div></div>`).join('');
  const content = `${href('/innovations','← Powrót do katalogu','back')}
    ${heading('ANALIZA INNOWACJI',i.title,'Każda rekomendacja wymaga weryfikacji przez autora lub eksperta.',href('/innovations/new','＋ Dodaj kolejną','btn'))}
    <div class="card-meta" style="margin:-11px 0 21px">${demoTag(i.is_demo)} ${tags(i.domain_tags,4)} <span class="tag tag-outline">${e(stageNames[i.stage]||'')}</span></div>
    <div class="detail-grid"><div class="stack"><section class="detail-card"><h2>Opis rozwiązania</h2><div class="data-heading">Problem</div><p>${e(i.problem)}</p><div class="data-heading">Proponowane rozwiązanie</div><p>${e(i.solution)}</p><div class="data-heading">Deklarowany wpływ</div><p>${e(i.claimed_impact||'Brak deklarowanych efektów.')}</p><div class="data-heading">Warunki wdrożenia</div><p>${e(i.requirements||'Brak danych — wymagane uzupełnienie.')}</p><div class="line"></div><div class="card-meta">${tags(i.target_groups,6)}</div><p class="small-note">Źródło: ${e(i.source_mode==='online'?'Weryfikowany rekord z internetowego źródła':i.source_mode==='discovery'?'Wykrycie z dokumentu, zatwierdzone ręcznie':i.source_mode==='pdf'?'Wprowadzenie po analizie pliku PDF':'Wprowadzenie ręczne')} · ${e(orgName(i.organization_id,d.organizations))}</p>${i.source_url && window.RadarOnlineSearch.safeHttps(i.source_url)?`<p class="small-note">Oryginalne źródło: <a target="_blank" rel="noopener noreferrer" href="${e(i.source_url)}">${e(i.source_provider||'Otwórz stronę źródłową')}</a> · ${e(i.source_published_at||'Data publikacji nieznana')} · pozyskano ${e((i.source_retrieved_at||'').slice(0,10))}</p>`:''}</section>
      <section class="detail-card"><h2>Możliwie podobne projekty <span class="counter">${d.similar.length}</span></h2>${d.similar.length?d.similar.map((s)=>`<div class="match-row"><div class="match-title">${href('/innovations/'+s.innovation.id,e(s.innovation.title))}<span class="tag tag-slate">${s.similarity_score} / 100*</span></div><p class="match-reason">${e(s.reasons.join(' ')||'Potencjalne podobieństwo tekstowe.')}</p><div class="small-note">*Podobieństwo heurystyczne, nie dowód duplikatu.</div></div>`).join(''):'<div class="empty">Nie znaleziono silnego podobieństwa w lokalnym katalogu.</div>'}</section></div>
      <div class="stack"><section class="detail-card"><h2>Ocena potencjału</h2><div class="stat-highlight"><div><span class="small-note">Wynik wstępny</span><div><strong>${a.score===null?'—':a.score}</strong><span class="small-note"> / 100</span></div><p>Pokrycie kryteriów: ${Math.round(a.coverage*100)}%</p></div><span class="tag ${a.status==='provisional'?'tag-good':'tag-demo'}">${a.status==='provisional'?'WSTĘPNA':'BRAK DANYCH'}</span></div>${assessments}<p class="small-note" style="margin-top:16px">${e(a.disclaimer)}</p>${a.missing_questions.length?`<div class="notice" style="margin-top:12px"><b>Do uzupełnienia:</b> ${e(a.missing_questions.join(' '))}</div>`:''}</section></div></div>
    ${d.evidence.records.length?`<section class="detail-card evidence-section"><h2>Źródła opisu <span class="counter">${d.evidence.records.length}</span></h2><p>${e(d.evidence.disclaimer)}</p><div class="evidence-list">${d.evidence.records.map(r=>`<div class="evidence-item"><strong>${e(r.field)} · ${e(r.source_name)} · ${r.line_number?'wiersz '+r.line_number:'metadane źródła'}</strong><blockquote>${e(r.quote)}</blockquote>${r.source_url && window.RadarOnlineSearch.safeHttps(r.source_url)?`<a href="${e(r.source_url)}" target="_blank" rel="noopener noreferrer">Sprawdź źródło ↗</a>`:''}</div>`).join('')}</div></section>`:''}
    <div class="detail-grid"><section class="detail-card"><h2>Dopasowane potrzeby <span class="counter">${d.matches.length}</span></h2><p>Dlaczego dana innowacja może odpowiadać na opisany problem?</p>${d.matches.length?d.matches.map((m)=>matchBlock(m,d.organizations,'need')).join(''):'<div class="empty">Brak przekonujących dopasowań w katalogu.</div>'}<div class="notice neutral" style="margin-top:14px">*Wyniki są punktacją dopasowania słów, obszarów i etapu rozwoju. Nie są zweryfikowaną prognozą ani gwarancją współpracy.</div></section><section class="detail-card"><h2>Następne kroki</h2><p>Co powinien zrobić człowiek, zanim rozpocznie wdrożenie?</p><div class="steps">${actions}</div></section></div>`;
  shell(content,'/innovations','Szczegóły innowacji');
}
async function needDetail(id) {
  const d = await api('/api/needs/'+id), n=d.need;
  const content = `${href('/needs','← Powrót do potrzeb','back')}${heading('OD POTRZEBY DO INNOWACJI',n.title,'Rozwiązania z katalogu pasujące do problemu organizacji.')}
    <div class="card-meta" style="margin:-10px 0 20px">${demoTag(n.is_demo)} ${tags(n.domain_tags,4)}</div>
    <div class="detail-grid"><section class="detail-card"><h2>Kontekst potrzeby</h2><div class="data-heading">Problem do rozwiązania</div><p>${e(n.problem)}</p><div class="data-heading">Oczekiwany rezultat</div><p>${e(n.desired_outcome||'Nie wskazano.')}</p><div class="data-heading">Kontekst organizacji</div><p>${e(n.context||'Brak opisu kontekstu.')}</p><div class="data-heading">Ograniczenia</div><p>${e(n.constraints||'Wymagane doprecyzowanie.')}</p><p class="small-note">Organizacja: ${e(orgName(n.organization_id,d.organizations))}</p></section>
    <section class="detail-card"><h2>Innowacje do rozważenia <span class="counter">${d.matches.length}</span></h2>${d.matches.length?d.matches.map((m)=>matchBlock(m,d.organizations,'innovation')).join(''):'<div class="empty">Brak przekonujących dopasowań.</div>'}</section></div>
    <div class="notice">Wszystkie potrzeby demonstracyjne są fikcyjne. Dopasowanie nie oznacza, że organizacja wyraziła zgodę na pilotaż, kontakt lub finansowanie.</div>`;
  shell(content,'/needs','Szczegóły potrzeby');
}
function field(name, label, value='', opts={}) {
  const attrs = `${opts.required?'required':''} ${opts.minlength?`minlength="${opts.minlength}"`:''}`;
  if (opts.select) return `<div class="field ${opts.full?'full':''}"><label for="f-${name}">${e(label)}${opts.required?'<span class="required-mark" aria-hidden="true"> *</span>':''}</label><select id="f-${name}" name="${name}" ${attrs}>${opts.select.map(([value1,text])=>`<option value="${e(value1)}" ${value1===value?'selected':''}>${e(text)}</option>`).join('')}</select></div>`;
  return `<div class="field ${opts.full?'full':''}"><label for="f-${name}">${e(label)}${opts.required?'<span class="required-mark" aria-hidden="true"> *</span>':''}</label>${opts.textarea?`<textarea id="f-${name}" name="${name}" placeholder="${e(opts.placeholder||'')}" ${attrs}>${e(value)}</textarea>`:`<input id="f-${name}" name="${name}" value="${e(value)}" type="text" placeholder="${e(opts.placeholder||'')}" ${attrs}>`}${opts.hint?`<small>${e(opts.hint)}</small>`:''}</div>`;
}
function innovationForm() {
  const d=state.draft;
  const content = heading('NOWA KARTA','Dodaj innowację','Opisz lokalny pomysł lub wczytaj tekstowy PDF. Wszystkie dane można sprawdzić i poprawić przed zapisem.')+
    `<div class="form-layout"><div><section class="form-section"><h2>01 / Analiza dokumentu</h2><p>Opcjonalny import PDF z warstwą tekstową. Ekstrakcja działa offline, na prostych regułach.</p>
      <div class="upload-box"><div class="upload-symbol" aria-hidden="true">⇧</div><strong>Wybierz dokument PDF (do 10 MB)</strong><p>Proste PDF-y z warstwą tekstową są odczytywane lokalnie; zaawansowane PDF-y i skany mogą nie działać. Żadne dane nie są wysyłane do zewnętrznej usługi AI.</p><input id="pdf-input" aria-label="Wybierz plik PDF" type="file" accept=".pdf,application/pdf"><div style="margin:12px 0">lub wklej opis:</div><textarea id="extract-text" aria-label="Treść dokumentu do analizy" rows="4" class="text-extract" placeholder="Tytuł: ...&#10;Problem: ...&#10;Rozwiązanie: ..."></textarea><button type="button" class="btn btn-primary" data-action="extract" style="margin-top:12px">⌁ Analizuj i uzupełnij formularz</button></div>
      ${state.sourceMode==='discovery'?`<div class="notice green" style="margin-top:12px"><strong>Pomysł wykryty w dokumencie.</strong> Sprawdź wszystkie pola, etap i dziedziny przed zapisem. ${state.sourceEvidence.length} pól ma cytaty źródłowe (to nie jest weryfikacja prawdziwości).</div>`:''}
      ${state.sourceMode==='online'?`<div class="notice neutral" style="margin-top:12px"><strong>Rekord ze źródła publicznego.</strong> <a href="${e(state.sourceMeta.source_url)}" target="_blank" rel="noopener noreferrer">Sprawdź oryginalny materiał ↗</a>. Sam tytuł lub abstrakt nie potwierdza innowacji. Uzupełnij problem i zweryfikuj opis przed zapisem.</div>`:''}
      ${state.extracted?`<div class="notice green" style="margin-top:12px"><b>Odczytano ${state.extracted.extracted_characters} znaków.</b> ${e(state.extracted.warnings.join(' '))}</div>`:''}
    </section><form id="innovation-form" data-form="new-innovation"><section class="form-section"><h2>02 / Sprawdź dane</h2><p>Przed zapisem popraw pola rozpoznane automatycznie. Nic nie jest publikowane poza lokalną demonstracją.</p><div class="form-grid">
      ${field('title','Tytuł innowacji',d.title,{full:true,required:true,minlength:6,placeholder:'np. Adaptacyjny plan powtórek'})}
      ${field('organization_name','Nazwa organizacji',d.organization_name,{full:true,required:true,minlength:3,placeholder:'np. Szkoła Demo D'})}
      ${field('problem','Jaki problem rozwiązuje?',d.problem,{full:true,textarea:true,required:true,minlength:20,placeholder:'Opisz problem oraz odbiorców'})}
      ${field('solution','Na czym polega rozwiązanie?',d.solution,{full:true,textarea:true,required:true,minlength:20,placeholder:'Opisz proces, narzędzie lub technologię'})}
      ${field('innovation_type','Rodzaj innowacji',d.innovation_type||'educational',{select:Object.entries(typeNames)})}
      ${field('stage','Etap rozwoju',d.stage||'concept',{select:Object.entries(stageNames)})}
      ${field('domain_tags','Obszary (po przecinku)',d.domain_tags,{full:true,placeholder:'edukacja, nauka'})}
      ${field('target_groups','Grupy docelowe (po przecinku)',d.target_groups,{full:true,placeholder:'uczniowie, nauczyciele'})}
      ${field('claimed_impact','Zakładany wpływ',d.claimed_impact,{full:true,textarea:true,placeholder:'Jaka zmiana jest spodziewana? Bez niepotwierdzonych liczb.'})}
      ${field('requirements','Warunki przeniesienia',d.requirements,{full:true,textarea:true,placeholder:'Co będzie wymagane w innej organizacji?'})}
      ${field('keywords','Słowa kluczowe (po przecinku)',d.keywords,{full:true,placeholder:'np. powtórki, uczniowie, nauka'})}
      </div></section><div id="form-error" role="status" aria-live="polite"></div><div class="buttons"><button type="submit" class="btn btn-primary">Zapisz i przeanalizuj →</button>${href('/innovations','Anuluj','btn')}</div></form></div>
    <aside class="sticky-side"><section class="detail-card"><h2>Jak to działa?</h2><div class="steps"><div class="step"><div class="step-num">1</div><div><div class="step-title">Wprowadź pomysł</div><p class="step-p">Dodaj opis albo PDF z tekstem.</p></div></div><div class="step"><div class="step-num">2</div><div><div class="step-title">Zatwierdź dane</div><p class="step-p">Sprawdź problemy, rozwiązanie i źródła.</p></div></div><div class="step"><div class="step-num">3</div><div><div class="step-title">Zobacz możliwości</div><p class="step-p">Ocena, podobne pomysły, potrzeby i plan.</p></div></div></div></section><div class="notice">Tryb lokalny nie zawiera uwierzytelniania i nie jest przeznaczony do prawdziwych danych osobowych ani poufnych dokumentów.</div></aside></div>`;
  shell(content,'/innovations/new','Dodaj innowację');
}
function needForm() {
  const content = heading('NOWA POTRZEBA','Zgłoś problem','Dodaj potrzebę organizacji i sprawdź, jakie rozwiązania już znajdują się w katalogu.')+
    `<form data-form="new-need" class="form-layout"><div><section class="form-section"><h2>Opis potrzeby</h2><div class="form-grid">
    ${field('title','Nazwa potrzeby','',{full:true,required:true,minlength:6,placeholder:'np. Mniej zużytej energii w szkołach'})}
    ${field('organization_name','Nazwa organizacji','',{full:true,required:true,minlength:3})}
    ${field('problem','Opis problemu','',{full:true,required:true,minlength:20,textarea:true})}
    ${field('context','Kontekst wdrożenia','',{full:true,textarea:true})}
    ${field('desired_outcome','Oczekiwany wynik','',{full:true,textarea:true})}
    ${field('constraints','Wymagania i ograniczenia','',{full:true,textarea:true})}
    ${field('domain_tags','Obszary (po przecinku)','',{full:true,placeholder:'samorząd, energia'})}
    ${field('target_groups','Odbiorcy (po przecinku)','',{full:true,placeholder:'samorządy, zarządcy'})}
    ${field('keywords','Słowa kluczowe (po przecinku)','',{full:true})}
    ${field('minimum_stage','Minimalny etap rozwoju','concept',{select:Object.entries(stageNames)})}</div></section><div id="form-error" role="status" aria-live="polite"></div><div class="buttons"><button class="btn btn-primary" type="submit">Zapisz potrzebę →</button>${href('/needs','Anuluj','btn')}</div></div><aside class="sticky-side"><div class="notice green">Wyniki będą orientacyjnymi propozycjami, nie potwierdzeniem gotowości podmiotów do kontaktu lub finansowania.</div></aside></form>`;
  shell(content,'/needs/new','Zgłoś potrzebę');
}
function demoDiscoveryDocuments() {
  const ids=['inn-adaptive','inn-waste-routes'];
  const orgs=window.RadarSeed.organizations;
  return ids.map((id,index)=>{
    const i=window.RadarSeed.innovations.find(item=>item.id===id);
    const organization=orgs.find(org=>org.id===i.organization_id)?.name||'Instytucja demonstracyjna';
    return { name:`Przykład-${index+1}.txt`,is_demo:true,
      text:`Tytuł: ${i.title}\nOrganizacja: ${organization}\nProblem: ${i.problem}\nRozwiązanie: ${i.solution}\nEfekt: ${i.claimed_impact}\nWymagania: ${i.requirements}` };
  });
}
function discoveryPage() {
  const report=state.discovery;
  const candidateCards=report?.candidates.map((item,index)=>{
    const inn=item.fields, a=item.assessment;
    const evidence=item.evidence.map(r=>`<div class="evidence-item"><strong>${e(r.field)} · ${e(r.source_name)} · ${r.line_number?'wiersz '+r.line_number:'metadane źródła'}</strong><blockquote>${e(r.quote)}</blockquote>${r.source_url && window.RadarOnlineSearch.safeHttps(r.source_url)?`<a href="${e(r.source_url)}" target="_blank" rel="noopener noreferrer">Sprawdź źródło ↗</a>`:''}</div>`).join('');
    const matchRows=item.matches.slice(0,3).map(m=>`<div class="match-row"><div class="match-title"><span>${e(m.need.title)}</span><span class="tag tag-slate">${m.match_score===null?'Weryfikacja':m.match_score+' / 100*'}</span></div><p class="match-reason">${m.reasons.map(e).join(' ')}</p><p class="small-note">${m.matched_keywords?.length?'Wspólne pojęcia: '+e(m.matched_keywords.join(', '))+'. ':''}${m.risks?.length?'Ograniczenia: '+e(m.risks.join(' ')):''}</p></div>`).join('');
    return `<article class="detail-card discovery-result"><div class="discovery-result-head"><span class="tag ${inn.is_demo?'tag-demo':'tag-slate'}">${inn.is_demo?'PRZYKŁAD SYNTETYCZNY':'WYKRYTO W PLIKU'}</span><span class="small-note">${e(item.source_name)}</span></div>
      <h3>${e(inn.title)}</h3><p><strong>Problem:</strong> ${e(inn.problem||'Brak — uzupełnij przed zapisem.')}</p><p><strong>Rozwiązanie:</strong> ${e(inn.solution)}</p>
      <div class="discovery-metrics"><div><strong>${a.score===null?'Brak pełnej oceny':a.score+' / 100'}</strong><small>Ocena wstępna · pokrycie ${Math.round(a.coverage*100)}%</small></div><div><strong>${item.matches.length}</strong><small>Potencjalne dopasowania</small></div><div><strong>${item.similar.length}</strong><small>Podobne wpisy w katalogu</small></div></div>
      <div class="card-meta">${tags(inn.domain_tags,5)} ${tags(inn.keywords,4)}</div>
      <details class="discovery-details"><summary>Ocena i ograniczenia</summary><ul>${a.dimensions.map(d=>`<li>${e(d.label)} — ${d.grade===null?'brak danych':d.grade+' / 4'}; ${e(d.reason)}</li>`).join('')}</ul><p class="small-note">${e(a.disclaimer)}</p><p class="small-note">${e(item.warnings.join(' '))}</p></details>
      <details class="discovery-details"><summary>Dopasowania i następne kroki</summary><div>${matchRows||'<p class="small-note">Brak silnych dopasowań w lokalnym katalogu.</p>'}</div><ol class="discovery-steps">${item.actions.map(task=>`<li><strong>${e(task.title)}</strong> — ${e(task.success_check)}</li>`).join('')}</ol></details>
      <details class="discovery-details"><summary>Cytaty źródłowe (${item.evidence.length})</summary><div class="evidence-list">${evidence||'<p>Brak cytatów do pokazania.</p>'}</div><p class="small-note">Cytat oznacza tylko obecność zdania w pliku, nie potwierdzenie jego prawdziwości.</p></details>
      <button type="button" class="btn btn-primary" data-action="use-discovered" data-index="${index}">Sprawdź pola i dodaj do katalogu</button></article>`;
  }).join('')||'';
  const content=heading('DISCOVERY ENGINE','Wykryj innowacje w dokumentach','Wczytaj kilka lokalnych plików. Reguły wykrywają opisane pomysły, a Ty decydujesz, co trafi do katalogu.')+
    `<div class="detail-grid"><section class="detail-card"><h2>01 / Wybierz dokumenty</h2><p>Pliki są analizowane wyłącznie w przeglądarce. Obsługiwane: tekstowe PDF, TXT i MD. Maksymalnie 15 dokumentów po 10 MB.</p>
    <div class="field"><label for="discovery-files">Dokumenty z opisami innowacji</label><input type="file" id="discovery-files" accept=".pdf,.txt,.md,application/pdf,text/plain,text/markdown" multiple><small>Skan bez warstwy tekstowej może wymagać ręcznego przepisania.</small></div>
    <div class="field" style="margin-top:16px"><label for="discovery-text">Lub wklej opis innowacji</label><textarea id="discovery-text" class="text-extract" rows="4" placeholder="Tytuł: ...&#10;Problem: ...&#10;Rozwiązanie: ..."></textarea></div>
    <div class="buttons" style="margin-top:16px"><button type="button" class="btn btn-primary" data-action="run-discovery">Wykryj kandydatów</button><button type="button" class="btn" data-action="demo-discovery">Uruchom 2 przykłady</button></div>
    <div id="discovery-status" role="status" aria-live="polite"></div></section>
    <section class="detail-card"><h2>Jak działa silnik?</h2><ol class="discovery-steps"><li>Wykrywa nagłówki, np. <strong>Tytuł, Problem, Rozwiązanie</strong>.</li><li>Zachowuje fragmenty źródłowe i numer wiersza.</li><li>Podpowiada dziedziny i słowa kluczowe — do sprawdzenia.</li><li>Liczy wstępną ocenę, podobieństwo i dopasowanie do potrzeb.</li><li>Dopiero po Twojej decyzji zapisuje pomysł.</li></ol><div class="notice neutral">Brak generatywnej AI, wyszukiwania internetowego i weryfikacji praw autorskich. Materiały poufne i dane osobowe nie powinny trafiać do tego prototypu.</div></section></div>
    ${report?`<section class="discovery-report" aria-label="Wyniki wykrywania"><div class="section-head"><div><h2>02 / Kandydaci do oceny <span class="counter">${report.candidates.length}</span></h2><p>Sprawdzono ${report.documents_count} dokumentów. Niczego nie zapisano automatycznie.</p></div></div>${report.warnings.length?`<div class="notice">${report.warnings.map(e).join(' ')}</div>`:''}
      ${candidateCards||'<div class="empty">Nie wykryto kandydatów z rozpoznanym tytułem i rozwiązaniem. Spróbuj opisu z nagłówkami lub wpisz dane ręcznie.</div>'}
      <p class="small-note">Metoda: ${e(report.method)}. ${e(report.disclaimer)}</p></section>`:''}`;
  shell(content,'/discovery','Wykrywanie');
}
async function runDiscovery(documents) {
  const report=await api('/api/discovery/analyze',{method:'POST',body:JSON.stringify({documents})});
  state.discovery=report;discoveryPage();
  document.getElementById?.('page-title')?.focus?.({preventScroll:true});
  window.scrollTo(0,0);
}

function onlinePage() {
  const report=state.online;
  const errors=report?.errors||[];
  const cards=report?.candidates.map((item,index)=>{
    const r=item.record,a=item.assessment,inn=item.fields;
    const original=window.RadarOnlineSearch.safeHttps(r.url);
    const matchRows=item.matches.slice(0,3).map(m=>`<li>${e(m.need.title)} — ${m.match_score==null?'brak pełnej oceny':m.match_score+' / 100*'} · ${e(m.reasons.join(' '))}</li>`).join('');
    return `<article class="detail-card online-result">
      <div class="discovery-result-head"><span class="tag ${r.source_type==='live_api'?'tag-good':'tag-slate'}">${r.source_type==='live_api'?'OPENALEX · API NA ŻYWO':'NCBR · PRÓBKA 21.11.2026'}</span><span class="small-note">${e(r.record_type)} · ${e(r.published_at||'brak daty publikacji')}</span></div>
      <h3>${e(r.title)}</h3><p class="small-note">${e(r.organization_name||'Organizacja nieznana')}</p>
      ${r.problem?`<p><strong>Problem:</strong> ${e(r.problem)}</p>`:''}
      <p><strong>${r.record_type==='research_work'?'Abstrakt:':'Opis projektu:'}</strong> ${e(cut(r.description||'Nie znaleziono abstraktu — uzupełnij informacje ręcznie.',1100))}</p>
      <div class="notice neutral">${e(r.notice)} Odczyt nie potwierdza transferowalności ani nowości.</div>
      <div class="discovery-metrics"><div><strong>${a.score===null?'—':a.score+' / 100'}</strong><small>Ocena wstępna · pokrycie ${Math.round(a.coverage*100)}%</small></div>
        <div><strong>${item.matches.length}</strong><small>Potencjalne potrzeby</small></div><div><strong>${item.similar.length}</strong><small>Podobne wpisy lokalne</small></div></div>
      <details class="discovery-details"><summary>Ocena, dopasowania i plan weryfikacji</summary>
        <ul>${a.dimensions.map(d=>`<li>${e(d.label)}: ${d.grade===null?'brak danych':d.grade+' / 4'}</li>`).join('')}</ul>
        <p class="small-note">${e(a.disclaimer)}</p><h4>Potencjalne potrzeby</h4><ul>${matchRows||'<li>Brak zgodności z lokalnym katalogiem potrzeb.</li>'}</ul>
        <h4>Następne kroki</h4><ol>${item.actions.map(t=>`<li>${e(t.title)} — ${e(t.success_check)}</li>`).join('')}</ol>
      </details>
      <div class="buttons online-actions"><a class="btn btn-secondary" target="_blank" rel="noopener noreferrer" href="${e(original)}">Otwórz źródło ↗</a>
      <button type="button" class="btn btn-primary" data-action="use-online" data-index="${index}" ${inn.solution.length<20?'disabled title="Brak opisu do analizy"':''}>Sprawdź i dodaj do katalogu</button></div>
      ${inn.solution.length<20?'<p class="small-note">Brak treści w rekordzie: otwórz źródło i dodaj pomysł ręcznie.</p>':''}
    </article>`;
  }).join('')||'';
  const sourceLine=report?.sources.map(x=>`${e(x.name)}: ${x.count} wyników ${x.live?'(na żywo)':'(zapisana próbka)'}`).join(' · ')||'';
  const content=heading('ONLINE DISCOVERY','Szukaj w internecie','Znajdź publikacje i projekty, a następnie zweryfikuj je w lokalnym silniku oceny i dopasowania.')+
    `<div class="detail-grid"><section class="detail-card"><h2>01 / Wyszukaj materiały</h2>
      <form data-form="search-online" id="online-form"><div class="field"><label for="online-query">Temat, problem lub technologia</label><input id="online-query" name="query" required minlength="3" maxlength="180" value="${e(state.onlineQuery)}" placeholder="np. nauczanie adaptacyjne"></div>
      <div class="field" style="margin-top:12px"><label for="online-source">Źródło</label><select id="online-source" name="source">
      <option value="both" ${state.onlineSource==='both'?'selected':''}>OpenAlex (API) + NCBR (lokalna próbka)</option>
      <option value="openalex" ${state.onlineSource==='openalex'?'selected':''}>OpenAlex — tylko API na żywo</option>
      <option value="ncbr" ${state.onlineSource==='ncbr'?'selected':''}>NCBR — tylko lokalna próbka 3 projektów</option>
      </select></div><div class="field" style="margin-top:12px"><label for="online-limit">Limit wyników na źródło</label><select id="online-limit" name="limit">${[5,8,10,15,20].map(n=>`<option value="${n}" ${state.onlineLimit===n?'selected':''}>${n}</option>`).join('')}</select></div>
      <div class="buttons" style="margin-top:14px"><button type="submit" class="btn btn-primary">Szukaj w źródłach</button></div><div id="online-status" role="status" aria-live="polite"></div></form></section>
      <section class="detail-card"><h2>Jak wykorzystujemy wyniki?</h2><ol class="discovery-steps"><li>OpenAlex udostępnia rekordy publikacji poprzez HTTP API.</li><li>NCBR jest na razie <strong>lokalną próbką 3 prawdziwych projektów</strong> z oficjalnych stron, nie bieżącą wyszukiwarką.</li><li>System normalizuje dane i usuwa powtórzenia.</li><li>Istniejący silnik ocenia dostępne pola, szuka analogów i potrzeb.</li><li>Użytkownik otwiera źródło, poprawia dane i sam zatwierdza zapis.</li></ol>
      <div class="notice neutral">Jeśli OpenAlex jest blokowany przez CORS lub brak sieci, próbka NCBR i cały tryb dokumentów działają nadal. Kluczy API nie wklejaj do aplikacji.</div></section></div>
    ${report?`<section class="discovery-report"><div class="section-head"><div><h2>02 / Wyniki <span class="counter">${report.candidates.length}</span></h2>
      <p>${e(report.query)} · ${sourceLine||'Źródła niedostępne'} · ${report.duplicates_count} powtórzeń usunięto</p></div></div>
      ${errors.map(err=>`<div class="notice online-error"><strong>${e(err.source_id)}:</strong> ${e(err.message)}</div>`).join('')}
      ${cards||'<div class="empty">Brak wyników dla tej frazy. Spróbuj innych słów lub wybierz drugie źródło.</div>'}
      <p class="small-note">${e(report.disclaimer)}</p></section>`:''}`;
  shell(content,'/online','Wyszukiwanie online');
}
async function runOnlineSearch(query,source,limit){
  state.onlineQuery=query;state.onlineSource=source;state.onlineLimit=limit;
  const sources=source==='both'?['openalex','ncbr']:[source];
  state.online=await window.RadarOnlineSearch.search(query,sources,limit);
  onlinePage();document.getElementById?.('page-title')?.focus?.({preventScroll:true});
  window.scrollTo(0,0);
}

async function navigate(route, replace=false) {
  if (!replace && location.hash !== '#'+route) { location.hash = route; return; }
  root.innerHTML = '<div class="loading"><span class="spinner"></span>Wczytywanie…</div>';
  try {
    if (route==='/') await dashboard();
    else if (route==='/innovations') await innovationsList();
    else if (route==='/discovery') discoveryPage();
    else if (route==='/online') onlinePage();
    else if (route==='/needs') await needsList();
    else if (route==='/innovations/new') innovationForm();
    else if (route==='/needs/new') needForm();
    else if (/^\/innovations\/[a-z0-9-]+$/i.test(route)) await innovationDetail(route.split('/')[2]);
    else if (/^\/needs\/[a-z0-9-]+$/i.test(route)) await needDetail(route.split('/')[2]);
    else pageError(new Error('Nie znaleziono strony.'));
  } catch(err) {pageError(err);}
  document.getElementById?.('page-title')?.focus?.({preventScroll:true});
  window.scrollTo(0,0);
}
function formObject(form) {
  const result = Object.fromEntries(new FormData(form).entries());
  for (const key of ['domain_tags','target_groups','keywords']) result[key] = result[key]?.split(',').map((part)=>part.trim()).filter(Boolean) || [];
  return result;
}
function inlineError(message) {const slot=document.querySelector('#form-error'); if (slot) slot.innerHTML=`<div class="form-alert">${e(message)}</div>`;}
document.addEventListener('click',async (event)=>{
  const link=event.target.closest('a[data-nav]');
  if(link) { event.preventDefault(); await navigate(link.dataset.nav); return; }
  const act=event.target.closest('[data-action]');
  if(act?.dataset.action==='use-online') {
    const item=state.online?.candidates[Number(act.dataset.index)];if(!item)return;
    state.draft={...item.fields};state.sourceEvidence=item.evidence;state.sourceName=item.source_name;state.sourceMeta={
      source_url:item.fields.source_url,source_provider:item.fields.source_provider,source_identifier:item.fields.source_identifier,
      source_published_at:item.fields.source_published_at,source_retrieved_at:item.fields.source_retrieved_at};
    state.sourceMode='online';state.extracted=null;state.isDemo=false;await navigate('/innovations/new');return;
  }
  if(act?.dataset.action==='use-discovered') {
    const idx=Number(act.dataset.index);
    const item=state.discovery?.candidates[idx];
    if(!item)return;
    state.draft={...item.fields};state.sourceEvidence=item.evidence;
    state.sourceName=item.source_name;state.isDemo=Boolean(item.fields.is_demo);
    state.sourceMode='discovery';state.sourceMeta={};state.extracted=null;
    await navigate('/innovations/new');return;
  }
  if(act?.dataset.action==='demo-discovery') {
    try{await runDiscovery(demoDiscoveryDocuments());}
    catch(err){alert(err.message)}return;
  }
  if(act?.dataset.action==='run-discovery') {
    const input=document.querySelector('#discovery-files');
    const pasted=document.querySelector('#discovery-text')?.value.trim()||'';
    const files=Array.from(input?.files||[]);
    if(!files.length&&!pasted){alert('Wybierz dokumenty lub wklej tekst.');return;}
    if(files.length+(pasted?1:0)>15){alert('Można przeanalizować maksymalnie 15 dokumentów.');return;}
    act.disabled=true;act.textContent='Wykrywanie…';
    const status=document.querySelector('#discovery-status');
    try{
      const docs=[];
      for(const file of files){
        if(file.size>10_000_000)throw new Error('Plik '+file.name+' przekracza 10 MB.');
        const isPdf=/\.pdf$/i.test(file.name);
        if(!isPdf&&!/\.(txt|md)$/i.test(file.name))throw new Error('Nieobsługiwany format: '+file.name);
        const text=isPdf?await window.RadarPdf.textFromPdf(file):await file.text();
        docs.push({name:file.name,text});
      }
      if(pasted)docs.push({name:'Wklejony tekst',text:pasted});
      await runDiscovery(docs);
    } catch(err){if(status)status.innerHTML='<div class="form-alert">'+e(err.message)+'</div>';act.disabled=false;act.textContent='Wykryj kandydatów';}
    return;
  }
  if(act?.dataset.action==='open-folder') {
    try { const opened=await window.RadarStore.openFolder();if(opened)await navigate(location.hash.slice(1)||'/',true); }
    catch(err) {if(err.name !== 'AbortError')alert(err.message);}
    return;
  }
  if(act?.dataset.action==='export') {
    try { window.RadarStore.downloadBackup(); }
    catch(err) { alert(err.message); }
    return;
  }
  if(act?.dataset.action==='import') {
    document.querySelector('#json-import')?.click(); return;
  }
  if(act?.dataset.action==='extract') {
    const doc=document.querySelector('#pdf-input')?.files?.[0];
    const text=document.querySelector('#extract-text')?.value || '';
    if(!doc&&!text.trim()) {alert('Wybierz PDF lub wpisz tekst.');return;}
    act.disabled=true; act.textContent='Analizowanie…';
    const inputs=document.querySelector('#innovation-form');
    if(inputs) state.draft=Object.fromEntries(new FormData(inputs).entries());
    try {
      let data;
      if(doc) {
        if(doc.size>10_000_000) throw new Error('PDF może mieć maksymalnie 10 MB.');
        data=await api('/api/innovations/extract',{method:'POST',headers:{'Content-Type':'application/pdf'},body:doc});
        state.sourceMode='pdf';
      } else {
        data=await api('/api/innovations/extract',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text})});
        state.sourceMode='form';
      }
      state.extracted=data;
      state.sourceEvidence=[];state.sourceName='';state.isDemo=false;
      state.draft={...state.draft,...data.fields};
      innovationForm();
    } catch(err) {alert(err.message);act.disabled=false;act.textContent='⌁ Analizuj i uzupełnij formularz';}
  }
});
document.addEventListener('submit', async (event)=>{
  const form=event.target;
  if(!form.matches('form[data-form]'))return;
  event.preventDefault();
  const action=form.dataset.form;
  if(action==='search-innovations') {const q=new FormData(form).get('q'); await innovationsList(String(q||''));return;}
  if(action==='search-needs') {const q=new FormData(form).get('q');await needsList(String(q||''));return;}
  if(action==='search-online') {
    const values=new FormData(form);const query=String(values.get('query')||'').trim();
    const source=String(values.get('source')||'both');const limit=Number(values.get('limit')||8);
    const button=form.querySelector('button[type="submit"]');if(button){button.disabled=true;button.textContent='Wyszukiwanie…';}
    try{await runOnlineSearch(query,source,limit);}catch(err){const slot=document.querySelector('#online-status');if(slot)slot.innerHTML='<div class="form-alert">'+e(err.message)+'</div>';if(button){button.disabled=false;button.textContent='Szukaj w źródłach';}}return;
  }
  const button=form.querySelector('button[type="submit"]'); if(button)button.disabled=true;
  try {
    const payload=formObject(form);
    if(action==='new-innovation'){
      payload.source_mode=state.sourceMode;
      if(state.sourceMode==='discovery'||state.sourceMode==='online') {payload.source_evidence=state.sourceEvidence;payload.source_name=state.sourceName;payload.is_demo=state.isDemo;}
      if(state.sourceMode==='online') Object.assign(payload,state.sourceMeta);
      const response=await api('/api/innovations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      state.draft={};state.extracted=null;state.sourceMode='form';state.sourceEvidence=[];state.sourceName='';state.sourceMeta={};state.isDemo=false;await navigate('/innovations/'+response.innovation.id);
    } else if(action==='new-need'){
      const response=await api('/api/needs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      await navigate('/needs/'+response.need.id);
    }
  } catch(err) {inlineError(err.message);if(button)button.disabled=false;}
});
document.addEventListener('change', async (event) => {
  if(event.target?.id !== 'json-import') return;
  const file = event.target.files?.[0]; if(!file) return;
  try {
    const text = await file.text();
    const parsed = JSON.parse(text);
    if(!confirm('Import zastąpi własne lokalne wpisy. Kontynuować?')) return;
    await window.RadarStore.restoreBackup(parsed);
    await navigate('/',true);
    alert('Dane zaimportowano.');
  } catch (err) { alert('Import nieudany: '+err.message); }
  finally { event.target.value = ''; }
});
window.addEventListener('hashchange',()=>navigate(location.hash.slice(1) || '/',true));
navigate(location.hash.slice(1) || '/',true);
