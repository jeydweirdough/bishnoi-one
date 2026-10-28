"use server";
import {api} from '../platform/lib/api';
import {attempt} from '../platform/lib/result';
export async function startZoho(outbound=false){return attempt(()=>api.post<{url:string}>('/finance/integrations/zoho/start'+(outbound?'?outbound=true':''),{}));}
export async function checkZoho(){return attempt(()=>api.post<{organizations:Organization[]}>('/finance/integrations/zoho/check',{}));}
export async function chooseZoho(id:string){return attempt(()=>api.post('/finance/integrations/zoho/organization',{organizationId:id}));}
export async function disconnectZoho(){return attempt(()=>api.post('/finance/integrations/zoho/disconnect',{}));}
export type Organization={id:string;name:string;currency:string};

export async function pauseZohoUpdater(paused:boolean){return attempt(()=>api.post('/finance/integrations/zoho/updater',{paused}));}
