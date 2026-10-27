"use server";
import {refresh} from 'next/cache';
import {api,enc} from '../platform/lib/api';
import {attempt} from '../platform/lib/result';
import type {OrderInput,SalesOrder} from './types';
export async function saveOrder(id:string|null,body:OrderInput){return attempt(async()=>{const value=id?await api.put<SalesOrder>(`/finance/sales-orders/${enc(id)}`,body):await api.post<SalesOrder>('/finance/sales-orders',body);refresh();return value;});}
export async function orderStep(id:string,step:'submit'|'approve'|'return'|'cancel',version:number,reason?:string){return attempt(async()=>{const value=await api.post<SalesOrder>(`/finance/sales-orders/${enc(id)}/${step}`,{version,reason:reason||null});refresh();return value;});}
