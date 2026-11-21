'use strict';
/* Bridges externally sourced records into the existing deterministic engine. */
(() => {
 const SOURCE_LIST=Object.freeze([
  {id:'openalex',name:'OpenAlex',kind:'live_api',description:'Publiczne publikacje naukowe — wyszukiwanie na żywo'},
  {id:'ncbr',name:'NCBR',kind:'curated_snapshot',description:'3 sprawdzone polskie projekty — lokalny indeks, bez pobierania na żywo'}
 ]);
 const safeHttps=(raw)=>{try{const url=new URL(raw);return url.protocol==='https:'?url.href:'';}catch{return '';}};
 const normalizeTitle=t=>String(t||'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase('pl').replace(/[^\p{L}\p{N}]+/gu,' ').trim().slice(0,200);
 function deduplicate(records) {
   const visited=new Set();const duplicates=[];const unique=[];
   for(const item of records){
     const key=item.doi&&safeHttps(item.doi)?'doi:'+item.doi.toLowerCase():
       item.source_id+':'+item.record_id;
     const loose=normalizeTitle(item.title);
     if(visited.has(key)||(loose&&visited.has('title:'+loose))){duplicates.push(item);continue;}
     visited.add(key);if(loose)visited.add('title:'+loose);unique.push(item);
   }
   return {unique,duplicates};
 }
 function toCandidate(record) {
   if(!record || !safeHttps(record.url) || !record.title)return null;
   const solution=String(record.description||'').slice(0,2500);
   const problem=String(record.problem||'').slice(0,1800);
   const inferred=window.RadarDiscovery.infer([record.title,problem,solution].join(' '));
   const evidence=[];
   // A web record has no PDF line numbers. Title is the only exact field-value citation here.
   const titleQuote=String(record.title);
   evidence.push({field:'title',source_name:record.source_label,quote:titleQuote,source_url:record.url,
     evidence_status:'present_in_source_unverified',evidence_type:'online_metadata'});
   const fields={
     id:'web-'+String(record.source_id)+'-'+String(record.record_id), title:String(record.title).slice(0,160),
     problem,solution,claimed_impact:'',requirements:'',organization_name:String(record.organization_name||'').slice(0,150),
     innovation_type:inferred.innovation_type,domain_tags:inferred.domain_tags,target_groups:inferred.target_groups,
     keywords:inferred.keywords,stage:'concept',is_demo:false,review_status:'requires_review',
     source_mode:'online',source_name:record.source_label,source_evidence:evidence,
     source_url:record.url,source_provider:record.source_id,source_identifier:String(record.record_id).slice(0,120),
     source_published_at:record.published_at||'',source_retrieved_at:record.retrieved_at||'',
     discovery_method:'external-source-v0.5'
   };
   return {fields,evidence,source_name:record.source_label,record,
     warnings:[record.notice,'Nie potwierdzono nowości ani gotowości do transferu.','Kategoria i etap są orientacyjne. Sprawdź oryginalną stronę przed zapisem.']};
 }
 function enrich(record,store) {
   const candidate=toCandidate(record);if(!candidate)return null;
   const i=candidate.fields;
   const assessment=window.RadarAssessment.calculateAssessment(i);
   const similar=window.RadarMatching.findSimilarInnovations(i,store.innovations,3);
   const matches=window.RadarMatching.getMatchesForInnovation(i,store.needs,5);
   return {...candidate,assessment,similar,matches,actions:window.RadarActions.nextSteps(i,assessment,matches,similar)};
 }
 async function search(query, sources=['openalex','ncbr'],limit=8,options={}) {
   const trimmed=String(query||'').trim();
   if(trimmed.length<3||trimmed.length>180)throw new Error('Wpisz frazę o długości 3–180 znaków.');
   if(!Array.isArray(sources)||sources.length<1||sources.length>2||sources.some(id=>!SOURCE_LIST.some(s=>s.id===id)))throw new Error('Wybierz poprawne źródło.');
   if(!Number.isInteger(limit)||limit<1||limit>20)throw new Error('Limit wyników: 1–20.');
   const responses=[], errors=[];
   for(const name of [...new Set(sources)]) {
     try {
       const response=name==='openalex'?await window.RadarOpenAlex.search(trimmed,limit,options):window.RadarNCBR.search(trimmed,limit);
       responses.push(response);
     }catch(error){errors.push({source_id:name,message:error.message||'Błąd źródła.'});}
   }
   const {unique,duplicates}=deduplicate(responses.flatMap(r=>r.records));
   const store=window.RadarStore.all();
   const candidates=unique.map(item=>enrich(item,store)).filter(Boolean);
   return {query:trimmed,sources:responses.map(r=>({id:r.source_id,name:r.source_label,live:r.live,count:r.records.length,total:r.total_found??null})),
     candidates,duplicates_count:duplicates.length,errors,generated_at:new Date().toISOString(),
     method:'external_source_normalization_plus_offline_core',
     disclaimer:'Wyniki to publikacje lub opisy projektów, nie potwierdzone nowe innowacje. Ocena i dopasowania są heurystyczne. Zapis wyłącznie po weryfikacji człowieka.'};
 }
 window.RadarOnlineSearch=Object.freeze({SOURCE_LIST,safeHttps,deduplicate,toCandidate,enrich,search});
})();
