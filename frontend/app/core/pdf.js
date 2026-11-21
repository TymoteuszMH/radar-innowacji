'use strict';
/* Dependency-free PDF fallback. Supports simple text-layer PDFs with
   FlateDecode/ASCII85Decode. This is NOT a general PDF parser or OCR. */
(() => {
  function byteString(bytes) {
    const chunks=[];
    for(let i=0;i<bytes.length;i+=16000) chunks.push(String.fromCharCode(...bytes.subarray(i,i+16000)));
    return chunks.join('');
  }
  function bytesFrom(str) {const arr=new Uint8Array(str.length);for(let i=0;i<str.length;i++)arr[i]=str.charCodeAt(i)&255;return arr;}
  function decode85(data) {
    const out=[];let chunk=[];
    for(const c of data) {
      if(c===126) break;
      if(c===122 && !chunk.length) {out.push(0,0,0,0);continue;}
      if(c<=32 || c>117 || c<33)continue;
      chunk.push(c-33);
      if(chunk.length===5) {let n=0;for(const v of chunk)n=n*85+v;out.push((n>>>24)&255,(n>>>16)&255,(n>>>8)&255,n&255);chunk=[];}
    }
    if(chunk.length>1) {
      const length=chunk.length;
      while(chunk.length<5)chunk.push(84);
      let n=0;for(const v of chunk)n=n*85+v;
      const four=[(n>>>24)&255,(n>>>16)&255,(n>>>8)&255,n&255];
      out.push(...four.slice(0,length-1));
    }
    return new Uint8Array(out);
  }
  async function decodeStream(obj) {
    const marker=/\bstream\r?\n/.exec(obj);if(!marker)return '';
    let stream=obj.slice(marker.index+marker[0].length,obj.lastIndexOf('endstream'));
    if(stream.endsWith('\r\n')) stream=stream.slice(0,-2);
    else if(stream.endsWith('\n'))stream=stream.slice(0,-1);
    let bytes=bytesFrom(stream);
    const filters=(obj.slice(0,marker.index).match(/\/(ASCII85Decode|FlateDecode|LZWDecode|DCTDecode|JPXDecode)/g)||[]).map(x=>x.slice(1));
    for(const filter of filters) {
      if(filter==='ASCII85Decode')bytes=decode85(bytes);
      else if(filter==='FlateDecode') {
        if(typeof DecompressionStream==='undefined')throw new Error('Ta przeglądarka nie obsługuje rozpakowania PDF. Wklej tekst ręcznie.');
        try {
          const stream=new Blob([bytes]).stream().pipeThrough(new DecompressionStream('deflate'));
          bytes=new Uint8Array(await new Response(stream).arrayBuffer());
        } catch {throw new Error('Nie udało się rozpakować warstwy tekstowej PDF.');}
      } else throw new Error('Nieobsługiwany rodzaj kompresji PDF. Wklej tekst ręcznie.');
    }
    return byteString(bytes);
  }
  function makeCmap(text) {
    const map={};
    for(const m of text.matchAll(/<([\dA-Fa-f]{2,8})>\s*<([\dA-Fa-f]{4,16})>/g)) {
      const h=m[2];let char='';
      for(let j=0;j<h.length;j+=4)char+=String.fromCharCode(parseInt(h.slice(j,j+4),16));
      map[parseInt(m[1],16)]=char;
    }
    return map;
  }
  function unescapePdfLiteral(str) {
    const bytes=[];
    for(let i=0;i<str.length;i++) {
      if(str[i]!=='\\') {bytes.push(str.charCodeAt(i)&255);continue;}
      i++; const c=str[i];
      if(!c)break;
      if(/[0-7]/.test(c)) {
        let digits=c;
        while(digits.length<3 && i+1<str.length && /[0-7]/.test(str[i+1]))digits+=str[++i];
        bytes.push(parseInt(digits,8)&255);continue;
      }
      if(c==='n')bytes.push(10);
      else if(c==='r')bytes.push(13);
      else if(c==='t')bytes.push(9);
      else if(c==='b')bytes.push(8);
      else if(c==='f')bytes.push(12);
      else if(c==='\r' || c==='\n'){if(c==='\r' && str[i+1]==='\n')i++;}
      else bytes.push(c.charCodeAt(0)&255);
    }
    return bytes;
  }
  function textFromBytes(bytes,cmap) {
    if(cmap && Object.keys(cmap).length) {
      return bytes.map(v=>cmap[v] || (v>=32&&v<127?String.fromCharCode(v):'')).join('');
    }
    return new TextDecoder('windows-1252').decode(new Uint8Array(bytes));
  }
  function parseTextBlock(block,cmaps) {
    const font=block.match(/\/(F[\w+.-]+)\s+[\d.]+\s+Tf/)?.[1] ?? '';
    const cmap=cmaps[font] || cmaps._default;
    const parts=[];
    // Simple text showing operators Tj. Also handles array TJ of literal strings.
    const pieces=block.matchAll(/\(((?:\\[\s\S]|[^\\)])*)\)\s*Tj|\[((?:[^\]]|\][^\s])*?)\]\s*TJ/g);
    for(const m of pieces) {
      if(m[1]!==undefined)parts.push(textFromBytes(unescapePdfLiteral(m[1]),cmap));
      else for(const s of m[2].matchAll(/\(((?:\\[\s\S]|[^\\)])*)\)/g))parts.push(textFromBytes(unescapePdfLiteral(s[1]),cmap));
    }
    return parts.join(' ').replace(/\s+/g,' ').trim();
  }
  async function textFromPdf(file) {
    const buffer=await file.arrayBuffer();
    if(buffer.byteLength<7 || new TextDecoder('ascii').decode(buffer.slice(0,5))!=='%PDF-')throw new Error('Nieprawidłowy format PDF.');
    const raw=byteString(new Uint8Array(buffer));
    const objects=new Map();
    for(const m of raw.matchAll(/(?:^|[\r\n])\s*(\d+)\s+\d+\s+obj\b([\s\S]*?)\bendobj\b/g))objects.set(m[1],m[2]);
    if(!objects.size)throw new Error('Nie udało się otworzyć struktury PDF. Wklej tekst ręcznie.');
    const cmapCache={};
    for(const [id,obj] of objects) {
      if(!obj.includes('/ToUnicode'))continue;
      const ref=obj.match(/\/ToUnicode\s+(\d+)\s+\d+\s+R/);
      if(ref && objects.has(ref[1])) {
        try {cmapCache[id]=makeCmap(await decodeStream(objects.get(ref[1])));}catch { /* malformed embedded font */ }
      }
    }
    const cmaps={};
    for(const [id,obj] of objects) {
      if(!cmapCache[id])continue;
      const fontName=obj.match(/\/Name\s*\/([\w+.-]+)/)?.[1];
      if(fontName)cmaps[fontName]=cmapCache[id];
    }
    const known=Object.values(cmaps);if(known.length===1)cmaps._default=known[0];
    let lines=[];
    for(const obj of objects.values()) {
      if(!obj.includes('stream') || obj.includes('begincmap'))continue;
      let stream='';
      try {stream=await decodeStream(obj);}catch{continue;}
      if(!stream.includes('BT'))continue;
      for(const m of stream.matchAll(/\bBT\b([\s\S]*?)\bET\b/g)) {
        const line=parseTextBlock(m[1],cmaps);
        if(line)lines.push(line);
      }
    }
    const result=lines.join('\n').trim().slice(0,150000);
    if(result.length<30)throw new Error('Nie znaleziono czytelnej warstwy tekstowej. PDF może być skanem lub używać nieobsługiwanego kodowania. Wklej tekst ręcznie.');
    return result;
  }
  window.RadarPdf=Object.freeze({textFromPdf});
})();
