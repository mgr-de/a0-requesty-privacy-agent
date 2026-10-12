import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
import {test} from 'node:test';
const source=(await readFile(new URL('../webui/privacy-agent-store.js',import.meta.url),'utf8')).replace(/^import .*;\r?\n/gm,'').replace('export const store=','globalThis.store=');
function setup(api){const context={createStore:(name,value)=>value,callJsonApi:api,toastFrontendError:()=>{},toastFrontendSuccess:()=>{}};vm.createContext(context);vm.runInContext(source,context);return context.store;}
test('late status after close cannot change the reopened setup',async()=>{
 let resolve;const store=setup(()=>new Promise(r=>resolve=r));const pending=store.action('status');store.cleanup();resolve({ok:true,active:true});await pending;assert.equal(store.status,null);assert.equal(store.busy,false);
});
test('activation and deactivation require separate explicit choices',async()=>{
 const calls=[];const store=setup(async p=>{calls.push(p);return {ok:true};});await store.activate();await store.deactivate();assert.equal(calls.length,0);
 store.confirmAll=true;store.configurationCurrent=()=>true;await store.activate();assert.equal(calls.length,1);
});
test('catalog never selects a model or invokes paid model validation',async()=>{
 const calls=[];const store=setup(async(path,input)=>{calls.push(input.action);return {ok:true,models:[{id:'eligible',allowed:true,supports_vision:true,supports_tool_calling:true}]};});await store.action('catalog');assert.deepEqual(calls,['catalog']);assert.equal(store.main,'');assert.equal(store.vision,'');
});
test('credentials are cleared and catalog invalidated after saving',async()=>{
 const store=setup(async()=>({ok:true,has_key:true}));store.key='SYNTHETIC';store.loaded=true;await store.action('key',{key:store.key});assert.equal(store.key,'');assert.equal(store.loaded,false);
});

test('short model list preserves explicit selections and has a provider switch',()=>{
 const store=setup(async()=>({ok:true}));store.models=['short','vendor/short','other/short'].map(id=>({id,allowed:true,supports_tool_calling:true,supports_vision:true}));
 store.main='vendor/short';assert.deepEqual(Array.from(store.choices(),m=>m.id),['short','vendor/short']);
 store.showProviders=true;assert.equal(store.choices().length,3);
});
