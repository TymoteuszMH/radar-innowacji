'use strict';
/* Browser-local workspace. No server or external data transfer. */
(() => {
  const KEY = 'innovation-radar.workspace.v2';
  let memory = { organizations: [], innovations: [], needs: [] };
  let storageWarning = '';
  let folderHandle = null;
  let folderName = '';

  function clone(value) { return JSON.parse(JSON.stringify(value)); }
  function normalize(value) {
    if(!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Niepoprawny format kopii.');
    const result = {};
    for(const key of ['organizations','innovations','needs']) {
      if(!Array.isArray(value[key]) || value[key].length > 1000) throw new Error('Niepoprawne dane: '+key);
      result[key] = value[key].map(item => {
        if(!item || typeof item !== 'object' || Array.isArray(item)) throw new Error('Niepoprawny rekord.');
        if(typeof item.id !== 'string' || !/^[a-zA-Z0-9-]{1,80}$/.test(item.id)) throw new Error('Niepoprawny identyfikator.');
        if(key !== 'organizations' && (typeof item.title !== 'string' || item.title.length > 200)) throw new Error('Niepoprawny tytuł.');
        if(key === 'organizations' && (typeof item.name !== 'string' || item.name.length > 200)) throw new Error('Niepoprawna nazwa organizacji.');
        return item;
      });
    }
    return result;
  }
  try {
    const value = localStorage.getItem(KEY);
    if(value) memory = normalize(JSON.parse(value));
  } catch(e) { storageWarning = 'Dane nie mogą być zapisywane w pamięci przeglądarki; zrób eksport JSON.'; }
  function save() {
    try { localStorage.setItem(KEY, JSON.stringify(memory)); storageWarning=''; }
    catch(e) { storageWarning='Brak miejsca lub dostępu do zapisu lokalnego. Wyeksportuj kopię JSON.'; throw new Error(storageWarning); }
  }
  function all() {
    const s = clone(window.RadarSeed);
    for(const type of ['organizations','innovations','needs']) {
      const seeded=new Set(s[type].map(x=>x.id));
      s[type].push(...clone(memory[type]).filter(x=>!seeded.has(x.id)));
    }
    return s;
  }
  async function commit(type,record,org) {
    if(!['innovations','needs'].includes(type)) throw new Error('Nieznany typ.');
    const old = clone(memory);
    memory.organizations.push(org);
    memory[type].unshift(record);
    try { save(); } catch(err) { memory=old; throw err; }
    if(folderHandle) {
      try { await writeToFolder(); }
      catch(err) { storageWarning='Nie udało się zapisać pliku w folderze. Wyeksportuj kopię JSON.'; }
    }
  }
  function backup() { return {
    format:'innovation-radar-local-backup',version:2,created_at:new Date().toISOString(),
    data:clone(memory)
  }; }
  async function restoreBackup(value) {
    if(value?.format !== 'innovation-radar-local-backup' || value.version !== 2) throw new Error('Nieobsługiwana kopia danych.');
    const checked=normalize(value.data);
    const old=memory; memory=checked;
    try{save();}catch(err){memory=old;throw err;}
    if(folderHandle) await writeToFolder();
  }
  async function writeToFolder() {
    if(!folderHandle)return;
    const directory=await folderHandle.getDirectoryHandle('data',{create:true});
    const fileHandle=await directory.getFileHandle('workspace.json',{create:true});
    const file=await fileHandle.createWritable();
    try {await file.write(JSON.stringify(backup(),null,2));await file.close();}
    catch(err){try{await file.abort();}catch{}throw err;}
  }
  async function openFolder() {
    if(!window.showDirectoryPicker) throw new Error('Twoja przeglądarka nie obsługuje wyboru folderu. Użyj Chrome lub Edge, albo eksportu JSON.');
    const selected=await window.showDirectoryPicker({mode:'readwrite'});
    const dir=await selected.getDirectoryHandle('data',{create:true});
    let existing;
    try {
      const h=await dir.getFileHandle('workspace.json');
      const file=await h.getFile();
      if(file.size)existing=JSON.parse(await file.text());
    } catch(err) { if(err.name!=='NotFoundError')throw err; }
    let imported=null;
    if(existing) {
      if(existing.format!=='innovation-radar-local-backup'||existing.version!==2) throw new Error('Plik data/workspace.json ma nieobsługiwany format.');
      imported=normalize(existing.data);
    }
    if(imported && !confirm('W tym folderze jest zapisany workspace. Wczytać jego dane i zastąpić wpisy z pamięci przeglądarki?'))return false;
    const previous=clone(memory);
    const previousHandle=folderHandle;
    folderHandle=selected;folderName=selected.name;
    try {
      if(imported)memory=imported;
      save();
      await writeToFolder();
    }catch(err){ memory=previous;folderHandle=previousHandle;folderName=previousHandle?.name||'';throw err; }
    return true;
  }
  function downloadBackup() {
    const blob=new Blob([JSON.stringify(backup(),null,2)],{type:'application/json'});
    const url=URL.createObjectURL(blob);
    try {
      const link=document.createElement('a');
      link.href=url; link.download='innovation-radar-workspace.json';
      document.body.append(link);link.click();link.remove();
    } finally {setTimeout(()=>URL.revokeObjectURL(url),3000);}
  }
  window.RadarStore=Object.freeze({ all,commit,backup,restoreBackup,downloadBackup,openFolder,get folderName(){return folderName;},get storageWarning(){return storageWarning;} });
})();
