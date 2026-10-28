"use client";
import {useEffect} from 'react';
import {useRouter} from 'next/navigation';
export function SavedDataRefresh(){
 const router=useRouter();
 useEffect(()=>{const timer=setInterval(()=>{
  const reading=document.querySelector('[data-source-list] [aria-expanded="true"], details[data-source-coverage][open]');
  if(document.visibilityState==='visible'&&!reading&&!['INPUT','TEXTAREA','SELECT','BUTTON'].includes(document.activeElement?.tagName??''))router.refresh();
 },60000);return()=>clearInterval(timer);},[router]);
 return null;
}
