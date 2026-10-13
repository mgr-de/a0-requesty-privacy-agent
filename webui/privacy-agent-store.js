import {createStore} from '/js/AlpineStore.js';
import {callJsonApi} from '/js/api.js';
import {toastFrontendError,toastFrontendSuccess} from '/components/notifications/notification-store.js';
export const store=createStore('privacyAgent',{
    status:null,busy:false,epoch:0,key:'',models:[],loaded:false,
    main:'',utility:'',vision:'',languages:['en','de'],confirmAll:false,confirmDisable:false,
    account:{eu_gateway:false,requesty_zdr:false,provider_zdr:false,approved_eu_models:false},
    preview:null,rows:[],preserveCurrent:true,reviewed:'',backupId:'',confirmUnmasked:false,
    async createDeveloperChat(){
        if(this.busy)return;
        this.busy=true;const epoch=this.epoch;
        try{
            const result=await callJsonApi('plugins/requesty_privacy_agent/developer_chat',{});
            if(epoch!==this.epoch)return;
            if(!result.ok)throw new Error(result.error||'Developer-Chat konnte nicht angelegt werden.');
            // Opening the new chat uses the native navigation contract.
            if(typeof globalThis.setContext==='function')globalThis.setContext(result.ctxid);
            toastFrontendSuccess('Neuer Developer-Chat: PII-Maskierung aus · Secret-Prüfung aktiv.','Privacy Agent');
        }catch(e){if(epoch===this.epoch)toastFrontendError(e.message,'Privacy Agent');}
        finally{if(epoch===this.epoch)this.busy=false;}
    },
    overrides(){return Object.fromEntries(this.rows.map(r=>[r.name,{main:r.main,utility:r.utility,vision:r.vision||null}]));},
    migrationCurrent(){return this.reviewed===JSON.stringify({overrides:this.overrides(),preserve:this.preserveCurrent,languages:this.languages});},
    async loadMigration(){await this.action('catalog');await this.action('migration_preview',{preserve_current:this.preserveCurrent});},
    async refreshMigration(){await this.action('migration_preview',{overrides:this.overrides(),preserve_current:this.preserveCurrent});},
    async applyMigration(){if(this.preview&&this.migrationCurrent())await this.action('migration_apply',{fingerprint:this.preview.fingerprint,overrides:this.overrides(),preserve_current:this.preserveCurrent,languages:[...this.languages]});},
    cleanup(){this.preview=null;this.rows=[];this.reviewed='';this.epoch++;this.key='';this.busy=false;this.models=[];this.loaded=false;this.confirmAll=false;this.confirmDisable=false;this.confirmUnmasked=false;},
    async open(){this.cleanup();await this.action('status');},
    showProviders:false,
    choices(vision=false){
        const eligible=this.models.filter(m=>m.allowed&&(!vision||m.supports_vision===true)&&m.supports_tool_calling===true);
        const hasShort=eligible.some(m=>!m.id.includes('/'));
        const selected=[this.main,this.utility,this.vision,...this.rows.flatMap(r=>[r.main,r.utility,r.vision])];
        return eligible.filter(m=>this.showProviders||!hasShort||!m.id.includes('/')||selected.includes(m.id));
    },
    configurationCurrent(){
        if(this.status?.native_presets)return true;
        const models=this.status?.models;
        const languages=this.status?.local?.pii_filter?.languages;
        return !!models?.chat && this.main===models.chat.name && this.utility===models.utility?.name && this.vision===models.vision?.name
            && JSON.stringify([...new Set([...this.languages,'en'])].sort())===JSON.stringify([...(languages||[])].sort());
    },
    async action(action,extra={}){
        if(this.busy)return;this.busy=true;const epoch=this.epoch;
        try{
            const result=await callJsonApi('plugins/requesty_privacy_agent/setup',{action,...extra});
            if(epoch!==this.epoch)return;
            if(!result.ok)throw new Error(result.error||'Einrichtung fehlgeschlagen.');
            if(action==='catalog'){this.models=result.models;this.loaded=true;}
            else if(action==='migration_preview'){
                this.preview=result.preview;
                this.rows=[...(result.preview.presets||[]).filter(p=>p.chat?.provider==='requesty_guarded'&&!p.name.startsWith('Requesty bisherige Einrichtung')).map(p=>({name:p.name,main:p.chat?.name||'',utility:p.utility?.name||'',vision:p.vision?.name||''})),...(result.preview.blocked||[]).map(p=>({...p}))];
                this.reviewed=JSON.stringify({overrides:this.overrides(),preserve:this.preserveCurrent,languages:this.languages});
            }
            else{
                this.status=result;
                if(action==='migration_apply'){this.backupId=result.receipt?.backup_id||'';this.preview=null;this.rows=[];}
                if(['status','configure','activate','deactivate'].includes(action)){
                    this.main=result.models?.chat?.name||this.main;
                    this.utility=result.models?.utility?.name||this.utility;
                    this.vision=result.models?.vision?.name||this.vision;
                    this.languages=result.local?.pii_filter?.languages||this.languages;
                }
                this.account={eu_gateway:false,requesty_zdr:false,provider_zdr:false,approved_eu_models:false,...result.account?.settings};
            }
            if(action==='key'){this.key='';this.models=[];this.loaded=false;this.preview=null;this.rows=[];this.reviewed='';}
            if(action!=='status')toastFrontendSuccess(action==='activate'?'Mindestregeln gelten jetzt für alle Profile.':'Einstellungen aktualisiert.','Privacy Agent');
        }catch(e){if(epoch===this.epoch)toastFrontendError(e.message,'Privacy Agent');}
        finally{if(epoch===this.epoch)this.busy=false;}
    },
    async configure(){if(this.main&&this.utility&&this.vision)await this.action('configure',{configuration:{main:this.main,utility:this.utility,vision:this.vision,languages:[...this.languages]}});},
    async activate(){if(this.confirmAll&&this.configurationCurrent())await this.action('activate',{confirm_all_profiles:true});},
    async deactivate(){if(this.confirmDisable)await this.action('deactivate',{confirmation:'DISABLE_INSTANCE_PROTECTION'});}
});
