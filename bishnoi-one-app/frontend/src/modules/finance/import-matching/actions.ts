"use server";
import {refresh} from 'next/cache';
import {api,enc} from '@/src/modules/finance/platform/lib/api';
import {attempt,type Result} from '@/src/modules/finance/platform/lib/result';
import type {Match,Proposal} from './types';

// Import matching: saved by someone who may confirm that section, it's final; otherwise a proposal
// (tax labels: BIR and Compliance). The API checks who may do each (app/routers/imports.py).

export async function proposeMatch(id:string,body:Proposal):Promise<Result<Match>>{
 return attempt(async()=>{const saved=await api.put<Match>(`/finance/imports/matching/${enc(id)}`,body);refresh();return saved;});
}

export async function confirmMatch(id:string):Promise<Result<Match>>{
 return attempt(async()=>{const saved=await api.post<Match>(`/finance/imports/matching/${enc(id)}/confirm`);refresh();return saved;});
}
