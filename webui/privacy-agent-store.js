import {createStore} from '/js/AlpineStore.js';
import {callJsonApi} from '/js/api.js';
import {toastFrontendError,toastFrontendSuccess} from '/components/notifications/notification-store.js';
export const store=createStore('privacyAgent',{
    status:null,busy:false,epoch:0,key:'',models:[],loaded:false,
    main:'',utility:'',vision:'',languages:['en','de'],confirmAll:false,confirmDisable:false,
    account:{eu_gateway:false,requesty_zdr:false,provider_zdr:false,approved_eu_models:false},
    cleanup(){this.epoch++;this.key='';this.busy=false;this.models=[];this.loaded=false;this.confirmAll=false;this.confirmDisable=false;},
    async open(){this.cleanup();await this.action('status');},
    showProviders:false,
    choices(vision=false){
        const eligible=this.models.filter(m=>m.allowed&&(!vision||m.supports_vision===true)&&m.supports_tool_calling===true);
        const hasShort=eligible.some(m=>!m.id.includes('/'));
        return eligible.filter(m=>this.showProviders||!hasShort||!m.id.includes('/')||[this.main,this.utility,this.vision].includes(m.id));
    },
    configurationCurrent(){
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
            else{
                this.status=result;
                if(['status','configure','activate','deactivate'].includes(action)){
                    this.main=result.models?.chat?.name||this.main;
                    this.utility=result.models?.utility?.name||this.utility;
                    this.vision=result.models?.vision?.name||this.vision;
                    this.languages=result.local?.pii_filter?.languages||this.languages;
                }
                this.account={eu_gateway:false,requesty_zdr:false,provider_zdr:false,approved_eu_models:false,...result.account?.settings};
            }
            if(action==='key'){this.key='';this.models=[];this.loaded=false;}
            if(action!=='status')toastFrontendSuccess(action==='activate'?'Mindestregeln gelten jetzt für alle Profile.':'Einstellungen aktualisiert.','Privacy Agent');
        }catch(e){if(epoch===this.epoch)toastFrontendError(e.message,'Privacy Agent');}
        finally{if(epoch===this.epoch)this.busy=false;}
    },
    async configure(){if(this.main&&this.utility&&this.vision)await this.action('configure',{configuration:{main:this.main,utility:this.utility,vision:this.vision,languages:[...this.languages]}});},
    async activate(){if(this.confirmAll&&this.configurationCurrent())await this.action('activate',{confirm_all_profiles:true});},
    async deactivate(){if(this.confirmDisable)await this.action('deactivate',{confirmation:'DISABLE_INSTANCE_PROTECTION'});}
});
