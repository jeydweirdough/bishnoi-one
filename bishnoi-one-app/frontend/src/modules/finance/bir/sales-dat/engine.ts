// @ts-nocheck
/* The BIR Sales DAT converter's logic, copied line for line from converter.html
   (Downloads/DEV-PROJECTS/BIR DAT Converter, Oct 19 2026: its lines 369-1417), so its
   results are provably the same: tests/bir-sales-dat.test.mjs runs both on the same
   files and requires identical DATs. Change a rule here only with Sir Rommel's
   confirmation, and record it in rules.ts. Unchecked by TypeScript on purpose: it is
   kept exactly as the original rather than rewritten. The typed entry point is prepare.ts. */

/* BIR RELIEF Summary List of Sales — Oojeema CSV -> .DAT, plus report reconciliation */

function parseCSV(text){
  text = text.replace(/^﻿/, "");
  const rows=[]; let row=[], cur="", q=false;
  for(let i=0;i<text.length;i++){
    const c=text[i];
    if(q){ if(c==='"'){ if(text[i+1]==='"'){cur+='"';i++;} else q=false; } else cur+=c; }
    else if(c==='"') q=true;
    else if(c===','){ row.push(cur); cur=""; }
    else if(c==='\r'){ }
    else if(c==='\n'){ row.push(cur); rows.push(row); row=[]; cur=""; }
    else cur+=c;
  }
  if(cur!==""||row.length){ row.push(cur); rows.push(row); }
  return rows;
}

const MONTHS={JAN:1,FEB:2,MAR:3,APR:4,MAY:5,JUN:6,JUL:7,AUG:8,SEP:9,OCT:10,NOV:11,DEC:12};
/* accepts 1,234.50  " -   "  (1,234.50)  and plain numbers */
const num = v => { if(typeof v==="number") return v;
                   let s=String(v==null?"":v).replace(/[, ]/g,""); if(s===""||s==="-")return 0;
                   let neg=false; if(/^\(.*\)$/.test(s)){ neg=true; s=s.slice(1,-1); }
                   const n=parseFloat(s); return isNaN(n)?0:(neg?-n:n); };
/* Ñ -> N, ó -> O, etc.  Stripping accents outright turns YBAÑEZ into YBAEZ
   and OSMEÑA into OSMEA, which are different names. */
const FOLD={"Ø":"O","ø":"o","Æ":"AE","æ":"ae","Œ":"OE","œ":"oe",
            "ß":"ss","Đ":"D","đ":"d","Þ":"TH","þ":"th","Ł":"L","ł":"l"};
const fold = t => String(t==null?"":t).replace(/[À-ɏ]/g,c=>FOLD[c]||c)
        .normalize("NFD").replace(/[̀-ͯ]/g,"");
const clean = (t,w) => {
  let s=fold(t).toUpperCase().replace(/[^A-Z0-9 ]/g,"").replace(/ {2,}/g," ").trim();
  return w?s.slice(0,w).trim():s; };
/* Customer names in the DAT, per the rule confirmed by the supervisor (Oct 2026):
   capitals; & -> AND; period and hyphen -> space; apostrophes and commas deleted;
   Ñ -> N; any other symbol removed. */
const cleanName = t => fold(t).toUpperCase().replace(/&/g," AND ").replace(/[.\-]/g," ")
        .replace(/['’,]/g,"").replace(/[^A-Z0-9 ]/g," ").replace(/ {2,}/g," ").trim();
/* Registered names the cleaning rules get wrong. Keyed by the first 9 digits of the TIN;
   an entry here always wins over the rules. Add one line per customer. */
const NAME_EXCEPTIONS = {
  /* "200306457": "GENERIC PHARMACY",   example: first 9 TIN digits, then the exact name for the DAT.
     Empty by decision (15 Oct 2026): names follow the rules; the TIN is what must be right. */
};
const datName = (name, tin) => { const x=NAME_EXCEPTIONS[tin9(tin)]; return x?clean(x):cleanName(name); };
/* every customer name that the DAT spells differently from Oojeema, for review */
function nameChanges(rows){
  const seen={}, out=[];
  rows.forEach(r=>{ const k=tin9(r.tin)+"|"+r.name; if(seen[k]) return; seen[k]=1;
    const plain=fold(r.name).toUpperCase().replace(/\s+/g," ").trim(), dat=datName(r.name,r.tin);
    if(dat===plain) return;
    const exc=!!NAME_EXCEPTIONS[tin9(r.tin)];
    out.push({original:r.name, tin:r.tin, dat, why:exc?"Exceptions list":"Cleaning rules",
      check:!exc && /[&\-]|\.[A-Za-z]/.test(r.name)});   /* & , hyphen, or "M.CORTEZ": the rules may be wrong */
  });
  return out.sort((a,b)=>(b.why==="Exceptions list")-(a.why==="Exceptions list")||b.check-a.check||a.original.localeCompare(b.original));
}
/* For matching only, never for output: ignores spacing, punctuation and "&" vs "AND",
   so a name matches however it was cleaned (old rule, new rule, or as typed in Oojeema). */
const nameKey = t => fold(t).toUpperCase().replace(/&/g,"AND").replace(/[^A-Z0-9]/g,"").replace(/AND/g,"");
const tin9 = t => String(t==null?"":t).replace(/\D/g,"").slice(0,9);

/* split one merged address into two <=30 char fields on a word boundary */
function splitAddr(a){
  const s=clean(a); if(!s) return ["",""];
  if(s.length<=30) return [s,""];
  let cut=s.lastIndexOf(" ",30); if(cut<=0) cut=30;
  return [s.slice(0,cut).trim(), clean(s.slice(cut).trim(),30)];
}

/* rows: arrays of cell text, from a CSV or from a worksheet */
function parseOojeemaRows(rows){
  const tp={tradeName:"",name:"",tin:"",address:"",ir:null};
  const data=[]; let total=null;
  rows.forEach((r,i)=>{
    const k=(r[0]||"").trim().toUpperCase().replace(/[\s:]+$/,"");
    if(k==="TAXPAYER TRADE NAME") tp.tradeName=(r[1]||"").trim();
    else if(k==="TAXPAYER NAME")  tp.name=(r[1]||"").trim();
    else if(k==="TIN"||k==="VAT-REG TIN") tp.tin=(r[1]||"").trim();
    else if(k==="TAXPAYER ADDRESS") tp.address=(r[1]||"").trim();
    else if(/^TOTAL/.test(k)) total={gross:num(r[5]),exempt:num(r[6]),zero:num(r[7]),
                                     taxable:num(r[8]),vat:num(r[9])};
    else{
      const m=k.match(/^([A-Z]{3})\s+(\d{1,2}),\s*(\d{4})$/);
      if(m&&MONTHS[m[1]]) data.push({
        row:i+1, month:MONTHS[m[1]], day:+m[2], year:+m[3],
        tin:(r[1]||"").trim(), name:((r[2]||"").trim()||(r[3]||"").trim()),
        address:(r[4]||"").trim(),
        gross:num(r[5]), exempt:num(r[6]), zero:num(r[7]),
        taxable:num(r[8]), vat:num(r[9])
      });
      else { /* a typed "Income Statement" figure, as in the reconciliation workbook */
        const at=r.findIndex(c=>String(c||"").trim().toUpperCase()==="INCOME STATEMENT");
        if(at>=0){ const v=r.slice(at+1).find(c=>String(c||"").trim()!==""&&!isNaN(num(c))&&num(c)!==0);
                   if(v!=null) tp.ir={value:num(v), row:i+1}; }
      }
    }
  });
  return {taxpayer:tp, rows:data, total};
}
function parseOojeema(text){ return parseOojeemaRows(parseCSV(text)); }

/* pull exact addresses out of an Oojeema-generated DAT, keyed by TIN then by name */
function addressBook(datText){
  const book={byTin:{}, byName:{}, header:null};
  for(const r of parseCSV(datText)){
    if(r.length>=15&&r[0]==="D") { const k=tin9(r[2]);
      if(k) book.byTin[k]=[r[7],r[8]]; book.byName[nameKey(r[3])]=[r[7],r[8]]; }
    else if(r.length>=17&&r[0]==="H") book.header={name:r[3],trade:r[7],a1:r[8],a2:r[9],rdo:r[14],fy:r[16]};
  }
  return book;
}

function lastDay(y,m){ return new Date(y,m,0).getDate(); }
const pad=(n,w)=>String(n).padStart(w,"0");
const amtH = v => (Math.round(v*100)/100).toFixed(2);
const amtD = v => { const n=Math.round(v*100)/100; return n===0?"0":n.toFixed(2); };
const qq = s => '"'+s+'"';

function buildDAT(parsed, opts){
  opts=opts||{}; const book=opts.book||null;
  const rs=parsed.rows; if(!rs.length) throw new Error("No sales rows found in the CSV.");
  const y=rs[0].year, m=rs[0].month;
  const period = pad(m,2)+"/"+pad(opts.day||lastDay(y,m),2)+"/"+y;
  const seller = tin9(parsed.taxpayer.tin);

  let hA1,hA2;
  if(book&&book.header){ hA1=book.header.a1; hA2=book.header.a2; }
  else [hA1,hA2]=splitAddr(parsed.taxpayer.address);
  const regName = clean(parsed.taxpayer.name||parsed.taxpayer.tradeName);
  const trdName = clean(parsed.taxpayer.tradeName||parsed.taxpayer.name);

  const t={exempt:0,zero:0,taxable:0,vat:0};
  rs.forEach(r=>{t.exempt+=r.exempt;t.zero+=r.zero;t.taxable+=r.taxable;t.vat+=r.vat;});

  const out=[[ "H","S",qq(seller),qq(regName),qq(""),qq(""),qq(""),qq(trdName),
    qq(hA1),qq(hA2), amtH(t.exempt),amtH(t.zero),amtH(t.taxable),amtH(t.vat),
    qq(clean(opts.rdo||"53A")), period, String(parseInt(opts.fyMonth,10)||12) ].join(",")];

  for(const r of rs){
    const k=tin9(r.tin); let a1,a2, src="split";
    const hit = book && ((k&&book.byTin[k]) || book.byName[nameKey(r.name)]);
    if(hit){ [a1,a2]=hit; src="dat"; } else [a1,a2]=splitAddr(r.address);
    r._addrSource=src;
    out.push([ "D","S",qq(k),qq(datName(r.name,r.tin)),qq(""),qq(""),qq(""),
      qq(clean(a1,30)),qq(clean(a2,30)),
      amtD(r.exempt),amtD(r.zero),amtD(r.taxable),amtD(r.vat),
      seller, period ].join(","));
  }
  return { text: out.join("\r\n")+"\r\n",
           filename: seller+"S"+pad(m,2)+y+".DAT",
           period, totals:t, count:rs.length };
}

/* One line per customer (supervisor, 17 Oct 2026): all of a customer's rows for the month are added into one line.
   The customer is the 9-digit TIN (all a DAT keeps); a row with no TIN is grouped by its name. Amounts are added
   in centavos. A customer whose rows add to zero in every column is left out and listed. */
function oneRowPerCustomer(rows){
  const by=new Map(), c=v=>Math.round((v||0)*100);
  rows.forEach(r=>{ const t=tin9(r.tin), k=t?"T"+t:"N"+nameKey(r.name);
    if(!by.has(k)) by.set(k,{rows:[],names:new Map()});
    const g=by.get(k); g.rows.push(r); g.names.set(r.name,(g.names.get(r.name)||0)+1); });
  const out=[], zero=[];
  by.forEach(g=>{ const f=g.rows[0], sum=key=>g.rows.reduce((a,r)=>a+c(r[key]),0)/100;
    const name=[...g.names].sort((a,b)=>b[1]-a[1])[0][0];           /* the name used most; the first one on a tie */
    const r=Object.assign({},f,{name, address:(g.rows.find(x=>x.address)||f).address||"", count:g.rows.length, parts:g.rows,
      exempt:sum("exempt"), zero:sum("zero"), taxable:sum("taxable"), vat:sum("vat")});
    if("gross" in f) r.gross=sum("gross");
    (r.exempt||r.zero||r.taxable||r.vat?out:zero).push(r); });
  return {rows:out, zero, merged:rows.length-out.length-zero.length};
}

function validate(parsed, vatRate){
  vatRate = vatRate||12; const issues=[];
  parsed.rows.forEach((r,i)=>{
    const line=i+1;
    if(!tin9(r.tin)) issues.push({sev:"warn",line,name:r.name,msg:"No TIN — included with a blank TIN. Confirm how this customer should be reported before filing."});
    else if(tin9(r.tin).length<9) issues.push({sev:"error",line,name:r.name,msg:"TIN has fewer than 9 digits"});
    if(!clean(r.name)) issues.push({sev:"error",line,name:"(blank)",msg:"No customer name"});
    /* differences of 5 centavos or less are rounding (supervisor, Oct 2026) */
    const exp=Math.round(r.taxable*vatRate)/100;
    if(Math.abs(Math.round(r.vat*100)-Math.round(r.taxable*vatRate))>5)
      issues.push({sev:"warn",line,name:r.name,
        msg:"Output VAT "+r.vat.toFixed(2)+" is not "+vatRate+"% of taxable sales (expected "+exp.toFixed(2)+")"});
    const sum=r.exempt+r.zero+r.taxable;
    if(Math.abs(sum-r.gross)>0.01)
      issues.push({sev:"warn",line,name:r.name,
        msg:"Exempt + zero-rated + taxable = "+sum.toFixed(2)+" but gross sales is "+r.gross.toFixed(2)});
    if(!r.address) issues.push({sev:"info",line,name:r.name,msg:"No address on file"});
  });
  if(parsed.total){
    const t={exempt:0,zero:0,taxable:0,vat:0};
    parsed.rows.forEach(r=>{t.exempt+=r.exempt;t.zero+=r.zero;t.taxable+=r.taxable;t.vat+=r.vat;});
    [["exempt","Exempt sales"],["zero","Zero-rated sales"],["taxable","Taxable sales"],["vat","Output VAT"]]
      .forEach(([k,lbl])=>{
        const rep = parsed.total[k];
        if(Math.abs(t[k]-rep)>0.01)
          issues.push({sev:"error",line:"—",name:"TOTAL row",
            msg:lbl+": rows add to "+t[k].toFixed(2)+" but the CSV total says "+rep.toFixed(2)});
      });
  }
  const seen={}; let repeat=0;
  parsed.rows.forEach(r=>{ const k=tin9(r.tin); if(!k)return; seen[k]=(seen[k]||0)+1; if(seen[k]===2) repeat++; });
  if(repeat) issues.push({sev:"info",line:"—",name:"Repeat customers",
    msg:repeat+" customers appear on more than one row (one row per invoice)."});
  return issues;
}

/* Re-read a finished DAT and confirm it is what we meant to write. */
function checkDAT(text, filename, expectCount){
  const checks=[], ok=(c,label)=>checks.push({ok:!!c,label});
  const lines=text.split("\r\n"); if(lines[lines.length-1]==="") lines.pop();
  ok(text.endsWith("\r\n") && !/[^\r]\n/.test(text), "Every line ends with a Windows line break (CRLF)");
  ok(!/[^\x20-\x7E\r\n]/.test(text), "Plain characters only (no accents or symbols outside A–Z, 0–9, punctuation)");
  const recs=lines.map(l=>parseCSV(l+"\n")[0]||[]);
  const h=recs[0]||[], ds=recs.slice(1);
  ok(h[0]==="H" && h.length===17, "First line is the header, with 17 fields");
  ok(ds.length && ds.every(r=>r[0]==="D" && r.length===15), "Every other line is a detail line, with 15 fields");
  if(expectCount!=null) ok(ds.length===expectCount, ds.length+" detail lines for "+expectCount+" sales rows");
  const c=v=>Math.round(num(v)*100), sumC=i=>ds.reduce((a,r)=>a+c(r[i]),0);
  const same=[10,11,12,13].every((hi,k)=>c(h[hi])===sumC(9+k));
  ok(same, "Header totals equal the sum of the detail lines (exempt, zero-rated, taxable, VAT)");
  ok(ds.every(r=>r[13]===h[2] && r[14]===h[15]), "Every detail line carries the same seller TIN and period as the header");
  const m=/^(\d{9})S(\d{2})(\d{4})\.DAT$/.exec(filename||"");
  ok(m && m[1]===h[2] && h[15] && m[2]===h[15].slice(0,2) && m[3]===h[15].slice(6),
     "File name "+filename+" matches the seller TIN and period (TIN + S + MMYYYY.DAT)");
  return checks;
}

/* ---- DAT -> CSV in the layout of Oojeema's Sales Relief export (requested Oct 2026) ----
   The content is the DAT's own: names, addresses (the two lines joined) and amounts as filed.
   A DAT keeps only the first 9 TIN digits. tinFull maps them back to the full TIN with branch
   code, taken from Oojeema's own files; without a match the TIN is written as XXX-XXX-XXX
   (a branch code is never made up). */
const SR_HEAD_LINES = [
  'TAXABLE,TAXPAYER,"REGISTERED NAME","NAME OF CUSTOMER","CUSTOMER\'S ADDRESS","AMOUNT OF","AMOUNT OF","AMOUNT OF","AMOUNT OF","AMOUNT OF","AMOUNT OF"',
  'MONTH,IDENTIFICATION,,"(Last Name, First Name, Middle Name)",,"GROSS SALES","EXEMPT SALES","ZERO-RATED SALES","TAXABLE SALES","OUTPUT TAX","GROSS TAXABLE SALES"',
  ',NUMBER'];
/* full TINs as Oojeema writes them, by their first 9 digits; a TIN with several branch codes is left out */
function tinMap(tins){
  const by={}; tins.forEach(t=>{ t=String(t||"").trim(); const d=tin9(t);
    if(d.length===9 && /^\d{3}-\d{3}-\d{3}-\d{3,5}$/.test(t)) (by[d]=by[d]||new Set()).add(t); });
  const out={}; Object.keys(by).forEach(d=>{ if(by[d].size===1) out[d]=[...by[d]][0]; }); return out;
}
function datToSalesReliefCSV(datText, tinFull){
  const recs=parseCSV(datText), h=recs.find(r=>r[0]==="H"), ds=recs.filter(r=>r[0]==="D");
  if(!h||!ds.length) throw new Error("No H or D records found. Is this a sales DAT file?");
  const q=v=>{ v=String(v==null?"":v); return /[\s,"]/.test(v)?'"'+v.replace(/"/g,'""')+'"':v; };
  const amt=c=>(c<0?"-":"")+(Math.abs(c)/100).toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2});
  let full=0, short=0;
  const tin=t=>{ const d=tin9(t); if(!d) return "";
    if(tinFull&&tinFull[d]){ full++; return tinFull[d]; } short++; return d.replace(/^(\d{3})(\d{3})(\d{3})$/,"$1-$2-$3"); };
  const addr=(a,b)=>[a,b].map(s=>String(s||"").trim()).filter(Boolean).join(" ");
  const m=/^(\d{2})\/(\d{2})\/(\d{4})$/.exec(h[15]||"");
  const when=m?MON[+m[1]-1].toUpperCase()+" "+m[2]+", "+m[3]:(h[15]||"");
  const L=[], row=a=>L.push(a.map(q).join(","));
  L.push('"SALES TRANSACTION"','"RECONCILIATION OF LISTING FOR ENFORCEMENT"',"","","");
  row(["TAXPAYER TRADE NAME",h[7]]); row(["TAXPAYER NAME",h[3]]);
  const sellerTin=tin(h[2]); full=0; short=0;          /* count customer TINs only */
  row(["TIN",sellerTin]); row(["TAXPAYER ADDRESS",addr(h[8],h[9])]); L.push("");
  SR_HEAD_LINES.forEach(l=>L.push(l));
  const t={gross:0,exempt:0,zero:0,taxable:0,vat:0,gt:0};
  ds.forEach(r=>{
    const ex=C(r[9]), zr=C(r[10]), tx=C(r[11]), vt=C(r[12]), gross=ex+zr+tx, gt=tx+vt;
    t.gross+=gross; t.exempt+=ex; t.zero+=zr; t.taxable+=tx; t.vat+=vt; t.gt+=gt;
    row([when, tin(r[2]), r[3], "", addr(r[7],r[8]), amt(gross), amt(ex), amt(zr), amt(tx), amt(vt), amt(gt)]);
  });
  row(["TOTAL\t","","","","",amt(t.gross),amt(t.exempt),amt(t.zero),amt(t.taxable),amt(t.vat),amt(t.gt)]);
  L.push("",'"END OF REPORT"');
  return {text:"﻿"+L.join("\n")+"\n", rows:ds.length, totals:t, tinFull:full, tinShort:short, sellerTin};
}

/* ================= Reconciliation engine ================= */
/* amounts are kept as whole centavos so totals never drift */
const C = v => Math.round(num(v)*100);
const sumBy = (xs,k) => xs.reduce((a,x)=>a+(x[k]||0),0);
const fmt = c => (c<0?"−":"")+(Math.abs(c)/100).toLocaleString("en-PH",{minimumFractionDigits:2,maximumFractionDigits:2});
const norm = s => String(s==null?"":s).toLowerCase().replace(/\s+/g," ").trim();
const DATE_RE = /^[A-Z][a-z]{2} \d{1,2}, \d{4}$/;
const INV_RE = /\b(?:SI|BI)\d{5,}\b/i, INV_RE_ALL = /\b(?:SI|BI)\d{5,}\b/gi;
/* month and year of a GL date: "Sep 01, 2026" as exported, or an Excel date serial */
function entryMonth(v){
  if(typeof v==="number"&&v>20000){ const d=new Date(Date.UTC(1899,11,30)+Math.round(v)*864e5); return {mon:d.getUTCMonth()+1, yr:d.getUTCFullYear()}; }
  const m=/^([A-Z][a-z]{2}) \d{1,2}, (\d{4})$/.exec(String(v==null?"":v).trim());
  return m?{mon:MON.indexOf(m[1].toLowerCase())+1||null, yr:+m[2]}:{mon:null, yr:null};
}

/* --- reading .xlsx without any library: unzip + read the sheet XML --- */
function unzip(ab){
  const u8=new Uint8Array(ab), dv=new DataView(ab), files={};
  let e=-1; for(let i=u8.length-22;i>=Math.max(0,u8.length-65557);i--) if(dv.getUint32(i,true)===0x06054b50){e=i;break;}
  if(e<0) throw new Error("This is not a valid .xlsx file.");
  let p=dv.getUint32(e+16,true); const n=dv.getUint16(e+10,true), td=new TextDecoder();
  for(let k=0;k<n;k++){
    if(dv.getUint32(p,true)!==0x02014b50) break;
    const method=dv.getUint16(p+10,true), size=dv.getUint32(p+20,true), nl=dv.getUint16(p+28,true),
          xl=dv.getUint16(p+30,true), cl=dv.getUint16(p+32,true), off=dv.getUint32(p+42,true);
    const name=td.decode(u8.subarray(p+46,p+46+nl));
    const start=off+30+dv.getUint16(off+26,true)+dv.getUint16(off+28,true);
    files[name]={method, data:u8.subarray(start,start+size)};
    p+=46+nl+xl+cl;
  }
  return files;
}
async function inflateRaw(u8){
  const s=new Blob([u8]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
  return new Uint8Array(await new Response(s).arrayBuffer());
}
const xmlText = s => s.replace(/_x([0-9A-Fa-f]{4})_/g,(m,h)=>String.fromCharCode(parseInt(h,16)))
  .replace(/&lt;/g,"<").replace(/&gt;/g,">").replace(/&quot;/g,'"').replace(/&apos;/g,"'")
  .replace(/&#x([0-9A-Fa-f]+);/g,(m,h)=>String.fromCharCode(parseInt(h,16)))
  .replace(/&#(\d+);/g,(m,d)=>String.fromCharCode(+d)).replace(/&amp;/g,"&");
const attr = (s,n) => { const m=s.match(new RegExp("(?:^|\\s)"+n+'="([^"]*)"')); return m?m[1]:null; };
const colIdx = s => s.replace(/\d+/g,"").split("").reduce((a,ch)=>a*26+ch.charCodeAt(0)-64,0)-1;
function runsText(x){
  x=x.replace(/<rPh\b[\s\S]*?<\/rPh>/g,"").replace(/<t\b[^>]*\/>/g,"");
  let t=""; for(const m of x.matchAll(/<t\b[^>]*>([\s\S]*?)<\/t>/g)) t+=m[1]; return xmlText(t);
}
async function readXlsx(ab){
  const z=unzip(ab), td=new TextDecoder();
  const txt=async n=>{ const f=z[n]; if(!f) return null; return td.decode(f.method===0?f.data:await inflateRaw(f.data)); };
  const ss=[], sst=await txt("xl/sharedStrings.xml");
  if(sst) for(const m of sst.matchAll(/<si\b[^>]*>([\s\S]*?)<\/si>|<si\s*\/>/g)) ss.push(m[1]?runsText(m[1]):"");
  const wb=await txt("xl/workbook.xml"), rels=await txt("xl/_rels/workbook.xml.rels");
  if(!wb) throw new Error("This is not a valid .xlsx file.");
  const target={}; for(const m of (rels||"").matchAll(/<Relationship\b([^>]*)>/g)) target[attr(m[1],"Id")]=attr(m[1],"Target");
  const sheets=[];
  for(const m of wb.matchAll(/<sheet\b([^>]*)>/g)){
    const name=xmlText(attr(m[1],"name")||""), t=target[attr(m[1],"r:id")]; if(!t) continue;
    const xml=await txt(t.startsWith("/")?t.slice(1):"xl/"+t); if(!xml) continue;
    const grid=[]; let rn=0;
    for(const r of xml.matchAll(/<row\b([^>]*?)(?:\/>|>([\s\S]*?)<\/row>)/g)){
      rn=+(attr(r[1],"r")||rn+1); const row=[]; let cn=-1;
      for(const c of (r[2]||"").matchAll(/<c\b([^>]*?)(?:\/>|>([\s\S]*?)<\/c>)/g)){
        const ref=attr(c[1],"r"); cn=ref?colIdx(ref):cn+1;
        const t=attr(c[1],"t"), inner=c[2]||"", v=(inner.match(/<v>([\s\S]*?)<\/v>/)||[])[1];
        let val=null;
        if(t==="s") val=v!=null?ss[+v]:null;
        else if(t==="inlineStr") val=runsText(inner);
        else if(t==="str"||t==="e") val=v!=null?xmlText(v):null;
        else if(t==="b") val=v==="1";
        else if(v!=null) val=+v;
        row[cn]=val;
      }
      grid[rn-1]=row;
    }
    for(let i=0;i<grid.length;i++) if(!grid[i]) grid[i]=[];
    sheets.push({name, grid});
  }
  return sheets;
}

/* --- recognise each report by its column headings --- */
function findHeader(grid, need){
  for(let r=0;r<Math.min(grid.length,60);r++){
    const map={}; (grid[r]||[]).forEach((v,c)=>{ const k=norm(v); if(k&&!(k in map)) map[k]=c; });
    if(need.every(n=>n in map)) return {row:r, col:map};
  }
  return null;
}
const SJ_HEAD=["si/bi no","amount","output vat"], GL_HEAD=["reference number","total debit","total credit"],
      SR_HEAD=["gross sales","exempt sales"];
const IS_HEAD=["account","jan","jun","dec"];
function classify(grid){
  let h;
  if((h=findHeader(grid,SJ_HEAD))) return {kind:"sj",h};
  if((h=findHeader(grid,GL_HEAD))) return {kind:"gl",h};
  if((h=findHeader(grid,SR_HEAD))) return {kind:"sr",h};
  if((h=findHeader(grid,IS_HEAD))) return {kind:"is",h};
  return null;
}

/* Oojeema "Income Statement Monthly" (the IR): one row per account, one column per month */
const MON=["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"];
function parseIS(grid, h, from){
  const lines={}, year=(grid.find(r=>/^year/i.test(cellTxt((r||[])[0])))||[])[1];
  for(let r=h.row+1;r<grid.length;r++){
    const row=grid[r]||[], label=cellTxt(row[0]); if(!label) continue;
    const vals=MON.map(m=>(m in h.col)?C(row[h.col[m]]):null);
    if(vals.some(v=>v!==null&&v!==0)||!(label in lines)) lines[label]={row:r+1, vals};
  }
  return {from, year, lines};
}
/* the September (etc.) figures the reconciliation needs, found by account name */
function isFigures(is, month){
  const find=re=>{ const k=Object.keys(is.lines).find(l=>re.test(l)); return k?{label:k, row:is.lines[k].row, value:is.lines[k].vals[month-1]}:null; };
  const f={month, total:find(/^total revenue$/i), sales:find(/^sale of goods/i), disc:find(/^sales discounts?$/i), fee:find(/^packaging charges/i),
           deferred:find(/^def+er+ed sales/i)};
  /* every line that makes up Total Revenue (the lines between Sale of Goods and Total Revenue) */
  f.revenue=f.sales&&f.total?Object.keys(is.lines).filter(l=>is.lines[l].row>f.sales.row&&is.lines[l].row<f.total.row)
    .map(l=>({label:l, row:is.lines[l].row, value:is.lines[l].vals[month-1]})).sort((a,b)=>a.row-b.row):[];
  return f;
}
const cellTxt = v => v==null?"":String(v).replace(/_x000D_/g,"").replace(/\s*\r?\n\s*/g," ").trim();

function parseSJ(grid, h, from){
  const c=h.col, g=(row,k)=>(k in c)?row[c[k]]:null, lines=[], issues=[];
  for(let r=h.row+1;r<grid.length;r++){
    const row=grid[r]||[], si=cellTxt(g(row,"si/bi no")).toUpperCase(), amt=g(row,"amount");
    if(!si && (amt==null||amt==="")) continue;
    if(/^(grand )?total/.test(norm(row[0]))) continue;
    const L={from, row:r+1, date:cellTxt(g(row,"transaction date")), name:cellTxt(g(row,"customer name")),
      tin:cellTxt(g(row,"customer tin")), desc:cellTxt(g(row,"description")), si, ref:cellTxt(g(row,"reference no")),
      amt:C(amt), disc:C(g(row,"discount")), vat:C(g(row,"output vat")), vatable:C(g(row,"vatable sales")),
      gov:C(g(row,"sales to government")), exempt:C(g(row,"vat exempt sales")), zero:C(g(row,"zero-rated sales")),
      nonvat:C(g(row,"non-vat sales"))};
    L.net=L.amt-L.vat;                       /* the existing workflow: Net Sales = Amount − Output VAT */
    const parts=L.vat+L.vatable+L.gov+L.exempt+L.zero+L.nonvat;
    if(!si) issues.push({where:from+" row "+L.row, name:L.name, msg:"Sales Journal line has no SI/BI number ("+fmt(L.amt)+")"});
    if(parts-L.disc!==L.amt) issues.push({where:from+" row "+L.row, name:L.name,
      msg:"Amount "+fmt(L.amt)+" does not equal its sales columns plus VAT, less discount ("+fmt(parts-L.disc)+")"});
    lines.push(L);
  }
  return {lines, issues, from};
}

function parseGL(grid, h, from){
  const c=h.col, g=(row,k)=>(k in c)?row[c[k]]:null, entries=[], issues=[], accounts={};
  let acct="(no account name)";
  /* the export's "Date :" range (e.g. "Mar 01, 2026 - Mar 31, 2026"), as year*100+month: an account is only
     used for the months its export covers */
  let period=null;
  for(let r=0;r<h.row&&!period;r++){
    const m=/([A-Za-z]{3})[a-z]*\.?\s+\d{1,2},?\s*(\d{4})\s*-\s*([A-Za-z]{3})[a-z]*\.?\s+\d{1,2},?\s*(\d{4})/.exec((grid[r]||[]).map(cellTxt).join(" "));
    if(m&&MON.includes(m[1].toLowerCase())&&MON.includes(m[3].toLowerCase()))
      period={a:+m[2]*100+MON.indexOf(m[1].toLowerCase())+1, b:+m[4]*100+MON.indexOf(m[3].toLowerCase())+1};
  }
  const A=a=>accounts[a]=accounts[a]||{name:a, beginning:null, balance:null, n:0, net:0, periods:period?[period]:null};
  for(let r=h.row+1;r<grid.length;r++){
    const row=grid[r]||[], a0=cellTxt(row[0]), dr=g(row,"total debit"), cr=g(row,"total credit");
    const hasAmt=(dr!=null&&dr!=="")||(cr!=null&&cr!=="");
    const label=norm(g(row,"voucher number")), isDate=DATE_RE.test(a0)||(typeof row[0]==="number"&&row[0]>20000);
    if(/^beginning balance/i.test(a0)){ A(acct).beginning=C(cr)-C(dr); continue; }
    if(label==="subtotal"||label==="grand total") continue;
    if(label==="balance"){ A(acct).balance=C(cr)-C(dr); continue; }
    if(isDate && hasAmt){
      const e={from, row:r+1, account:acct, date:a0, name:cellTxt(g(row,"customer / vendor")), desc:cellTxt(g(row,"description")),
        status:cellTxt(g(row,"status")), ref:cellTxt(g(row,"reference number")), voucher:cellTxt(g(row,"voucher number")),
        dr:C(dr), cr:C(cr), si:null, link:null};
      Object.assign(e, entryMonth(row[0]));
      let m=e.ref.match(INV_RE);
      if(m){ e.si=m[0].toUpperCase(); e.link="reference"; }
      else if((m=e.desc.match(INV_RE))){ e.si=m[0].toUpperCase(); e.link="description"; }
      /* a JV can name several invoices ("SI000003636 AND SI000003637") */
      e.sis=[...new Set((e.ref+" "+e.desc).toUpperCase().match(INV_RE_ALL)||[])];
      const a=A(acct); a.n++; a.net+=e.cr-e.dr;
      entries.push(e); continue;
    }
    if(a0 && !hasAmt && !isDate) A(acct=a0);
  }
  Object.values(accounts).forEach(a=>{
    if(a.beginning!=null && a.balance!=null && a.balance-a.beginning!==a.net)
      issues.push({where:from, name:a.name, msg:"Entries add to "+fmt(a.net)+" but Balance less Beginning Balance is "+fmt(a.balance-a.beginning)});
  });
  return {entries, accounts, issues, from, period};
}
/* several GL exports combined: an account in more than one export covers all their periods */
function mergeGLAccounts(parts){
  const out={};
  parts.forEach(p=>Object.values(p.accounts).forEach(a=>{
    const o=out[a.name];
    if(!o){ out[a.name]=Object.assign({},a,{periods:a.periods&&a.periods.slice()}); return; }
    o.periods=o.periods&&a.periods?o.periods.concat(a.periods):null;
  }));
  return out;
}

function parseSRGrid(grid, from){
  const p=parseOojeemaRows(grid.map(r=>(r||[]).map(v=>v==null?"":String(v))));
  p.from=from; return p;
}
function listingFromSR(p){
  const r0=p.rows[0]||{};
  return {from:p.from, taxpayer:p.taxpayer, month:r0.month, year:r0.year,
    rows:p.rows.map(r=>({where:p.from+" row "+r.row, row:r.row, tin:r.tin, name:r.name, address:r.address,
    exempt:C(r.exempt), zero:C(r.zero), taxable:C(r.taxable), vat:C(r.vat)}))};
}
function parseDATListing(text, from){
  const out={from, header:null, rows:[]};
  parseCSV(text).forEach((r,i)=>{
    if(r[0]==="H"){ out.header={tin:r[2], name:r[3], trade:r[7], exempt:C(r[10]), zero:C(r[11]), taxable:C(r[12]), vat:C(r[13]),
                                rdo:r[14], period:r[15], fy:r[16]};
      const m=/^(\d{2})\/\d{2}\/(\d{4})$/.exec(r[15]||""); if(m){ out.month=+m[1]; out.year=+m[2]; }
      out.taxpayer={tin:r[2], name:r[3], tradeName:r[7], address:""}; }
    else if(r[0]==="D") out.rows.push({where:from+" line "+(i+1), row:i+1, tin:r[2], name:r[3],
      exempt:C(r[9]), zero:C(r[10]), taxable:C(r[11]), vat:C(r[12])});
  });
  return out;
}

/* Match listing rows (Sales Relief / DAT, which carry no invoice numbers) to Sales Journal lines:
   same customer, then identical exempt / zero-rated / VATable / VAT amounts. */
function matchListing(rows, sjLines){
  const key=nameKey, cust={}, tinKeys={};
  sjLines.forEach(l=>{ (cust[key(l.name)]=cust[key(l.name)]||[]).push(l);
    const t=tin9(l.tin); if(t)(tinKeys[t]=tinKeys[t]||new Set()).add(key(l.name)); });
  /* Oojeema's Sales Relief reports Sales to Government under Taxable Sales (e.g. LUCKY 8 SI000003128, June 2026) */
  const sigS=l=>[l.exempt,l.zero,l.vatable+l.gov,l.vat].join("|"), sigR=r=>[r.exempt,r.zero,r.taxable,r.vat].join("|");
  const res=rows.map(r=>({r, status:null, lines:[], diff:null}));
  const byCust={};
  res.forEach(x=>{
    let k=key(x.r.name);
    if(!cust[k]){ const t=tin9(x.r.tin);
      if(t&&tinKeys[t]&&tinKeys[t].size===1){ k=[...tinKeys[t]][0]; x.viaTin=true; }
      else if(k.length>=20){ /* Oojeema's DAT cuts names at 50 characters: match on the start, only if unique */
        const c=Object.keys(cust).filter(s=>s.startsWith(k)); if(c.length===1){ k=c[0]; x.viaPrefix=true; } } }
    (byCust[k]=byCust[k]||[]).push(x);
  });
  const used=new Set(), missing=[];
  Object.keys(cust).forEach(k=>{ if(!byCust[k]) byCust[k]=[]; });
  for(const [k,xs] of Object.entries(byCust)){
    const S=cust[k]||[], bS={}, bR={};
    S.forEach(l=>(bS[sigS(l)]=bS[sigS(l)]||[]).push(l));
    xs.forEach(x=>(bR[sigR(x.r)]=bR[sigR(x.r)]||[]).push(x));
    for(const [sig,rx] of Object.entries(bR)){
      const sl=bS[sig]||[], n=Math.min(rx.length,sl.length);
      for(let i=0;i<n;i++){ rx[i].status=sl.length===1?"exact":"group"; rx[i].lines=sl.length===1?[sl[0]]:sl; }
      sl.slice(0,n).forEach(l=>used.add(l));
    }
    const rL=xs.filter(x=>!x.status), sL=S.filter(l=>!used.has(l));
    if(rL.length===1 && sL.length===1){
      const x=rL[0], l=sL[0]; used.add(l);
      x.status="differs"; x.lines=[l];
      x.diff={exempt:x.r.exempt-l.exempt, zero:x.r.zero-l.zero, taxable:x.r.taxable-l.vatable-l.gov, vat:x.r.vat-l.vat};
    } else {
      rL.forEach(x=>{ x.status="unmatched"; x.candidates=sL; });
      sL.forEach(l=>missing.push({l}));
    }
  }
  return {rows:res, missing};
}
/* Sales Journal line -> index of its listing row; rows in a group of identical invoices are interchangeable */
function lineRows(m){
  const at=new Map(), groups=new Map();
  m.rows.forEach((x,i)=>{
    if(x.status==="exact"||x.status==="differs") at.set(x.lines[0],i);
    else if(x.status==="group"){ if(!groups.has(x.lines)) groups.set(x.lines,[]); groups.get(x.lines).push(i); } });
  groups.forEach((is,lines)=>is.forEach((i,k)=>at.set(lines[k],i)));
  return at;
}

function reconcile(inp){
  /* only GL entries dated in the month being reconciled: a GL export may cover the whole year */
  const inMonth=e=>!inp.month||!e.mon||(e.mon===inp.month&&(!inp.year||!e.yr||e.yr===inp.year));
  /* only GL accounts whose export covers that month: a March-only Sale of Goods GL says nothing about April */
  const key=inp.month&&inp.year?inp.year*100+inp.month:null, notCovered=[];
  const covers=a=>{ const x=inp.gl&&inp.gl.accounts&&inp.gl.accounts[a];
    return !key||!x||!x.periods||x.periods.some(p=>p.a<=key&&key<=p.b); };
  const cov=set=>{ if(!set) return set; const s=new Set();
    set.forEach(a=>{ if(covers(a)) s.add(a); else notCovered.push(a); }); return s; };
  inp=Object.assign({},inp,{accounts:cov(inp.accounts), feeAccounts:cov(inp.feeAccounts), discAccounts:cov(inp.discAccounts), defAccounts:cov(inp.defAccounts)});
  const sj=inp.sj?inp.sj.lines:[], glAll=inp.gl?inp.gl.entries.filter(inMonth):[];
  const gl=inp.accounts?glAll.filter(e=>inp.accounts.has(e.account)):glAll;
  const out={invoices:[], unlinkedGL:[], sjNoInvoice:sj.filter(l=>!l.si), totals:{}, listings:{}, noTin:[], sjLines:sj, feeBySi:null,
             glOutside:inp.gl?inp.gl.entries.length-glAll.length:0, notCovered};
  /* GL accounts tagged as packaging fees: amount per invoice, used to confirm each fee */
  if(inp.feeAccounts && inp.feeAccounts.size){
    out.feeBySi={}; out.unlinkedFee=[];
    glAll.filter(e=>inp.feeAccounts.has(e.account)).forEach(e=>{
      if(e.si) out.feeBySi[e.si]=(out.feeBySi[e.si]||0)+e.cr-e.dr; else out.unlinkedFee.push(e); });
  }
  /* GL accounts tagged as sales discounts (debit-normal): amount per invoice, used to confirm each discount */
  if(inp.discAccounts && inp.discAccounts.size){
    out.discBySi={}; out.unlinkedDisc=[];
    glAll.filter(e=>inp.discAccounts.has(e.account)).forEach(e=>{
      if(e.si) out.discBySi[e.si]=(out.discBySi[e.si]||0)+e.dr-e.cr; else out.unlinkedDisc.push(e); });
  }
  const accNet=set=>set&&set.size?glAll.filter(e=>set.has(e.account)).reduce((a,e)=>a+e.cr-e.dr,0):null;
  out.feeNet=accNet(inp.feeAccounts); out.discNet=accNet(inp.discAccounts); out.defNet=accNet(inp.defAccounts);
  /* each discount account on its own (Sales Discounts 4700, SC/PWD Discounts 4800), to check against its Income Statement line */
  if(inp.discAccounts&&inp.discAccounts.size){ out.discByAcct={}; inp.discAccounts.forEach(a=>out.discByAcct[a]=accNet(new Set([a]))); }
  /* GL accounts tagged as deferred sales (4400): a quarter-end JV credits the account for invoices whose sale
     moves to the next month, and the next day's JV reverses it. On the Income Statement the line shows
     debits less credits, so a deferral lowers Total Revenue and its reversal raises it. */
  /* an invoice from an earlier month: its Sales Journal lines (and Sales Relief row, for the customer's name,
     TIN and address as Oojeema lists them), from the other months loaded */
  const others=(inp.others||[]).slice().sort((a,b)=>b.key-a.key);
  const findElsewhere=sis=>{
    for(const o of others){
      const lines=o.sj.lines.filter(l=>sis.includes(l.si)); if(!lines.length) continue;
      if(o.sr&&!o.at){ o.m=matchListing(o.sr.rows,o.sj.lines); o.at=lineRows(o.m); }
      return {label:o.label, lines, rowFor:l=>o.at&&o.at.has(l)?o.m.rows[o.at.get(l)].r:null, hasSr:!!o.sr};
    }
    return null; };
  if(inp.defAccounts && inp.defAccounts.size){
    const sjNet={}; sj.forEach(l=>{ if(l.si) sjNet[l.si]=(sjNet[l.si]||0)+l.net; });
    out.deferred=glAll.filter(e=>inp.defAccounts.has(e.account)).map(e=>{
      const inSj=e.sis.filter(s=>s in sjNet);
      return {e, sis:e.sis, amt:e.cr-e.dr, kind:e.cr>=e.dr?"defer":"recognise", inSj, sjNet:inSj.reduce((a,s)=>a+sjNet[s],0),
              name:(sj.find(l=>inSj.includes(l.si))||{}).name||e.name||
                e.desc.replace(INV_RE_ALL,"").replace(/^\s*(and\s+)?/i,"").replace(/\b(to reverse|def+er+ed)\b.*$/i,"").trim()||e.desc};
    });
    /* a sale recognised this month was invoiced in an earlier month: find it in that month's Sales Journal */
    out.deferred.filter(d=>d.kind==="recognise"&&!d.inSj.length&&d.sis.length).forEach(d=>{
      const src=findElsewhere(d.sis); if(src){ d.src=src; d.name=src.lines[0].name; }
    });
  }

  /* invoice-by-invoice comparison needs the Sale of Goods GL itself, not only the discount / fee / deferred accounts */
  if(inp.sj && inp.gl && (!inp.accounts||inp.accounts.size)){
    const inv={}, get=si=>inv[si]=inv[si]||{si, sj:[], gl:[]};
    sj.forEach(l=>{ if(l.si) get(l.si).sj.push(l); });
    gl.forEach(e=>{ if(e.si) get(e.si).gl.push(e); else out.unlinkedGL.push(e); });
    out.invoices=Object.values(inv).map(v=>{
      v.name=(v.sj[0]&&v.sj[0].name)||(v.gl[0]&&v.gl[0].name)||"";
      v.sjNet=sumBy(v.sj,"net"); v.glNet=v.gl.reduce((a,e)=>a+e.cr-e.dr,0);
      v.diff=v.glNet-v.sjNet; v.notes=[]; v.review=false;
      if(!v.sj.length){ v.status="Only in GL"; v.review=true; }
      else if(!v.gl.length){ v.status="Only in Sales Journal"; v.review=true; }
      else if(v.diff===0) v.status="Agrees";
      else { v.status="Differs"; v.review=true; }
      const pos=v.sj.filter(l=>l.net>0), neg=v.sj.filter(l=>l.net<0);
      if(pos.length&&neg.length&&v.sjNet===0) v.notes.push("Issued and cancelled this month");
      else if(v.sj.length>1) v.notes.push("Appears "+v.sj.length+" times in the Sales Journal");
      if(neg.length&&!pos.length) v.notes.push("Only a cancellation this month — no sale on this invoice this month");
      v.gl.filter(e=>e.link==="description").forEach(e=>v.notes.push((e.voucher||"GL entry")+" included — the invoice number is in its description"));
      if(v.status==="Differs"){
        const disc=sumBy(v.sj,"disc"), vatable=sumBy(v.sj,"vatable");
        const fee=out.feeBySi&&out.feeBySi[v.si], gd=out.discBySi&&out.discBySi[v.si];
        if(fee && v.diff===-fee) v.explain="Packaging fee: matches the packaging-fee GL ("+fmt(fee)+")";
        else if(gd && v.diff===gd) v.explain="Sales discount: matches the Sales Discount GL ("+fmt(gd)+")";
        else if(disc && v.diff===disc) v.explain="GL is higher by exactly the Sales Journal discount ("+fmt(disc)+")";
        else if(vatable && v.diff===-vatable) v.explain="GL is lower by exactly this invoice's VATable sales ("+fmt(vatable)+")";
        else v.explain="No explanation found in the loaded files";
      }
      return v;
    }).sort((a,b)=>(b.review-a.review)||Math.abs(b.diff)-Math.abs(a.diff)||a.si.localeCompare(b.si));
    /* an invoice named on a Deferred Sales entry: if the deferral was also booked against Sale of Goods,
       the gap is the deferral, not a packaging fee */
    (out.deferred||[]).forEach(d=>{
      const vs=out.invoices.filter(v=>d.sis.includes(v.si)); if(!vs.length) return;
      const gap=vs.reduce((a,v)=>a+v.diff,0);
      vs.forEach(v=>{ v.deferred=(v.deferred||[]).concat([d]);
        v.notes.push((d.e.voucher||"Deferred Sales entry")+" on the Deferred Sales GL: "+(d.kind==="defer"?"deferred ":"recognised ")+fmt(Math.abs(d.amt))+
          (d.sis.length>1?" for "+d.sis.join(" and "):""));
        if(v.status!=="Agrees" && gap===-d.amt) v.explain="Deferred sales: matches "+(d.e.voucher||"the entry")+" on the Deferred Sales GL ("+fmt(d.amt)+")"; });
    });
    /* a sales adjustment: a JV on Sale of Goods that names one invoice only in its description, booked on top of
       the invoice (JV000004660, Mar 31 2026: "SI000002210 FRENT ... for CM on 3rd Qtr 2026", 45,035.75).
       It accounts for the whole gap, or it is not treated as one. */
    out.invoices.forEach(v=>{
      if(v.status==="Agrees"||v.deferred) return;
      /* a JV posted and then cancelled shows as a debit and a credit under one voucher: it nets to zero and is ignored
         (JV000004661, Jul 1 2026) */
      const byV={}; v.gl.filter(e=>e.link==="description"&&e.voucher&&e.sis.length===1).forEach(e=>(byV[e.voucher]=byV[e.voucher]||[]).push(e));
      const net=es=>es.reduce((s,e)=>s+e.cr-e.dr,0), vs=Object.keys(byV);
      const adj=[].concat(...vs.filter(k=>net(byV[k])!==0).map(k=>byV[k])), zero=vs.filter(k=>net(byV[k])===0);
      const a=net(adj);
      if(!adj.length||v.diff!==a) return;
      v.adjust=adj;
      v.explain="Sales adjustment: "+adj.map(e=>e.voucher+" ("+e.date+")").join(", ")+" names this invoice in its description ("+fmt(a)+")"+
        (zero.length?" · "+zero.join(", ")+" posted and reversed under the same voucher — nets to zero, ignored":"");
      if(!v.sj.length){ v.adjSrc=findElsewhere([v.si]); if(v.adjSrc) v.name=v.adjSrc.lines[0].name; }
    });
  }

  const T=out.totals;
  if(inp.sj) T.sj={exempt:sumBy(sj,"exempt"), zero:sumBy(sj,"zero"), taxable:sumBy(sj,"vatable")+sumBy(sj,"gov"), vat:sumBy(sj,"vat"),
                   gov:sumBy(sj,"gov"), nonvat:sumBy(sj,"nonvat"), disc:sumBy(sj,"disc"), amt:sumBy(sj,"amt"), net:sumBy(sj,"net")};
  if(inp.gl && (!inp.accounts||inp.accounts.size)) T.gl={net:gl.reduce((a,e)=>a+e.cr-e.dr,0)};
  const lt=rows=>({exempt:sumBy(rows,"exempt"), zero:sumBy(rows,"zero"), taxable:sumBy(rows,"taxable"), vat:sumBy(rows,"vat"),
                   net:sumBy(rows,"exempt")+sumBy(rows,"zero")+sumBy(rows,"taxable")});
  [["sr",inp.sr],["dat",inp.dat]].forEach(([k,src])=>{
    if(!src) return;
    T[k]=lt(src.rows);
    if(inp.sj) out.listings[k]=matchListing(src.rows, sj);
  });
  if(inp.ir!=null) T.ir={net:inp.ir};
  const noTinSrc=inp.dat||inp.sr;
  if(noTinSrc){
    const m=out.listings[inp.dat?"dat":"sr"];
    noTinSrc.rows.forEach((r,i)=>{ if(!tin9(r.tin)) out.noTin.push({r, match:m?m.rows[i]:null}); });
  }
  return out;
}

/* Income Statement (IR) revenue lines vs the GL accounts and Sales Journal they come from */
function irChecks(res, figs){
  const out=[], T=res.totals, add=(f,label,want,src)=>{
    if(!f||f.value==null) return;
    out.push({ok:f.value===want, label, msg:label+" "+fmt(f.value)+(f.value===want?" agrees with ":" ≠ ")+src+" ("+fmt(want)+")"}); };
  if(T.gl){ add(figs.sales,"Sale of Goods",T.gl.net,"the GL Sale of Goods");
    const c=out[out.length-1]; if(c&&!c.ok) c.msg+=" — if the GL was exported after the Income Statement, export the Income Statement again"; }
  /* without the Sale of Goods GL: Sale of Goods is credited before discount and without packaging fees */
  else if(T.sj) add(figs.sales,"Sale of Goods",sjSales(res),"the Sales Journal (net sales + discounts"+(res.feeNet!=null?" − packaging fees":"")+")");
  if(res.feeNet!=null) add(figs.fee,"Packaging Charges (Other Income)",res.feeNet,"the packaging-fee GL");
  if(res.defNet!=null) add(figs.deferred,"Deferred Sales",-res.defNet,"the Deferred Sales GL, debits less credits");
  /* discount lines (Sales Discounts, SC/PWD Discounts): each against its own GL account, else together against the Sales Journal */
  const done=new Set(), discLines=(figs.revenue||[]).filter(f=>/discount/i.test(f.label));
  if(figs.deferred&&res.defNet!=null) done.add(figs.deferred.label);
  if(res.discByAcct) Object.entries(res.discByAcct).forEach(([a,net])=>{
    const nm=norm(a.replace(/\s*\([^)]*\)\s*$/,"")), f=discLines.find(x=>norm(x.label)===nm);
    if(f){ done.add(f.label); add(f,f.label,net,a+" GL"); } });
  else if(T.sj && discLines.length){
    const sum=discLines.reduce((s,f)=>s+(f.value||0),0), lbl=discLines.map(f=>f.label).join(" + ");
    discLines.forEach(f=>done.add(f.label));
    out.push({ok:sum===-T.sj.disc, label:lbl, msg:lbl+" "+fmt(sum)+(sum===-T.sj.disc?" agrees with ":" ≠ ")+"the Sales Journal discounts ("+fmt(-T.sj.disc)+")"});
  }
  /* revenue lines this month that no loaded GL accounts for */
  (figs.revenue||[]).forEach(f=>{
    if(!f.value || done.has(f.label)) return;
    out.push({ok:false, label:f.label, msg:f.label+" "+fmt(f.value)+" is in Total Revenue this month"+
      (f.label===(figs.deferred&&figs.deferred.label)?" — load the Deferred Sales GL to see which invoices":" — no GL loaded for it, and no rule for it yet")});
  });
  return out;
}
/* what Sale of Goods should be, from the Sales Journal: net sales (after discount) + discounts − packaging fees */
const sjSales = res => res.totals.sj.net+res.totals.sj.disc-(res.feeNet||0);

/* Every listing row's TIN must be the TIN on its invoice in the Sales Journal. */
function tinChecks(res){
  const out=[];
  Object.entries(res.listings).forEach(([k,m])=>m.rows.forEach(x=>{
    if(!x.lines.length) return;
    const want=tin9(x.lines[0].tin), got=tin9(x.r.tin);
    if(want!==got) out.push({report:LISTING_LABEL[k], where:x.r.where, name:x.r.name,
      msg:"TIN is "+(got||"blank")+" but the Sales Journal has "+(want||"blank")+" for "+x.lines[0].si}); }));
  return out;
}

/* ---- Corrections: only the treatments the supervisor confirmed (Oct 2026) ----
   1. Invoices issued and cancelled in the same month: both rows left out.
   2. Discounts: sales reported after discount.
   3. Packaging fees: left out of the listing. A fee on a separate VATable line stays as VATable
      sales and the same amount is deducted from Exempt (so the listing balances with the IR).
   4. Deferred sales (Deferred Sales GL, 4400): reported in the month the sale is recognised, with its VAT —
      left out of the month invoiced, added in the month the deferral is reversed (supervisor, 17 Oct 2026).
   5. Sales adjustment JVs on Sale of Goods that name an invoice in their description: added under that invoice's
      customer as VATable sales with 12% Output VAT, in the JV's month (supervisor, 19 Oct 2026). The user can
      report a JV as Exempt or Zero-rated instead (step 4), since not every adjustment is VATable.
   SC/PWD discounts follow rule 2, like sales discounts (supervisor, 17 Oct 2026).
   Every change is logged against its invoice and source rows. Anything else that differs from
   its invoice is left exactly as reported and listed as open. */
const ADJ_CLASS={vatable:"VATable sales", exempt:"Exempt sales", zero:"Zero-rated sales"};
/* opts.adjClass: {"<GL file>#<row>": "vatable"|"exempt"|"zero"} — how each sales adjustment JV is reported */
function correctListing(res, key, opts){
  const m=res.listings[key]; if(!m) return null;
  const adjClass=(opts&&opts.adjClass)||{}, adjustments=[]; let feeOut=0;
  const LBL={exempt:"Exempt",zero:"Zero-rated",taxable:"VATable",vat:"Output VAT"}, COL={exempt:"exempt",zero:"zero",vatable:"taxable"};
  const rows=m.rows.map(x=>({x, r:Object.assign({},x.r), removed:false, touched:false}));
  /* one listing row per Sales Journal line */
  const rowOf=new Map(); lineRows(m).forEach((i,l)=>rowOf.set(l,rows[i]));
  /* each row remembers its invoice, for the per-customer breakdown */
  rowOf.forEach((o,l)=>{ o.r.inv={si:l.si, date:l.date, sjRow:l.row}; });
  const log=[], pending=[], open=[], added=[], label=LISTING_LABEL[key];
  const set=(o,col,val,rule,l,basis)=>{ o.touched=true;
    log.push({si:l.si, name:l.name, where:o.r.where, sjRow:l.row, rule, column:LBL[col], before:o.r[col], after:val, changed:o.r[col]!==val, basis:basis||""});
    o.r[col]=val; };
  const notFound=l=>open.push({si:l.si, name:l.name, where:"Sales Journal row "+l.row, msg:"Its row was not found in the "+label+" — nothing changed"});

  const bySi={}; res.sjLines.forEach(l=>{ if(l.si)(bySi[l.si]=bySi[l.si]||[]).push(l); });
  Object.values(bySi).forEach(ls=>{
    if(!(ls.some(l=>l.net>0)&&ls.some(l=>l.net<0)&&sumBy(ls,"net")===0)) return;
    ls.forEach(l=>{ const o=rowOf.get(l); if(!o) return notFound(l);
      o.removed=true; o.touched=true;
      log.push({si:l.si, name:l.name, where:o.r.where, sjRow:l.row, rule:"Issued and cancelled in the same month — row left out",
        column:"Whole row", before:o.r.exempt+o.r.zero+o.r.taxable, after:null, changed:true, basis:"Sales Journal: + and − lines on the same invoice"}); });
  });

  res.sjLines.filter(l=>l.disc).forEach(l=>{
    const o=rowOf.get(l); if(!o) return notFound(l); if(o.removed) return;
    const cols=["exempt","zero","vatable","gov","nonvat"].filter(c=>l[c]);
    let dBasis="Sales Journal discount "+fmt(l.disc);
    if(res.discBySi){
      const g=res.discBySi[l.si]||0;
      if(g!==l.disc){ o.touched=true; return open.push({si:l.si, name:l.name, where:o.r.where,
        msg:"Sales Journal discount "+fmt(l.disc)+" but the discount GLs show "+fmt(g)+" for this invoice — not changed"}); }
      dBasis+=" · discount GL: "+fmt(g);
    }
    if(cols.length===1 && (cols[0]==="exempt"||cols[0]==="zero") && !l.vat)
      set(o,COL[cols[0]],l[cols[0]]-l.disc,"Discount — sales reported after discount",l,dBasis);
    else open.push({si:l.si, name:l.name, where:o.r.where, msg:"Discount of "+fmt(l.disc)+" on an invoice with VATable or mixed sales — not changed. Decide which amounts it reduces."});
  });

  /* Deferred sales (supervisor, 17 Oct 2026): reported in the month the sale is recognised, with its Output VAT.
     The deferral month leaves the invoice out; the month the Deferred Sales GL reverses it adds the invoice,
     taken from that earlier month's Sales Journal. Only when the GL amount equals the invoices' net sales. */
  (res.deferred||[]).forEach(d=>{
    const sis=d.sis.join(", "), jv=(d.e.voucher||"Deferred Sales entry")+" ("+d.e.date+")", where=d.e.from+" row "+d.e.row;
    const no=msg=>open.push({si:sis||"(no invoice number)", name:d.name, where, msg:msg+" — nothing changed", deferred:d});
    if(!d.sis.length) return no(jv+" names no invoice number");
    if(d.kind==="defer"){
      const ls=res.sjLines.filter(l=>d.sis.includes(l.si)), net=sumBy(ls,"net");
      if(!ls.length) return no(jv+" defers "+fmt(d.amt)+" but "+sis+" is not in this month's Sales Journal");
      if(net!==d.amt) return no(jv+" defers "+fmt(d.amt)+" but "+sis+" has net sales of "+fmt(net)+". Only part of it is deferred — decide which amounts move");
      d.applied=true;
      return ls.forEach(l=>{ const o=rowOf.get(l); if(!o) return notFound(l); if(o.removed) return;
        o.removed=true; o.touched=true;
        log.push({si:l.si, name:l.name, where:o.r.where, sjRow:l.row, rule:"Deferred sale — left out, reported in the month it is recognised",
          column:"Whole row", before:o.r.exempt+o.r.zero+o.r.taxable, after:null, changed:true,
          basis:jv+" defers "+fmt(d.amt)+" · Exempt "+fmt(o.r.exempt)+(o.r.zero?" · Zero-rated "+fmt(o.r.zero):"")+" · VATable "+fmt(o.r.taxable)+" · Output VAT "+fmt(o.r.vat)+" move with it"}); });
    }
    if(d.inSj.length) return no(jv+" recognises "+fmt(-d.amt)+" deferred from an earlier month, but "+d.inSj.join(", ")+" is also in this month's Sales Journal — check it");
    if(!d.src) return no(jv+" recognises "+fmt(-d.amt)+" deferred from an earlier month. Load the Sales Journal (and Sales Relief) of the month "+sis+" was invoiced, so it can be added here");
    const ls=d.src.lines, net=sumBy(ls,"net");
    if(net!==-d.amt) return no(jv+" recognises "+fmt(-d.amt)+" but "+sis+" has net sales of "+fmt(net)+" in the "+d.src.label+" Sales Journal. Only part of it — decide which amounts move");
    const bad=ls.find(l=>l.disc&&!(l.exempt&&!l.vatable&&!l.gov&&!l.zero&&!l.vat));
    if(bad) return no(bad.si+" has a discount on VATable or mixed sales — decide which amounts it reduces");
    d.applied=true;
    ls.forEach(l=>{ const s=d.src.rowFor(l)||{};
      const r={where:"Added from "+d.src.label, tin:s.tin||l.tin, name:s.name||l.name, address:s.address||"",
               exempt:l.exempt-l.disc, zero:l.zero, taxable:l.vatable+l.gov, vat:l.vat,
               inv:{si:l.si, date:l.date, sjRow:l.row+" ("+d.src.label+")", added:true}};
      added.push(r);
      log.push({si:l.si, name:l.name, where:r.where, sjRow:l.row+" ("+d.src.label+")", rule:"Deferred sale — added in the month it is recognised",
        column:"Whole row", before:null, after:r.exempt+r.zero+r.taxable, changed:true, added:true,
        basis:jv+" recognises "+fmt(-d.amt)+" · invoiced "+l.date+" · Exempt "+fmt(r.exempt)+" · VATable "+fmt(r.taxable)+" · Output VAT "+fmt(r.vat)+
          (s.tin==null?" · customer from the Sales Journal"+(d.src.hasSr?" (no matching Sales Relief row)":"")+", address blank":"")}); });
  });

  /* Sales adjustment JV (supervisor, 19 Oct 2026): a JV on Sale of Goods that names an invoice in its description
     is reported in the JV's month under that invoice's customer, as VATable sales with 12% Output VAT, on a row
     of its own — the invoice's own row stays as invoiced. A debit (e.g. a credit memo) goes in the same way, negative. */
  res.invoices.filter(v=>v.adjust).forEach(v=>{
    const vs=v.adjust.map(e=>e.voucher).join(", ");
    let l=v.sj[0], s=null, from="";
    if(l){ const o=rowOf.get(l); s=o?o.r:null; }
    else if(v.adjSrc){ l=v.adjSrc.lines[0]; s=v.adjSrc.rowFor(l); from=" ("+v.adjSrc.label+")"; }
    if(!l) return open.push({si:v.si, name:v.name||v.adjust[0].desc, where:v.adjust[0].from+" row "+v.adjust[0].row,
      msg:vs+" names "+v.si+", which is not in this month's Sales Journal. Load the Sales Journal (and Sales Relief) of the month it was invoiced, to know the customer — nothing changed"});
    v.adjust.forEach(e=>{
      /* VATable unless the user picked Exempt or Zero-rated for this JV in step 4 */
      const id=e.from+"#"+e.row, chosen=adjClass[id], cls=chosen||"vatable";
      const amt=e.cr-e.dr, vat=cls==="vatable"?Math.sign(amt)*Math.round(Math.abs(amt)*0.12):0;
      const r={where:"Added from "+e.voucher, tin:s?s.tin:l.tin, name:s?s.name:l.name, address:s&&s.address||"",
               exempt:cls==="exempt"?amt:0, zero:cls==="zero"?amt:0, taxable:cls==="vatable"?amt:0, vat,
               inv:{si:v.si, date:e.date, sjRow:"GL row "+e.row+" · "+e.voucher, added:true}};
      added.push(r);
      adjustments.push({id, voucher:e.voucher, date:e.date, si:v.si, name:r.name, amt, vat, cls, chosen:!!chosen, desc:e.desc.replace(/\s+/g," "), row:e.row});
      log.push({si:v.si, name:r.name, where:r.where, sjRow:l.row+from,
        rule:"Sales adjustment JV — reported as "+ADJ_CLASS[cls]+(cls==="vatable"?" with 12% Output VAT":"")+(chosen?" (chosen in step 4)":""),
        column:"Whole row", before:null, after:amt, changed:true, added:true,
        basis:e.voucher+" ("+e.date+") on "+e.account+", GL row "+e.row+": "+e.desc.replace(/\s+/g," ")+" · "+ADJ_CLASS[cls]+" "+fmt(amt)+
          (cls==="vatable"?" · Output VAT "+fmt(vat)+" (12%, computed — not in the Sales Journal)":"")+(s?"":" · customer from the Sales Journal, address blank")});
    });
  });

  /* An invoice in the Sales Journal that the Sale of Goods GL never credited: left out when the packaging-fee GL
     shows the whole amount as a fee (an invoice for the fee alone); otherwise left as reported and listed. */
  res.invoices.filter(v=>v.status==="Only in Sales Journal"&&!v.deferred).forEach(v=>{
    const ls=v.sj.filter(l=>{ const o=rowOf.get(l); return !(o&&o.removed); }), net=sumBy(ls,"net"); if(!ls.length||!net) return;
    const f=res.feeBySi&&res.feeBySi[v.si];
    if(f && f===net && ls.every(l=>!l.vat)){
      return ls.forEach(l=>{ const o=rowOf.get(l); if(!o) return notFound(l);
        o.removed=true; o.touched=true; feeOut++;
        log.push({si:l.si, name:l.name, where:o.r.where, sjRow:l.row, rule:"Packaging fee only — row left out", column:"Whole row",
          before:o.r.exempt+o.r.zero+o.r.taxable, after:null, changed:true, basis:"Not credited to Sale of Goods · packaging-fee GL: "+fmt(f)}); }); }
    ls.forEach(l=>{ const o=rowOf.get(l); if(o) o.touched=true; });
    open.push({si:v.si, name:v.name, where:"Sales Journal row "+ls.map(l=>l.row).join(", "), irEffect:-net,
      msg:"In the Sales Journal ("+fmt(net)+") but not in the Sale of Goods GL — left as reported."+
        (res.feeBySi?(f?" The packaging-fee GL shows "+fmt(f)+" for it":""):" If it is a packaging fee, load this month\x27s packaging-fee GL (Packaging Charges) to confirm")});
  });

  /* Non-VAT Sales: the Sales Relief and the DAT have no Non-VAT column, so Oojeema leaves the amount out of the Sales Relief */
  res.sjLines.filter(l=>l.nonvat).forEach(l=>{ const o=rowOf.get(l); if(o&&o.removed) return; if(o) o.touched=true;
    open.push({si:l.si, name:l.name, where:o?o.r.where:"Sales Journal row "+l.row, irEffect:key==="sr"?l.nonvat:0,
      msg:"Non-VAT Sales of "+fmt(l.nonvat)+" (Sales Journal row "+l.row+") is not in the "+label+", which has no Non-VAT column — nothing changed. Decide how to report it (Exempt?)"}); });

  res.invoices.filter(v=>v.status==="Differs"&&!v.deferred&&!v.adjust).forEach(v=>{
    const pos=v.sj.filter(l=>l.net>0), disc=sumBy(v.sj,"disc"), vatable=sumBy(v.sj,"vatable");
    if(v.diff>0){ if(disc && v.diff===disc) return;
      return open.push({si:v.si, name:v.name, where:"", msg:"GL is "+fmt(v.diff)+" higher than the Sales Journal — no confirmed rule, not changed"}); }
    const fee=-v.diff;
    if(pos.length!==1) return open.push({si:v.si, name:v.name, where:"", msg:"Gap of "+fmt(fee)+" on an invoice with several Sales Journal lines — not changed"});
    const l=pos[0], o=rowOf.get(l); if(!o) return notFound(l);
    o.touched=true;   /* reported once, below — not again as an unexplained difference */
    let basis="Sales Journal less GL Sale of Goods: "+fmt(fee);
    if(res.feeBySi){
      const f=res.feeBySi[v.si]||0;
      if(f!==fee && !(vatable===fee && f===l.vatable+l.vat))
        return open.push({si:v.si, name:v.name, where:o.r.where, msg:"Gap of "+fmt(fee)+" but the packaging-fee GL shows "+fmt(f)+" for this invoice — not changed"});
      basis="Packaging-fee GL: "+fmt(f);
    }
    if(vatable && vatable===fee){
      /* Supervisor, 15 Oct 2026: a VATable packaging fee stays in the listing as VATable sales (with its VAT)
         and the same amount is deducted from Exempt, so the listing balances with the IR. */
      if(l.exempt>=fee) set(o,"exempt",l.exempt-fee,"Packaging fee on a VATable line — kept as VATable, same amount deducted from Exempt",l,
        basis+" · VATable "+fmt(l.vatable)+" and VAT "+fmt(l.vat)+" stay as reported");
      else open.push({si:v.si, name:v.name, where:o.r.where, msg:"VATable packaging fee of "+fmt(fee)+" is larger than the Exempt sales ("+fmt(l.exempt)+") it should be deducted from — not changed"});
    } else if(!l.vatable && l.exempt>=fee){
      set(o,"exempt",l.exempt-fee,"Packaging fee left out",l,basis);
    } else if(l.exempt>=fee && Math.abs(l.vat-Math.round(l.vatable*0.12))<=5){
      set(o,"exempt",l.exempt-fee,"Packaging fee left out",l,basis+" (VATable sales and their 12% VAT agree, so the fee is in Exempt)");
    } else open.push({si:v.si, name:v.name, where:o.r.where, msg:"Gap of "+fmt(fee)+" could not be placed in a sales column — not changed"});
  });

  rows.forEach(o=>{ if(o.touched) return;
    if(o.x.status==="differs") open.push({si:o.x.lines[0].si, name:o.r.name, where:o.r.where, msg:"Differs from its invoice line, and no confirmed rule explains it — left as reported"});
    else if(o.x.status==="unmatched") open.push({si:"", name:o.r.name, where:o.r.where, msg:"No matching Sales Journal line — left as reported"}); });

  const kept=rows.filter(o=>!o.removed).map(o=>o.r), out=kept.concat(added);
  const t={exempt:sumBy(out,"exempt"), zero:sumBy(out,"zero"), taxable:sumBy(out,"taxable"), vat:sumBy(out,"vat")}; t.net=t.exempt+t.zero+t.taxable;
  return {key, rows:out, log, pending, open, removed:rows.length-kept.length, added:added.length,
          adjusted:adjustments.length, adjustments, feeOut,
          deferredOut:log.filter(e=>/^Deferred sale — left out/.test(e.rule)).length, totals:t};
}
/* src: the listing ({taxpayer, month, year}), plus book (address book), rdo, fy */
function buildCorrectedDAT(cor, src){
  let rows=cor.rows.map(r=>({month:src.month, year:src.year, tin:r.tin, name:r.name, address:r.address||"",
    exempt:r.exempt/100, zero:r.zero/100, taxable:r.taxable/100, vat:r.vat/100, inv:r.inv, where:r.where}));
  const merge=src.perCustomer?oneRowPerCustomer(rows):null; if(merge) rows=merge.rows;
  const out=buildDAT({taxpayer:src.taxpayer, rows}, {book:src.book, rdo:src.rdo, fyMonth:src.fy});
  out.merge=merge; out.rows=rows;
  out.checks=checkDAT(out.text, out.filename, rows.length);
  return out;
}

/* ================= tiny .xlsx writer (stored zip, no compression) ================= */
const CRC=(()=>{ const t=new Uint32Array(256); for(let n=0;n<256;n++){ let c=n; for(let k=0;k<8;k++) c=c&1?0xEDB88320^(c>>>1):c>>>1; t[n]=c>>>0; } return t; })();
function crc32(u8){ let c=0xFFFFFFFF; for(let i=0;i<u8.length;i++) c=CRC[(c^u8[i])&0xFF]^(c>>>8); return (c^0xFFFFFFFF)>>>0; }
function zipStore(files){
  const te=new TextEncoder(), parts=[], central=[]; let off=0;
  files.forEach(f=>{
    const name=te.encode(f.name), data=typeof f.data==="string"?te.encode(f.data):f.data, crc=crc32(data);
    const lh=new DataView(new ArrayBuffer(30));
    lh.setUint32(0,0x04034b50,true); lh.setUint16(4,20,true); lh.setUint16(6,0x0800,true); lh.setUint16(8,0,true);
    lh.setUint16(10,0,true); lh.setUint16(12,33,true); lh.setUint32(14,crc,true); lh.setUint32(18,data.length,true);
    lh.setUint32(22,data.length,true); lh.setUint16(26,name.length,true); lh.setUint16(28,0,true);
    const ch=new DataView(new ArrayBuffer(46));
    ch.setUint32(0,0x02014b50,true); ch.setUint16(4,20,true); ch.setUint16(6,20,true); ch.setUint16(8,0x0800,true);
    ch.setUint16(10,0,true); ch.setUint16(12,0,true); ch.setUint16(14,33,true); ch.setUint32(16,crc,true);
    ch.setUint32(20,data.length,true); ch.setUint32(24,data.length,true); ch.setUint16(28,name.length,true);
    ch.setUint32(42,off,true);
    parts.push(new Uint8Array(lh.buffer),name,data); central.push(new Uint8Array(ch.buffer),name);
    off+=30+name.length+data.length;
  });
  const cdSize=central.reduce((a,b)=>a+b.length,0), end=new DataView(new ArrayBuffer(22));
  end.setUint32(0,0x06054b50,true); end.setUint16(8,files.length,true); end.setUint16(10,files.length,true);
  end.setUint32(12,cdSize,true); end.setUint32(16,off,true);
  const all=[...parts,...central,new Uint8Array(end.buffer)], out=new Uint8Array(all.reduce((a,b)=>a+b.length,0));
  let p=0; all.forEach(b=>{ out.set(b,p); p+=b.length; }); return out;
}
const xesc = s => String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;")
  .replace(/[\x00-\x08\x0B\x0C\x0E-\x1F]/g,"");
const colName = i => { let s=""; i++; while(i){ const m=(i-1)%26; s=String.fromCharCode(65+m)+s; i=(i-m-1)/26; } return s; };
/* sheets: [{name, widths:[..], rows:[[cell,..],..]}]; cell = string | number | {v, bold} | {peso: centavos} */
function buildXlsx(sheets){
  const NS='xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"';
  const sheetXml=s=>{
    let x='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet '+NS+'><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>';
    if(s.widths) x+='<cols>'+s.widths.map((w,i)=>'<col min="'+(i+1)+'" max="'+(i+1)+'" width="'+w+'" customWidth="1"/>').join("")+'</cols>';
    x+='<sheetData>';
    s.rows.forEach((r,i)=>{
      x+='<row r="'+(i+1)+'">';
      r.forEach((cell,j)=>{
        if(cell==null||cell==="") return;
        const ref=colName(j)+(i+1), bold=i===0||(typeof cell==="object"&&cell.bold);
        let v=cell; if(typeof cell==="object") v=("peso" in cell)?cell.peso/100:cell.v;
        if(typeof v==="number") x+='<c r="'+ref+'" s="'+(bold?3:1)+'"><v>'+v+'</v></c>';
        else x+='<c r="'+ref+'" t="inlineStr"'+(bold?' s="2"':'')+'><is><t xml:space="preserve">'+xesc(v)+'</t></is></c>';
      });
      x+='</row>';
    });
    return x+'</sheetData></worksheet>';
  };
  const files=[
    {name:"[Content_Types].xml", data:'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'+sheets.map((s,i)=>'<Override PartName="/xl/worksheets/sheet'+(i+1)+'.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>').join("")+'</Types>'},
    {name:"_rels/.rels", data:'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'},
    {name:"xl/workbook.xml", data:'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook '+NS+' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'+sheets.map((s,i)=>'<sheet name="'+xesc(s.name.replace(/[\[\]:*?\/\\]/g,"").slice(0,31))+'" sheetId="'+(i+1)+'" r:id="rId'+(i+1)+'"/>').join("")+'</sheets></workbook>'},
    {name:"xl/_rels/workbook.xml.rels", data:'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+sheets.map((s,i)=>'<Relationship Id="rId'+(i+1)+'" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet'+(i+1)+'.xml"/>').join("")+'<Relationship Id="rId'+(sheets.length+1)+'" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>'},
    {name:"xl/styles.xml", data:'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet '+NS+'><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="4"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="4" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/><xf numFmtId="4" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1" applyNumberFormat="1"/></cellXfs></styleSheet>'}
  ];
  sheets.forEach((s,i)=>files.push({name:"xl/worksheets/sheet"+(i+1)+".xml", data:sheetXml(s)}));
  return zipStore(files);
}

const LISTING_LABEL={sr:"Sales Relief", dat:"DAT"};
const MATCH_LABEL={exact:"Matches one invoice", group:"Matches a group of identical invoices", differs:"Same customer, amounts differ", unmatched:"No matching invoice line"};
function reconSheets(res, src){
  const P=c=>({peso:c}), sheets=[];
  const T=res.totals, cols=["exempt","zero","taxable","vat","net"];
  const sum=[["Report","Exempt","Zero-rated","VATable","Output VAT","Net sales","Notes"]];
  const line=(lbl,t,note)=>sum.push([lbl].concat(cols.map(k=>t&&t[k]!=null?P(t[k]):"")).concat([note||""]));
  if(T.sj) line("Sales Journal",T.sj,"Net sales = Amount − Output VAT. Category columns are before discount (discounts "+fmt(T.sj.disc)+").");
  if(T.gl) line("GL (selected accounts)",T.gl,"Credits less debits for the month, beginning balance excluded");
  if(T.sr) line("Sales Relief",T.sr,"Net sales = exempt + zero-rated + VATable");
  if(T.dat) line("DAT",T.dat,"Net sales = exempt + zero-rated + VATable");
  if(T.ir) line("IR / Income Statement",T.ir,"Typed figure");
  sum.push([]);
  sum.push([{v:"Counts",bold:true}]);
  if(res.invoices.length){
    const by=s=>res.invoices.filter(v=>v.status===s).length;
    sum.push(["Invoices compared",res.invoices.length],["Agree",by("Agrees")],["Differ",by("Differs")],
             ["Only in Sales Journal",by("Only in Sales Journal")],["Only in GL",by("Only in GL")],
             ["Needing review",res.invoices.filter(v=>v.review).length],["GL entries with no invoice number",res.unlinkedGL.length]);
  }
  Object.entries(res.listings).forEach(([k,m])=>{
    const by=s=>m.rows.filter(x=>x.status===s).length;
    sum.push([LISTING_LABEL[k]+" rows",m.rows.length],["  "+MATCH_LABEL.exact,by("exact")],["  "+MATCH_LABEL.group,by("group")],
             ["  "+MATCH_LABEL.differs,by("differs")],["  "+MATCH_LABEL.unmatched,by("unmatched")],
             ["  Sales Journal lines not in "+LISTING_LABEL[k],m.missing.length]);
  });
  sum.push(["Rows without TIN",res.noTin.length]);
  sheets.push({name:"Summary", widths:[38,16,14,16,16,16,70], rows:sum});

  if(res.invoices.length){
    const rows=[["Invoice","Customer","Status","Needs review","Sales Journal net","GL net","Difference (GL − SJ)","Explanation","Notes","Sales Journal rows","GL rows"]];
    res.invoices.forEach(v=>rows.push([v.si,v.name,v.status,v.review?"Yes":"",P(v.sjNet),P(v.glNet),P(v.diff),v.explain||"",v.notes.join("; "),
      v.sj.map(l=>l.row).join(", "),v.gl.map(e=>e.row).join(", ")]));
    res.unlinkedGL.forEach(e=>rows.push(["(none)",e.name||e.desc,"GL entry with no invoice number","Yes","",P(e.cr-e.dr),"","",e.voucher+" "+e.desc,"",String(e.row)]));
    sheets.push({name:"Invoices", widths:[14,40,22,12,16,16,18,52,60,14,12], rows});
  }
  if(res.deferred&&res.deferred.length){
    const rows=[["Date","Voucher","Invoice(s)","Customer","Debit","Credit","Effect on IR Total Revenue","In this month's Sales Journal","Sales Journal net","Description","GL row"]];
    res.deferred.forEach(d=>rows.push([d.e.date,d.e.voucher,d.sis.join(", "),d.name,P(d.e.dr),P(d.e.cr),P(-d.amt),
      d.inSj.length?d.inSj.join(", "):d.src?"No — invoiced in "+d.src.label:"No",d.inSj.length?P(d.sjNet):"",d.e.desc,d.e.from+" row "+d.e.row]));
    sheets.push({name:"Deferred sales", widths:[14,14,30,40,14,14,20,26,16,60,30], rows});
  }
  Object.entries(res.listings).forEach(([k,m])=>{
    const rows=[["Where","Customer","TIN","Exempt","Zero-rated","VATable","Output VAT","Match","Invoice(s)","Diff exempt","Diff zero-rated","Diff VATable","Diff VAT"]];
    m.rows.forEach(x=>{ const r=x.r, d=x.diff||{};
      rows.push([r.where,r.name,r.tin,P(r.exempt),P(r.zero),P(r.taxable),P(r.vat),MATCH_LABEL[x.status]+(x.status==="group"?" ("+x.lines.length+")":""),
        x.lines.map(l=>l.si).join(", "), d.exempt!=null?P(d.exempt):"", d.zero!=null?P(d.zero):"", d.taxable!=null?P(d.taxable):"", d.vat!=null?P(d.vat):""]); });
    m.missing.forEach(o=>rows.push(["Sales Journal row "+o.l.row,o.l.name,o.l.tin,P(o.l.exempt),P(o.l.zero),P(o.l.vatable),P(o.l.vat),"Not in "+LISTING_LABEL[k],o.l.si]));
    sheets.push({name:LISTING_LABEL[k]+" rows", widths:[24,44,20,14,12,14,14,36,40,12,12,12,12], rows});
  });
  if(res.noTin.length){
    const rows=[["Where","Customer","Exempt","Zero-rated","VATable","Output VAT","Invoice(s)"]];
    res.noTin.forEach(o=>rows.push([o.r.where,o.r.name,P(o.r.exempt),P(o.r.zero),P(o.r.taxable),P(o.r.vat),o.match?o.match.lines.map(l=>l.si).join(", "):""]));
    sheets.push({name:"No TIN", widths:[24,44,14,12,14,14,40], rows});
  }
  const cor=src.cor;
  if(cor){
    const rows=[["Invoice","Customer","Rule","Column","Before","After","Changed","Basis","Listing row","Sales Journal row"]];
    cor.log.forEach(e=>rows.push([e.si,e.name,e.rule,e.column,e.before==null?"":P(e.before),e.after==null?"left out":P(e.after),e.added?"Added":e.changed?"Yes":"No (already so)",e.basis,e.where,e.sjRow]));
    sheets.push({name:"Corrections", widths:[14,40,46,12,14,14,16,60,30,16], rows});
    const op=[["Type","Invoice","Customer","Where","Detail"]];
    cor.pending.forEach(p=>op.push(["Decision pending",p.si,p.name,p.where,p.msg]));
    cor.open.forEach(p=>op.push(["Left as reported",p.si,p.name,p.where,p.msg]));
    sheets.push({name:"Open items", widths:[18,14,40,30,100], rows:op});
    const nm=[["Name in Oojeema","TIN","Name in the DAT","Why","Worth checking"]];
    nameChanges(cor.rows).forEach(x=>nm.push([x.original,x.tin,x.dat,x.why,x.check?"Yes":""]));
    sheets.push({name:"Names", widths:[60,20,60,18,16], rows:nm});
  }
  if(src.fixOut){
    const pc=v=>({peso:Math.round(v*100)}), rows=[["Customer / invoice","TIN","Invoices","Exempt","Zero-rated","VATable","Output VAT","Date","Sales Journal row","Listing row"]];
    src.fixOut.rows.forEach(r=>{ const parts=r.parts||[r];
      const one=parts.length===1&&parts[0].inv||{};
      rows.push([{v:r.name,bold:true},r.tin||"",parts.length>1?parts.length:(one.si||1),pc(r.exempt),pc(r.zero),pc(r.taxable),pc(r.vat)].concat(parts.length>1?[]:[one.date||"",one.sjRow!=null?String(one.sjRow):"",parts[0].where||""]));
      if(parts.length>1) parts.forEach(p=>{ const v=p.inv||{};
        rows.push(["    "+(v.si||"(no invoice matched)")+(v.added?" (added)":""),"","",pc(p.exempt),pc(p.zero),pc(p.taxable),pc(p.vat),v.date||"",v.sjRow!=null?String(v.sjRow):"",p.where||""]); }); });
    sheets.push({name:"DAT lines", widths:[52,20,10,14,12,14,14,14,20,30], rows});
  }
  const iss=[["Report","Where","Name","Check"]];
  (src.issues||[]).forEach(i=>iss.push([i.report,i.where,i.name||"",i.msg]));
  sheets.push({name:"Source checks", widths:[16,30,40,90], rows:iss});
  return sheets;
}


export {parseCSV,parseOojeema,parseOojeemaRows,buildDAT,validate,checkDAT,tinMap,datToSalesReliefCSV,addressBook,splitAddr,
  clean,cleanName,nameKey,datName,nameChanges,NAME_EXCEPTIONS,tin9,readXlsx,classify,parseIS,isFigures,irChecks,lineRows,
  oneRowPerCustomer,sjSales,entryMonth,parseSJ,parseGL,mergeGLAccounts,parseSRGrid,listingFromSR,parseDATListing,matchListing,
  reconcile,tinChecks,correctListing,buildCorrectedDAT,buildXlsx,reconSheets,fmt,C,MON,zipStore,sumBy,
  LISTING_LABEL,MATCH_LABEL,ADJ_CLASS};
