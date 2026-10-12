import {updateNativePresetUI} from '/plugins/requesty_privacy_agent/webui/native-preset-ui.js';
export default async function(ctx){
    if(!['/plugins/_model_config/model_config_get','/plugins/_model_config/model_presets','/plugins/requesty/model_status','/plugins/requesty_privacy_agent/setup'].some(path=>String(ctx?.apiUrl||'').endsWith(path)))return;
    if(!ctx.response?.ok)return;
    try{const result=await ctx.response.clone().json();if(result.privacy_presets)updateNativePresetUI(result.privacy_presets.active);else if('native_presets' in result)updateNativePresetUI(result.native_presets&&(result.active??result.instance_protection));}catch{}
}
