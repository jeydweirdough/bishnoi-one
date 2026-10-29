"use server";
import {refresh} from 'next/cache';
import {api,enc} from '@/src/modules/finance/platform/lib/api';
import {attempt,type Result} from '@/src/modules/finance/platform/lib/result';
import type {Match,Proposal,Rule,RuleIn} from './types';

// Import matching: saved by someone who may confirm that section, it's final; otherwise a proposal
// (tax labels: BIR and Compliance). The API checks who may do each (app/routers/imports.py).

export async function proposeMatch(id:string,body:Proposal):Promise<Result<Match>>{
 return attempt(async()=>{const saved=await api.put<Match>(`/finance/imports/matching/${enc(id)}`,body);refresh();return saved;});
}

export async function confirmMatch(id:string):Promise<Result<Match>>{
 return attempt(async()=>{const saved=await api.post<Match>(`/finance/imports/matching/${enc(id)}/confirm`);refresh();return saved;});
}

// Supplier rules and line choices, for a label that depends on the record (or to change one supplier's
// or line's purchase type).
export async function loadRules(matchId:string):Promise<Result<{rules:Rule[]}>>{
 return attempt(()=>api.get<{rules:Rule[]}>(`/finance/imports/matching/${enc(matchId)}/rules`));
}

export async function saveRule(matchId:string,body:RuleIn):Promise<Result<Rule>>{
 return attempt(async()=>{const saved=await api.post<Rule>(`/finance/imports/matching/${enc(matchId)}/rules`,body);refresh();return saved;});
}

export async function confirmRule(id:string):Promise<Result<Rule>>{
 return attempt(async()=>{const saved=await api.post<Rule>(`/finance/imports/rules/${enc(id)}/confirm`);refresh();return saved;});
}

export async function removeRule(id:string):Promise<Result<{removed:string}>>{
 return attempt(async()=>{const done=await api.del<{removed:string}>(`/finance/imports/rules/${enc(id)}`);refresh();return done;});
}
