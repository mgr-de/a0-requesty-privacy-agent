import {updateNativePresetUI} from '/plugins/requesty_privacy_agent/webui/native-preset-ui.js';
export default async function(ctx){
    if(!String(ctx?.apiUrl||'').endsWith('/plugins/_model_config/model_config_get')&&!String(ctx?.apiUrl||'').endsWith('/plugins/requesty/model_status'))return;
    if(!ctx.response?.ok)return;
    try{const result=await ctx.response.clone().json();updateNativePresetUI(result.privacy_presets?.active);}catch{}
}
