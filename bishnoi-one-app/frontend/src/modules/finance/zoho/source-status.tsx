export type SourceCoverageData={mode?:string;windowStart:string;windowEnd:string;partial:boolean;error:string|null;finishedAt:string;summaryComplete?:boolean;pendingDetails?:number;getRequests?:number;intervalSeconds?:number};
export function sourceDate(value:string){return new Intl.DateTimeFormat('en-PH',{dateStyle:'medium'}).format(new Date(value+'T12:00:00Z'));}
export function sourceSaved(value:string){return new Intl.DateTimeFormat('en-PH',{dateStyle:'medium',timeStyle:'short',timeZone:'Asia/Manila'}).format(new Date(value.endsWith('Z')||/[+-]\d\d:\d\d$/.test(value)?value:value+'Z'));}
export function sourceAmount(cents:number|null|undefined,currency:string){if(cents===null||cents===undefined)return '—';return /^[A-Z]{3}$/.test(currency)?new Intl.NumberFormat('en-PH',{style:'currency',currency}).format(cents/100):`${(cents/100).toFixed(2)} (currency missing)`;}
export function SourceCoverage({coverage}:{coverage:SourceCoverageData|null}){
 if(!coverage)return <p role="status" className="mb-4 text-sm text-ink-2">No saved update for this period. Try All saved dates or ask the administrator to check the connection.</p>;
 const partial=coverage.mode!=='month-sync'||!coverage.summaryComplete;
 return <div className="mb-4 text-meta text-ink-2">
  <p role="status">Saved {sourceSaved(coverage.finishedAt)}. {coverage.error?'Last update paused; saved records remain available.':partial?'Saved coverage is incomplete.':'Summary scan completed.'} {(coverage.pendingDetails??0)>0&&'Some record details are still downloading.'}</p>
  <details data-source-coverage className="mt-1">
   <summary className="w-fit cursor-pointer text-ink-3 hover:text-ink">Update details</summary>
   <div className="mt-2 space-y-1 border-l-2 border-rule pl-3 text-ink-3">
    <p>Saved window: {sourceDate(coverage.windowStart)} to {sourceDate(coverage.windowEnd)}.</p>
    {coverage.pendingDetails!==undefined&&<p>{coverage.pendingDetails.toLocaleString('en-PH')} records await full details. This is background work; no manual entry is needed.</p>}
    <p>{coverage.mode==='month-sync'?`Background checks target every ${Math.round((coverage.intervalSeconds??300)/60)} minutes while the local updater is running. Limits and outages can delay them.`:'Limited saved history; this is not the complete Zoho history.'}</p>
    <p>Lists refresh saved data about every minute while open. Refresh pauses while you type or read expanded details. These pages do not contact Zoho.</p>
   </div>
  </details>
 </div>;
}
