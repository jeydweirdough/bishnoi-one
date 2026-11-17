// When the Zoho reader last saved (the connection page). The read-only Zoho lists were removed on 2026-11-17.
export function sourceSaved(value:string){return new Intl.DateTimeFormat('en-PH',{dateStyle:'medium',timeStyle:'short',timeZone:'Asia/Manila'}).format(new Date(value.endsWith('Z')||/[+-]\d\d:\d\d$/.test(value)?value:value+'Z'));}
