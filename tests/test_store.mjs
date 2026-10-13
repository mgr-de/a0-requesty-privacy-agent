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

test('migration needs current explicit model and language review before applying',async()=>{
 const calls=[];const store=setup(async(path,input)=>{calls.push(input.action);return {ok:true,preview:{presets:[{name:'Default',chat:{provider:'requesty_guarded',name:'main'},utility:{name:'utility'},vision:{}}],blocked:[],fingerprint:'snapshot'}};});
 await store.action('migration_preview');assert.equal(store.migrationCurrent(),true);
 store.rows[0].main='changed';assert.equal(store.migrationCurrent(),false);await store.applyMigration();assert.deepEqual(calls,['migration_preview']);
 store.reviewed=JSON.stringify({overrides:store.overrides(),preserve:store.preserveCurrent,languages:store.languages});store.languages=['en'];assert.equal(store.migrationCurrent(),false);
});
test('native preset mode remains editable without switching off protection',()=>{
 const store=setup(async()=>({ok:true}));store.status={native_presets:true,active:true};assert.equal(store.configurationCurrent(),true);
});
test('migration submit disabled binding returns a boolean for zero blockers',async()=>{
 const html=await readFile(new URL('../webui/config.html',import.meta.url),'utf8');
 assert.match(html,/preview\.blocked\.length>0/);
 assert.doesNotMatch(html,/x-model="row\[role\]"/);
});

test('closing resets the full-context Developer confirmation',()=>{
 const store=setup(async()=>({ok:true}));store.confirmUnmasked=true;store.cleanup();assert.equal(store.confirmUnmasked,false);
});

test('late Developer chat response cannot navigate after settings close',async()=>{
 let resolve;const store=setup(()=>new Promise(r=>resolve=r));const pending=store.createDeveloperChat();store.cleanup();resolve({ok:true,ctxid:'synthetic'});await pending;assert.equal(store.busy,false);
});

test('optional login is recommended without disabling Developer controls',async()=>{
 const html=await readFile(new URL('../webui/config.html',import.meta.url),'utf8');
 assert.match(html,/Anmeldung dringend empfohlen/);
 assert.match(html,/Ohne Anmeldung kann jeder mit Zugriff/);
 const disabled=[...html.matchAll(/:disabled="([^"]*)"/g)].map(match=>match[1]);
 assert.ok(disabled.every(expression=>!expression.includes('login_configured')));
 assert.match(html,/confirmUnmasked/);
});


test('inactive owned cleanup requires explicit consent and never toggles policy',async()=>{
 const actions=[];const store=setup(async(path,input)=>{actions.push(input);return {ok:true};});
 await store.cleanupAdapters();assert.equal(actions.length,0);
 store.confirmCleanup=true;await store.cleanupAdapters();
 assert.equal(actions[0].action,'cleanup_adapters');assert.equal(actions[0].confirmation,'REMOVE_INACTIVE_OWNED_ADAPTERS');
 assert.equal(store.confirmCleanup,false);
 const html=await readFile(new URL('../webui/config.html',import.meta.url),'utf8');
 assert.match(html,/activation_state==='broken'/);assert.match(html,/manager_adapters/);
});


test('Gateway-only requires separate consent and labels text checks disabled',async()=>{
 const calls=[];const store=setup(async(path,input)=>{calls.push(input);return {ok:true,active:true,local_guard_enabled:false};});
 await store.gatewayOnly();assert.equal(calls.length,0);
 store.confirmGatewayOnly=true;await store.gatewayOnly();
 assert.equal(calls[0].action,'gateway_only');assert.equal(calls[0].confirmation,'KEEP_GATEWAY_DISABLE_LOCAL_GUARD');
 assert.equal(store.status.active,true);assert.equal(store.status.local_guard_enabled,false);assert.equal(store.confirmGatewayOnly,false);
 store.confirmGatewayOnly=true;store.cleanup();assert.equal(store.confirmGatewayOnly,false);
 const html=await readFile(new URL('../webui/config.html',import.meta.url),'utf8');
 assert.match(html,/Gateway-Regeln aktiv · Local Guard aus/);assert.match(html,/confirmGatewayOnly/);
});
