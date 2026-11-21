'use strict';
/* Provenance verifies that a phrase appears in supplied text; it never verifies truth. */
(() => {
  const FIELDS = Object.freeze(['title','problem','solution','claimed_impact','requirements']);
  const normalize = (value) => String(value ?? '').normalize('NFC').replace(/\s+/g,' ').trim().toLocaleLowerCase('pl');
  function excerpt(field, value, line, lineNumber, sourceName) {
    if (!FIELDS.includes(field) || typeof value !== 'string' || !value.trim() || !line) return null;
    const quoted = String(line).trim().slice(0,1400);
    if (!normalize(quoted).includes(normalize(value))) return null;
    return {
      field, source_name:String(sourceName || 'Dokument').slice(0,160),
      line_number:lineNumber, quote:quoted,
      evidence_status:'present_in_source_unverified'
    };
  }
  function forRecord(records, fields) {
    if (!Array.isArray(records)) return [];
    const seen = new Set();
    return records.filter((record) => {
      if (!record || !FIELDS.includes(record.field) || !fields[record.field]) return false;
      if (typeof record.source_name !== 'string' || typeof record.quote !== 'string') return false;
      const online = record.evidence_type === 'online_metadata' && /^https:\/\/[^\s]+$/.test(record.source_url||'');
      if (!online && (!Number.isInteger(record.line_number) || record.line_number < 1)) return false;
      const value=normalize(fields[record.field]);
      const quote=normalize(record.quote);
      if (!value || !quote.includes(value)) return false;
      const key=record.field+'|'+record.source_name+'|'+(online?record.source_url:record.line_number);
      if (seen.has(key)) return false;
      seen.add(key); return true;
    }).slice(0,25).map((r) => ({
      field:r.field, source_name:r.source_name.slice(0,160),
      line_number:r.evidence_type==='online_metadata'?null:r.line_number, quote:r.quote.slice(0,1400),
      source_url:r.evidence_type==='online_metadata'?r.source_url:undefined, evidence_type:r.evidence_type==='online_metadata'?'online_metadata':'document_line',
      evidence_status:'present_in_source_unverified'
    }));
  }
  function summarize(innovation) {
    const records=forRecord(innovation.source_evidence,innovation);
    const sourced=new Set(records.map(r=>r.field));
    return {records, sourced_fields:[...sourced], missing_fields: FIELDS.filter(f => innovation[f] && !sourced.has(f)),
      disclaimer:'Cytat potwierdza obecność opisu w dokumencie, nie prawdziwość deklaracji ani skuteczność innowacji.'};
  }
  window.RadarEvidence=Object.freeze({FIELDS,excerpt,forRecord,summarize});
})();
