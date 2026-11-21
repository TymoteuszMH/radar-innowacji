'use strict';
/* Local adapter mirroring the former REST endpoints. No network requests. */
(() => {
  const { calculateAssessment } = window.RadarAssessment;
  const { findSimilarInnovations, getMatchesForInnovation, getMatchesForNeed } = window.RadarMatching;
  const { nextSteps } = window.RadarActions;
  const { previewExtract } = window.RadarAnalysis;
  const { analyzeDocuments } = window.RadarDiscovery;
  function clean(value, max=1000) { return typeof value==='string' ? value.trim().slice(0,max) : ''; }
  function tags(value, max=10) {
    if(!Array.isArray(value)) return [];
    return [...new Set(value.map(x=>clean(x,40).toLowerCase()).filter(Boolean))].slice(0,max);
  }
  function required(condition,message) {if(!condition) throw new Error(message);}
  function uid() {
    if(typeof crypto!=='undefined' && crypto.randomUUID) return crypto.randomUUID();
    const values=new Uint8Array(16);crypto.getRandomValues(values);
    return [...values].map(x=>x.toString(16).padStart(2,'0')).join('');
  }
  function addOrganization(body) {
    const name=clean(body.organization_name,140);
    required(name.length>=3,'Podaj nazwę organizacji (min. 3 znaki).');
    return {id:uid(),name,type:'public_other',region:'',is_demo:false,verified:false};
  }
  function httpsUrl(value) { try { const u=new URL(value);return u.protocol==='https:'?u.href.slice(0,1500):''; }catch{return '';} }
  function innovationPayload(body,org) {
    required(body && typeof body==='object' && !Array.isArray(body),'Niepoprawne dane.');
    const title=clean(body.title,160), problem=clean(body.problem,1800), solution=clean(body.solution,2500);
    required(title.length>=6 && problem.length>=20 && solution.length>=20,'Wymagane: tytuł (min. 6), problem i rozwiązanie (min. 20 znaków).');
    return {
      id:uid(),organization_id:org.id,title,problem,solution,
      domain_tags:tags(body.domain_tags), target_groups:tags(body.target_groups),
      innovation_type:['technical','organizational','educational','social','process'].includes(body.innovation_type)?body.innovation_type:'process',
      stage:['concept','prototype','pilot','implemented'].includes(body.stage)?body.stage:'concept',
      claimed_impact:clean(body.claimed_impact,1400),requirements:clean(body.requirements,1400),keywords:tags(body.keywords,12),
      is_demo:body.is_demo===true,source_mode:['pdf','discovery','online'].includes(body.source_mode)?body.source_mode:'form',
      source_evidence:window.RadarEvidence.forRecord(body.source_evidence,{title,problem,solution,claimed_impact:clean(body.claimed_impact,1400),requirements:clean(body.requirements,1400)}),
      source_name:clean(body.source_name,160),discovery_method:body.source_mode==='online'?'external-source-v0.5':(body.source_mode==='discovery'?'rules-v0.4':null),
      source_url:body.source_mode==='online'?httpsUrl(body.source_url):'',
      source_provider:body.source_mode==='online'?clean(body.source_provider,40):'',
      source_identifier:body.source_mode==='online'?clean(body.source_identifier,120):'',
      source_published_at:body.source_mode==='online'?clean(body.source_published_at,16):'',
      source_retrieved_at:body.source_mode==='online'?clean(body.source_retrieved_at,40):'',
      review_status:'draft',visibility:'private',created_at:new Date().toISOString()
    };
  }
  function needPayload(body,org) {
    required(body && typeof body==='object' && !Array.isArray(body),'Niepoprawne dane.');
    const title=clean(body.title,160),problem=clean(body.problem,1800);
    required(title.length>=6 && problem.length>=20,'Wymagane: tytuł (min. 6) oraz opis potrzeby (min. 20 znaków).');
    return {
      id:uid(),organization_id:org.id,title,problem,context:clean(body.context,1200),
      domain_tags:tags(body.domain_tags),target_groups:tags(body.target_groups),
      constraints:clean(body.constraints,1200),desired_outcome:clean(body.desired_outcome,1200),
      minimum_stage:['concept','prototype','pilot','implemented'].includes(body.minimum_stage)?body.minimum_stage:'concept',
      keywords:tags(body.keywords,12),is_demo:false,verified:false,visibility:'private',created_at:new Date().toISOString()
    };
  }
  function innovationDetail(innovation,store) {
    const assessment=calculateAssessment(innovation);
    const similar=findSimilarInnovations(innovation,store.innovations,3);
    const matches=getMatchesForInnovation(innovation,store.needs,5);
    return {innovation,assessment,similar,matches,actions:nextSteps(innovation,assessment,matches,similar),
      evidence:window.RadarEvidence.summarize(innovation),organizations:store.organizations};
  }
  async function request(endpoint,options={}) {
    const url=new URL(endpoint,'https://local.invalid');
    const path=url.pathname;
    const method=(options.method || 'GET').toUpperCase();
    const store=window.RadarStore.all();
    if(method==='GET' && path==='/api/dashboard') {
      const featured=store.innovations.slice(0,10).map(i=>({innovation:i,matches:getMatchesForInnovation(i,store.needs,1)}))
        .filter(x=>x.matches.length).sort((a,b)=>(b.matches[0].match_score??-1)-(a.matches[0].match_score??-1)).slice(0,4);
      return {counts:{innovations:store.innovations.length,needs:store.needs.length,organizations:store.organizations.length},featured,recent:store.innovations.slice(0,6),organizations:store.organizations};
    }
    if(method==='GET' && path==='/api/innovations') {
      const q=(url.searchParams.get('q')||'').toLocaleLowerCase('pl');
      const items=store.innovations.filter(i=>!q || [i.title,i.problem,i.solution,...(i.domain_tags||[])].join(' ').toLocaleLowerCase('pl').includes(q));
      return {items,organizations:store.organizations,total:items.length};
    }
    if(method==='GET' && path==='/api/needs') {
      const q=(url.searchParams.get('q')||'').toLocaleLowerCase('pl');
      const items=store.needs.filter(n=>!q || [n.title,n.problem,n.desired_outcome,...(n.domain_tags||[])].join(' ').toLocaleLowerCase('pl').includes(q));
      return {items,organizations:store.organizations,total:items.length};
    }
    if(method==='POST' && path==='/api/discovery/analyze') {
      let body;try{body=JSON.parse(options.body);}catch{throw new Error('Niepoprawne dokumenty do analizy.');}
      const report=analyzeDocuments(body.documents);
      const candidates=report.candidates.map(candidate=>{
        const i=candidate.fields;
        const assessment=calculateAssessment(i);
        const similar=findSimilarInnovations(i,store.innovations,3);
        const matches=getMatchesForInnovation(i,store.needs,5);
        return {...candidate,assessment,similar,matches,actions:nextSteps(i,assessment,matches,similar)};
      });
      return {...report,candidates,organizations:store.organizations};
    }
    if(method==='POST' && path==='/api/innovations/extract') {
      const data=options.body;
      if((typeof File!=='undefined' && data instanceof File) || data instanceof Blob) {
        if(data.size>10_000_000) throw new Error('PDF może mieć maksymalnie 10 MB.');
        const raw=await window.RadarPdf.textFromPdf(data);
        return previewExtract(raw,'przesłany dokument.pdf');
      }
      let body;
      try { body=JSON.parse(data); } catch { throw new Error('Niepoprawny tekst dokumentu.'); }
      required(typeof body.text==='string' && body.text.length<=150_000,'Wymagany tekst do 150 000 znaków.');
      return previewExtract(body.text);
    }
    if(method==='POST' && path==='/api/innovations') {
      let body; try{body=JSON.parse(options.body);}catch{throw new Error('Niepoprawny JSON.');}
      const org=addOrganization(body),innovation=innovationPayload(body,org);
      await window.RadarStore.commit('innovations',innovation,org);
      return {innovation,assessment:calculateAssessment(innovation)};
    }
    if(method==='POST' && path==='/api/needs') {
      let body;try{body=JSON.parse(options.body);}catch{throw new Error('Niepoprawny JSON.');}
      const org=addOrganization(body),need=needPayload(body,org);
      await window.RadarStore.commit('needs',need,org);
      return {need};
    }
    const inn=path.match(/^\/api\/innovations\/([a-zA-Z0-9-]+)$/);
    if(method==='GET' && inn) {
      const i=store.innovations.find(x=>x.id===inn[1]);
      required(i,'Nie znaleziono innowacji.');return innovationDetail(i,store);
    }
    const ne=path.match(/^\/api\/needs\/([a-zA-Z0-9-]+)$/);
    if(method==='GET' && ne) {
      const n=store.needs.find(x=>x.id===ne[1]);
      required(n,'Nie znaleziono potrzeby.');
      return {need:n,matches:getMatchesForNeed(n,store.innovations,7),organizations:store.organizations};
    }
    throw new Error('Nieobsługiwana operacja lokalna: '+method+' '+path);
  }
  window.RadarLocalApi=Object.freeze({request});
})();
