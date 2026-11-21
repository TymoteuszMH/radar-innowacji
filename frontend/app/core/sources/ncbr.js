'use strict';
/* Small verified public NCBR case-study index, curated on 2026-11-21.
   No scraping or live search; 'snapshot' is explicit in the UI. */
(() => {
 const INDEX=Object.freeze([
  {
   record_id:'ncbr-swiat-odkrywcow',title:'Świat odkrywców, odkrywanie świata – nowatorski program rozwoju kompetencji',
   organization_name:'Uniwersytet Wrocławski',
   problem:'Rozwijanie kompetencji kluczowych uczniów szkół podstawowych w wieku 11–15 lat.',
   description:'Opracowanie i wdrożenie programu edukacyjnego rozwijającego kompetencje oraz aktywność edukacyjną i kulturalną dzieci.',
   url:'https://www.gov.pl/web/ncbr/swiat-odkrywcow-odkrywanie-swiata--nowatorski-program-rozwoju-kompetencji-i-pobudzenia-aktywnosci-edukacyjnej-i-kulturalnej-dla-dzieci-szkol-podstawowych',
   excerpt:'Ideą projektu było opracowanie i wdrożenie nowatorskiego programu kształtowania kompetencji kluczowych u dzieci',
   category:'edukacja',date_range:'2018–2021'
  },
  {
   record_id:'ncbr-mooc-bydgoszcz',title:'Uczelnia kreatorem kompetencji kadr MŚP',
   organization_name:'Politechnika Bydgoska im. Jana i Jędrzeja Śniadeckich',
   problem:'Dostęp do praktycznej edukacji z zakresu funkcjonowania przedsiębiorstwa i rozwoju kompetencji zawodowych.',
   description:'Projekt obejmował przygotowanie siedmiu kursów e-learningowych MOOC udostępnionych na platformie NAVOICA.',
   url:'https://www.gov.pl/web/ncbr/uczelnia-kreatorem-kompetencji-kadr-msp',
   excerpt:'W efekcie zrealizowanego projektu powstało 7 kursów e-learningowych typu MOOC',
   category:'edukacja',date_range:'2020–2021'
  },
  {
   record_id:'ncbr-czujnik-swiatlowodowy',title:'Innowacyjny czujnik odkształceń na bazie specjalnych światłowodów mikrostrukturalnych',
   organization_name:'Polskie Centrum Fotoniki i Światłowodów',
   problem:'Monitorowanie odkształceń i poprawności działania urządzeń oraz infrastruktury przemysłowej.',
   description:'Światłowodowy czujnik do monitorowania odkształceń, umożliwiający rozróżnienie kierunku wygięcia badanego elementu.',
   url:'https://www.gov.pl/web/ncbr/innowacyjny-czujnik-odksztalcen-na-bazie-specjalnych-swiatlowodow-mikrostrukturalnych',
   excerpt:'Rezultatem projektu jest innowacyjny czujnik światłowodowy do monitorowania odkształceń',
   category:'technologia',date_range:'2016–2019'
  }
 ]);
 function search(query,limit=8) {
   const q=String(query||'').trim();if(q.length<3||q.length>180)throw new Error('Wpisz frazę o długości 3–180 znaków.');
   const words=q.toLocaleLowerCase('pl').split(/\s+/).filter(w=>w.length>2);
   const matches=INDEX.map(r=>({r,score:words.reduce((sum,word)=>sum+( [r.title,r.description,r.problem,r.organization_name,r.category].join(' ').toLocaleLowerCase('pl').includes(word)?1:0),0)}))
     .filter(item=>item.score>0).sort((a,b)=>b.score-a.score).slice(0,limit);
   return {source_id:'ncbr',source_label:'NCBR — próbka zweryfikowanych stron',live:false,query:q,records:matches.map(({r})=>({
     source_id:'ncbr',source_label:'NCBR',source_type:'curated_snapshot',record_id:r.record_id,
     record_type:'public_project',title:r.title,description:r.description,problem:r.problem,
     organization_name:r.organization_name,url:r.url,published_at:'',retrieved_at:'2026-11-21',
     evidence_excerpt:r.excerpt,notice:'Streszczenie przygotowane na podstawie oficjalnej strony. Dane pochodzą z próbki z 21.11.2026, nie z wyszukiwania na żywo.',
     classification:'public_project_candidate',provenance:'Katalog NCBR / gov.pl · kontrolowana próbka',text_available:true
   })), total_found:matches.length};
 }
 window.RadarNCBR=Object.freeze({INDEX,search});
})();
