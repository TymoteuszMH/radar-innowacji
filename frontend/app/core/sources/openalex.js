'use strict';
/* Public OpenAlex Works API. Works are research records, NOT validated innovations. */
(() => {
  const BASE = 'https://api.openalex.org/works';
  function abstractFromIndex(index, max=3200) {
    if (!index || typeof index !== 'object' || Array.isArray(index)) return '';
    const terms = [];
    for (const [word, positions] of Object.entries(index)) {
      if (!Array.isArray(positions)) continue;
      for (const pos of positions) if (Number.isInteger(pos) && pos >= 0 && pos < 1500) terms.push([pos,word]);
    }
    return terms.sort((a,b)=>a[0]-b[0]).slice(0,600).map(p=>p[1]).join(' ').slice(0,max);
  }
  function safeUrl(value) {
    if (typeof value !== 'string') return '';
    try { const u=new URL(value);return u.protocol==='https:'?u.href:''; } catch { return ''; }
  }
  function convert(work, retrievedAt) {
    if (!work || typeof work !== 'object') return null;
    const title=String(work.display_name||work.title||'').trim().slice(0,160);
    const id=String(work.id||'').match(/W\d{3,}/)?.[0]||'';
    if (!id || title.length<6) return null;
    const url=safeUrl(work.id)||`https://openalex.org/${id}`;
    const source=work.primary_location?.source?.display_name||'';
    const authorships=Array.isArray(work.authorships)?work.authorships:[];
    const organizations=[...new Set(authorships.flatMap(a=>(Array.isArray(a.institutions)?a.institutions:[]).map(i=>i?.display_name)).filter(Boolean))].slice(0,3);
    const abstract=abstractFromIndex(work.abstract_inverted_index);
    const doi=safeUrl(work.doi||'');
    return {
      source_id:'openalex', source_label:'OpenAlex', source_type:'live_api',
      record_id:id, record_type:'research_work', title, description:abstract,
      organization_name:organizations.join(', ').slice(0,150),
      authors:authorships.slice(0,4).map(a=>a?.author?.display_name).filter(Boolean),
      url, doi, published_at:/^\d{4}-\d{2}-\d{2}$/.test(work.publication_date||'')?work.publication_date:'',
      retrieved_at:retrievedAt, publication_source:String(source).slice(0,160),
      text_available:Boolean(abstract),
      notice:abstract?'Abstrakt publikacji, nie opis potwierdzonego wdrożenia.':'Brak abstraktu w rekordzie API; analiza treści niemożliwa.',
      classification:'candidate_from_publication',
      provenance:'OpenAlex API /works'
    };
  }
  function buildUrl(query, limit) {
    const q=String(query||'').trim();
    if(q.length<3||q.length>180) throw new Error('Wpisz frazę o długości 3–180 znaków.');
    const n=Number(limit);
    if(!Number.isInteger(n)||n<1||n>20)throw new Error('Limit: 1–20 wyników.');
    const url=new URL(BASE);url.searchParams.set('search',q);url.searchParams.set('per_page',String(n));
    return url.href;
  }
  async function search(query,limit=8,opts={}) {
    const fetcher=opts.fetchImpl||globalThis.fetch;
    if(typeof fetcher!=='function')throw new Error('Ta przeglądarka nie obsługuje połączeń HTTP.');
    const address=buildUrl(query,limit);
    const controller=typeof AbortController==='function'?new AbortController():null;
    const timeout=typeof setTimeout==='function'&&controller?setTimeout(()=>controller.abort(),10000):null;
    try {
      const response=await fetcher(address,controller?{signal:controller.signal,headers:{Accept:'application/json'}}:{headers:{Accept:'application/json'}});
      if (!response?.ok) {
        if(response?.status===429)throw new Error('OpenAlex ograniczył liczbę zapytań (HTTP 429). Spróbuj później.');
        if(response?.status===401||response?.status===403)throw new Error('OpenAlex wymaga autoryzacji lub odmówił dostępu. Nie umieszczaj klucza API w pliku HTML.');
        throw new Error('OpenAlex nie udostępnił danych (HTTP '+String(response?.status||'?')+').');
      }
      const data=await response.json();
      if(!Array.isArray(data?.results))throw new Error('OpenAlex zwrócił nieoczekiwany format danych.');
      const retrievedAt=new Date().toISOString();
      return {source_id:'openalex',source_label:'OpenAlex — na żywo',live:true,query:qSafe(query),
        records:data.results.map(w=>convert(w,retrievedAt)).filter(Boolean).slice(0,limit),
        total_found:Number.isFinite(data.meta?.count)?data.meta.count:null,request_url:address};
    } catch(error) {
      if(error.name==='AbortError')throw new Error('OpenAlex nie odpowiedział w ciągu 10 sekund.');
      if(error instanceof TypeError)throw new Error('Połączenie z OpenAlex nie powiodło się. Możliwy brak internetu, CORS lub blokada pliku file://.');
      throw error;
    } finally {if(timeout!==null)clearTimeout(timeout);}
  }
  const qSafe=q=>String(q).trim().slice(0,180);
  window.RadarOpenAlex=Object.freeze({buildUrl,abstractFromIndex,convert,search});
})();
