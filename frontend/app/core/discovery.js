'use strict';
/* Transparent rule-based discovery from local text sources, not generative AI. */
(() => {
  const HEADERS = Object.freeze({
    title:/^(?:tytuł|tytul|nazwa projektu|projekt|innowacja)\s*[:–-]\s*(.*)$/i,
    problem:/^(?:problem|wyzwanie|potrzeba)\s*[:–-]\s*(.*)$/i,
    solution:/^(?:rozwiązanie|rozwiazanie|proponowane rozwiązanie|opis rozwiązania|opis pomysłu)\s*[:–-]\s*(.*)$/i,
    claimed_impact:/^(?:efekt|rezultat|wpływ|wplyw|zakładany efekt)\s*[:–-]\s*(.*)$/i,
    requirements:/^(?:wymagania|warunki wdrożenia|warunki transferu)\s*[:–-]\s*(.*)$/i,
    organization_name:/^(?:organizacja|instytucja|autor projektu)\s*[:–-]\s*(.*)$/i
  });
  const hints = [
    {pattern:/uczni|szkoł|szkol|nauczy|edukac|lekcj|nauk/i, domains:['edukacja','nauka'], groups:['uczniowie','nauczyciele'], type:'educational'},
    {pattern:/gmin|samorząd|samorzad|miejsk|urzę|urze/i, domains:['samorząd'], groups:['samorządy'], type:'organizational'},
    {pattern:/odpad|śmieci|smieci|segregac|pojemnik/i, domains:['środowisko','logistyka'], groups:['samorządy'], type:'process'},
    {pattern:/pojazd|tras|transport|logist/i, domains:['logistyka'], groups:[], type:'process'},
    {pattern:/energia|energii|licznik|zużyc|zuzyc/i, domains:['energia'], groups:['zarządcy'], type:'technical'},
    {pattern:/czujnik|powietrz|pył|pyl/i, domains:['środowisko','iot'], groups:[], type:'technical'}
  ];
  const termHints=[
    ['powtórki',/powt[oó]r/i],['zaległości',/zaległ|zalegl/i],['nauka',/nauk/i],['uczniowie',/uczni/i],
    ['odpady',/odpad/i],['trasy',/tras/i],['transport',/transport|pojazd/i],['pojazdy',/pojazd/i],
    ['energia',/energ/i],['budynki',/budyn/i],['liczniki',/licznik/i],['zużycie',/zużyc|zuzyc/i],
    ['powietrze',/powietrz/i],['czujniki',/czujnik/i],['pyły',/pył|pyl/i],['szkoły',/szkoł|szkol/i],
    ['kolejka',/kolejk/i],['urząd',/urz[aąęe]d|urzę/i],['wizyty',/wizyt/i],['obsługa',/obsług|obslug/i]
  ];
  function infer(text) {
    const domain_tags=[], target_groups=[];
    let innovation_type='process';
    let typeAssigned=false;
    for (const rule of hints) if (rule.pattern.test(text)) {
      for(const tag of rule.domains) if(!domain_tags.includes(tag))domain_tags.push(tag);
      for(const group of rule.groups) if(!target_groups.includes(group))target_groups.push(group);
      if(!typeAssigned){innovation_type=rule.type;typeAssigned=true;}
    }
    const keywords=termHints.filter(([,regex])=>regex.test(text)).map(([term])=>term).slice(0,10);
    return {domain_tags:domain_tags.slice(0,8),target_groups:target_groups.slice(0,6),innovation_type,keywords};
  }
  function candidateSections(lines) {
    const indexes=[];
    lines.forEach((line,i)=>{if(HEADERS.title.test(line.trim())) indexes.push(i);});
    if(indexes.length===0)return [{start:0,end:lines.length}];
    return indexes.map((start,i)=>({start,end:indexes[i+1]??lines.length}));
  }
  function parseSection(lines, start, end, sourceName, sectionIndex, isDemo=false, docNumber=0) {
    const fields={}, evidence=[];let active=null;
    for(let i=start;i<end;i++) {
      const line=lines[i].trim();if(!line)continue;
      const header=Object.entries(HEADERS).find(([,pattern])=>pattern.test(line));
      if(header) {
        const [key,pattern]=header;
        const content=line.match(pattern)?.[1]?.trim()||'';
        active=key;
        if(content) {
          fields[key]=content.slice(0,key==='solution'?2500:1800);
          if(window.RadarEvidence && key!=='organization_name') {
            const ref=window.RadarEvidence.excerpt(key,content,line,i+1,sourceName);
            if(ref)evidence.push(ref);
          }
        }
      } else if(active && !fields[active] && line.length<1600) {
        fields[active]=line.slice(0,1600);
        if(window.RadarEvidence && active!=='organization_name') {
          const ref=window.RadarEvidence.excerpt(active,line,line,i+1,sourceName);
          if(ref)evidence.push(ref);
        }
      } else active=null; // Do not silently turn unrelated paragraphs into facts.
    }
    const missing=['title','problem','solution'].filter(key=>!fields[key] || fields[key].length<(key==='title'?6:18));
    if(missing.includes('title') || missing.includes('solution'))return {rejected:{source_name:sourceName,section:sectionIndex+1,reason:'Nie znaleziono rozpoznawalnego tytułu i opisu rozwiązania.'}};
    const inferred=infer([fields.title,fields.problem,fields.solution].join(' '));
    const candidate={
      title:fields.title,problem:fields.problem||'',solution:fields.solution,
      claimed_impact:fields.claimed_impact||'',requirements:fields.requirements||'',
      organization_name:fields.organization_name||'',...inferred,stage:'concept',is_demo:Boolean(isDemo),
      source_mode:'discovery',source_name:sourceName,
      source_evidence:evidence,discovery_method:'rules-v0.4',
      review_status:'requires_review'
    };
    return {candidate:{id:`candidate-${docNumber+1}-${sectionIndex+1}`,source_name:sourceName,section:sectionIndex+1,fields:candidate,
      completeness:missing.length?'niepełny':'kompletne podstawowe pola',
      warnings:[...(missing.length?[`Brakuje: ${missing.join(', ')}. Uzupełnij przed zapisaniem.`]:[]),
        'Dziedziny, słowa kluczowe i typ są podpowiedziami z reguł, nie ustalonymi faktami.',
        'Etap „Koncepcja” to wartość domyślna. Sprawdź faktyczny stan prac.',
        'Cytaty potwierdzają obecność stwierdzeń w dokumencie, nie ich prawdziwość.'],
      evidence, method:'nagłówki + słownik dziedzin'}};
  }
  function analyzeDocuments(documents) {
    if(!Array.isArray(documents)||!documents.length||documents.length>15)throw new Error('Wybierz od 1 do 15 dokumentów.');
    const candidates=[], rejected=[], warnings=[];
    for (const [docNo,doc] of documents.entries()) {
      if(!doc || typeof doc.text!=='string'||doc.text.length>150_000)throw new Error('Dokument może zawierać najwyżej 150 000 znaków.');
      const sourceName=String(doc.name||`Dokument ${docNo+1}`).slice(0,160);
      const lines=doc.text.replace(/\r/g,'').split('\n');
      if(lines.length>10000)throw new Error('Zbyt wiele wierszy w dokumencie.');
      const before=candidates.length;
      for(const [sectionIndex,chunk] of candidateSections(lines).entries()) {
        const result=parseSection(lines,chunk.start,chunk.end,sourceName,sectionIndex,Boolean(doc.is_demo),docNo);
        if(result.candidate)candidates.push(result.candidate);
        else if(result.rejected)rejected.push(result.rejected);
      }
      if(candidates.length===before)warnings.push(`${sourceName}: brak kandydata z rozpoznanym tytułem i rozwiązaniem.`);
    }
    return {
      candidates:candidates.slice(0,50),rejected,warnings,documents_count:documents.length,
      method:'deterministic_offline_rules',
      disclaimer:'To wykrywanie wzorców w tekstach, nie autonomiczna ocena nowości ani przeszukiwanie internetu. Każdy kandydat wymaga decyzji człowieka.'
    };
  }
  window.RadarDiscovery=Object.freeze({analyzeDocuments,infer});
})();
