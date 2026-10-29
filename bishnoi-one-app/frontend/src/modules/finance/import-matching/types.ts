// Import matching and Zoho export imports (the API's app/routers/imports.py).
export type Section='company'|'account'|'tax'|'money';
export type MatchStatus='open'|'proposed'|'confirmed';
export type Match={id:string;section:Section;sourceLabel:string;sourceCode:string|null;records:number;amountCentavos:number;status:MatchStatus;note:string|null;accountId:string|null;account:{id:string;code:string;name:string}|null;purchaseType:string|null;vatKind:string|null;company:string|null;proposedBy:string|null;proposedAt:string|null;confirmedBy:string|null;confirmedAt:string|null;seenAt:string|null;canPropose:boolean;savesConfirmed:boolean;automatic:boolean;canConfirm:boolean;waitingOn:string|null;mine:boolean;perRecord:boolean;rules:{proposed:number;confirmed:number}};
export type Option={key:string;label:string};
export type Matching={matches:Match[];counts:Record<Section,Record<MatchStatus,number>>;choices:{lineAccounts:{id:string;code:string;name:string;type:string}[];moneyAccounts:{id:string;code:string;name:string}[];purchaseTypes:Option[];vatKinds:Option[];companies:Option[]};may:{propose:boolean;confirm:boolean;confirm_tax:boolean;run:boolean};importsHere:boolean;runs:{id:string;kind:string;files:string[];counts:Record<string,number>;by:string;at:string}[]};
export type Proposal={accountId?:string|null;purchaseType?:string|null;vatKind?:string|null;company?:string|null;note?:string|null;perRecord?:boolean};
export type Rule={id:string;scope:'supplier'|'line';supplier:string;billSourceId:string|null;billNumber:string|null;linePosition:number|null;lineAmountCentavos:number|null;accountId:string|null;account:{id:string;code:string;name:string}|null;purchaseType:string|null;vatKind:string|null;status:'proposed'|'confirmed';note:string|null;proposedBy:string;proposedAt:string|null;confirmedBy:string|null;confirmedAt:string|null;canConfirm:boolean;canRemove:boolean};
export type RuleIn={scope:'supplier'|'line';supplier:string;billSourceId?:string;billNumber?:string;linePosition?:number;lineAmountCentavos?:number;accountId?:string|null;purchaseType?:string|null;vatKind?:string|null};
export type ImportKind='bills'|'supplier-payments';
export type Outcome='ready'|'held'|'skipped'|'imported';
export type ImportRow={sourceId:string;number:string;party:string;date:string;total:number;company:string;reasons:string[];outcome:Outcome;billId?:string;voucherId?:string};
export type ImportPlan={counts:Record<Outcome,number>;reasons:{reason:string;records:number}[];planKey:string;rows:ImportRow[];runId?:string};
export type SourceFile={name:string;content:string};
export type LabelRecords={label:string;section:Section;total:number;amountCentavos:number;shown:number;perRecord?:boolean;rows:{kind:string;number:string;date:string;party:string;amount:number;description:string;account:string;tax:string;company:string;billSourceId?:string;linePosition?:number;accountId?:string|null;accountIdFrom?:string|null;accountName?:string|null;purchaseType?:string|null;purchaseTypeFrom?:string|null;vatKind?:string|null;vatKindFrom?:string|null;changed?:boolean}[]};
/** The permissions that open Import matching: any one of them. */
export const IMPORT_TICKS=['imports.propose','imports.confirm','imports.confirm_tax','imports.run'];
export const money=(n:number)=>new Intl.NumberFormat('en-PH',{style:'currency',currency:'PHP'}).format(n/100);
/** A date the API gives, the same on the server and in the browser (Manila time). */
export const day=(at:string|null)=>at?new Intl.DateTimeFormat('en-PH',{dateStyle:'medium',timeZone:'Asia/Manila'}).format(new Date(at)):'';
/** The two CSVs picked together, read in the browser. */
export async function readPair(picked:File[]):Promise<SourceFile[]>{
 if(picked.length!==2)throw new Error('Choose both files together: the Zoho Bills export and the Vendor Payments export.');
 if(picked.some(f=>!f.name.toLowerCase().endsWith('.csv')))throw new Error('Choose the two CSV files exported from Zoho.');
 if(picked.reduce((n,f)=>n+f.size,0)>16*1024*1024)throw new Error('These files total more than 16 MB. Nothing was loaded.');
 return Promise.all(picked.map(async file=>({name:file.name,content:await file.text()})));
}
/** Sends the two files through this site's own route, which passes them to the API. */
export async function send<T>(path:string,body:unknown):Promise<T>{
 const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 const data=await response.json().catch(()=>null);
 if(!response.ok)throw new Error(typeof data?.detail==='string'?data.detail:'This could not finish. Nothing was changed.');
 return data as T;
}
