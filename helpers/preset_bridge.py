"""Owned reversible adapters for native A0 preset storage and APIs."""
from copy import deepcopy
from functools import wraps
from . import native_presets as n

_owned={}

def bind(target,name,factory):
    identity=(target,name)
    if identity in _owned:return
    original=getattr(target,name);proxy=factory(original)
    setattr(target,name,proxy);_owned[identity]=(original,proxy)

def healthy():return bool(_owned) and all(getattr(target,name) is proxy for (target,name),(_,proxy) in _owned.items())

def remove():
    for (target,name),(original,proxy) in list(_owned.items()):
        if getattr(target,name) is proxy:setattr(target,name,original)
        del _owned[(target,name)]

def check_selection(name,project='',profile=''):
    from plugins._model_config.helpers import model_config as mc
    from usr.plugins.requesty.helpers import scope
    candidate=mc.resolve_preset(name)
    if candidate is None:raise ValueError('The selected preset no longer exists.')
    raw=scope.read((project or '',profile),'config.json') if profile else None
    n.validate(candidate,profile_policy=raw)

def install():
    from . import manager as m
    from plugins._model_config.helpers import model_config as mc
    from helpers import plugins
    from plugins._model_config.api.model_presets import ModelPresets
    from plugins._model_config.api.model_override import ModelOverride
    from plugins._model_config.api.model_config_get import ModelConfigGet
    from plugins._model_config.api.model_search import ModelSearch
    from plugins._agent_editor.helpers import editor
    from agent import AgentContext
    from helpers.api import Response,ApiHandler
    import models

    def embedding_factory(original):
        @wraps(original)
        def checked(provider,name,model_config=None,**kwargs):
            if m.active():
                expected=n.embedding()
                if provider!=expected['provider'] or name!=expected['name'] or kwargs:
                    raise ValueError('Use the configured local embedding model without custom transport parameters.')
                if model_config is not None and (model_config.kwargs or model_config.api_base or model_config.api_key):
                    raise ValueError('Embedding model transport parameters must remain local.')
            return original(provider,name,model_config=model_config,**kwargs)
        return checked
    bind(models,'get_embedding_model',embedding_factory)

    def save_factory(original):
        @wraps(original)
        def checked(presets,*args,**kwargs):
            if n.enabled():
                previous={p['name']:p for p in mc.get_presets()};available=n.catalog()
                default=next((p for p in presets if p.get('name')=='Default'),None)
                if default is None:raise ValueError('Default cannot be removed.')
                for raw in presets:
                    if any(raw.get(role,{}).get('api_key') for role in ('chat','utility','vision','embedding')):raise ValueError('Store keys centrally or per profile, never in presets.')
                    if raw.get('chat',{}).get('provider')=='requesty_guarded':
                        entry=available.get(raw['chat'].get('name'),{})
                        raw['chat']['vision']=entry.get('supports_vision') is True
                    cleaned=mc.validate_presets([raw],require_default=False)[0]
                    # Retain unchanged, unconverted user presets without making
                    # them selectable. Every new/changed preset must validate.
                    if cleaned==previous.get(cleaned['name']):continue
                    effective=mc.config_to_preset(mc.build_config_from_preset(cleaned,mc.preset_to_config(default)),cleaned['name'])
                    n.validate(effective,available)
            return original(presets,*args,**kwargs)
        return checked
    bind(mc,'save_presets',save_factory)

    def reset_factory(original):
        @wraps(original)
        def checked(*args,**kwargs):
            if not n.enabled():return original(*args,**kwargs)
            available=n.catalog();presets=[n.build(name,*ids,available) for name,ids in n.TEMPLATES.items()]
            mc.save_presets(presets);return mc.get_presets()
        return checked
    bind(mc,'reset_presets',reset_factory)

    def providers_factory(original):
        @wraps(original)
        def checked(*args,**kwargs):
            return [{'value':'requesty_guarded','label':'Requesty (A0 Privacy)'}] if m.active() else original(*args,**kwargs)
        return checked
    bind(mc,'get_chat_providers',providers_factory)
    def embedding_providers_factory(original):
        @wraps(original)
        def checked(*args,**kwargs):
            return [{'value':'huggingface','label':'Local HuggingFace'}] if n.enabled() else original(*args,**kwargs)
        return checked
    bind(mc,'get_embedding_providers',embedding_providers_factory)

    def config_factory(original):
        @wraps(original)
        def checked(plugin_name,project_name,agent_profile,settings,*args,**kwargs):
            if n.enabled() and plugin_name=='_model_config' and settings.get('model_preset'):
                check_selection(settings['model_preset'],project_name,agent_profile)
            result=original(plugin_name,project_name,agent_profile,settings,*args,**kwargs)
            if n.enabled() and plugin_name=='_model_config' and not project_name and not agent_profile and settings.get('model_preset'):
                m.write('setup.json',{**m.read('setup.json'),'preset_name':settings['model_preset']})
            return result
        return checked
    bind(plugins,'save_plugin_config',config_factory)

    def editor_factory(original):
        @wraps(original)
        def checked(plan,value):
            if n.enabled() and isinstance(value,dict) and value.get('mode')=='preset':
                check_selection(value.get('name'),plan.project_name,plan.profile_id)
            return original(plan,value)
        return checked
    bind(editor,'_plan_model_preset',editor_factory)

    def api_factory(kind):
        def factory(original):
            @wraps(original)
            async def checked(self,input,request):
                if not n.enabled():return await original(self,input,request)
                try:
                    if kind=='presets' and input.get('action')=='select':
                        check_selection(input.get('name'),input.get('project_name',''),input.get('agent_profile',''))
                    if kind=='override' and input.get('action') in {'set','set_preset'}:
                        ctx=AgentContext.get(input.get('context_id'))
                        if ctx is None:return Response(status=404,response='Chat not found.')
                        if input['action']=='set_preset':check_selection(input.get('preset_name'),profile=ctx.agent0.config.profile)
                        else:
                            raw=input.get('override',{})
                            if raw.get('preset_name'):check_selection(raw['preset_name'],profile=ctx.agent0.config.profile)
                            else:
                                config=mc.build_config_from_preset(raw,mc.get_config(ctx.agent0))
                                n.validate(mc.config_to_preset(config,'Custom'))
                    if kind=='search' and input.get('model_type')=='embedding':
                        if input.get('provider')!='huggingface' or input.get('api_base') not in (None,''):raise ValueError('Embedding model search must remain local.')
                        name=n.embedding()['name'];query=str(input.get('query','')).lower()
                        return {'models':[name] if query in name.lower() else [],'provider':'huggingface','source':'required_local_embedding','error':''}
                    if kind=='search':
                        if input.get('provider')!='requesty_guarded':raise ValueError('Select Requesty while Privacy Agent is active.')
                        if input.get('api_base') not in (None,'','https://router.eu.requesty.ai/v1'):raise ValueError('Only the EU Requesty route is allowed.')
                        available=n.catalog()
                        from usr.plugins.requesty.helpers.policy import Policy
                        policy=Policy.parse(m.effective_policy());query=str(input.get('query','')).lower()
                        allowed=[entry['id'] for entry in available.values() if not policy.reasons(entry) and entry.get('supports_tool_calling') is True]
                        # Native field search shows short IDs by default. An
                        # explicit slash query also exposes provider-specific IDs.
                        if '/' not in query and any('/' not in name for name in allowed):allowed=[name for name in allowed if '/' not in name]
                        return {'models':sorted(name for name in allowed if query in name.lower()),'source':'requesty_privacy_catalog','provider':'requesty_guarded','error':''}
                    result=await original(self,input,request)
                    if kind=='presets' and isinstance(result,dict):
                        result['privacy_presets']={'active':True,'key_source':'Central Requesty key; an explicitly configured profile key takes precedence.'}
                    if kind=='config' and isinstance(result,dict):
                        result['chat_providers']=[{'value':'requesty_guarded','label':'Requesty (A0 Privacy)'}]
                        result['embedding_providers']=[{'value':'huggingface','label':'Local HuggingFace'}]
                        result['chat_provider_details']={'requesty_guarded':{'api_key_mode':'none'}}
                        result['privacy_presets']={'active':True,'key_source':'Central Requesty key; an explicitly configured profile key takes precedence.'}
                        result.setdefault('api_key_status',{})['requesty_guarded']=bool(m.read('credentials.json',{}).get('key'))
                        try:
                            n.validate(mc.config_to_preset(result.get('config',{}),'Current'))
                            result['model_configured']=result['api_key_status']['requesty_guarded']
                        except ValueError as error:
                            result['model_configured']=False;result['policy_error']=str(error)
                    return result
                except ValueError as error:return Response(status=400,response=str(error))
            return checked
        return factory
    for cls,kind in [(ModelPresets,'presets'),(ModelOverride,'override'),(ModelConfigGet,'config'),(ModelSearch,'search')]:bind(cls,'process',api_factory(kind))

    # A0's route loader creates distinct classes from the same source files.
    # Guard the authenticated common entry as well as ordinary imports.
    def handler_factory(original):
        @wraps(original)
        async def checked(self,request):
            kinds={'model_presets':'presets','model_override':'override','model_config_get':'config','model_search':'search'}
            kind=kinds.get(request.path.removeprefix('/api/plugins/_model_config/')) if request.path.startswith('/api/plugins/_model_config/') else None
            if kind is None or not n.enabled():
                result=await original(self,request)
                from .exception_lifecycle import profile_response
                profile_response(request,result)
                return result
            try:
                data=request.get_json(silent=True) if request.is_json else {}
                if not isinstance(data,dict):return Response(status=400,response='Model settings must be an object.')
                async def process(instance,input,request):return await instance.process(input,request)
                output=await api_factory(kind)(process)(self,data,request)
                if isinstance(output,Response):return output
                import json
                return Response(response=json.dumps(output),status=200,mimetype='application/json')
            except ValueError as error:return Response(status=400,response=str(error))
            except Exception:return Response(status=500,response='Privacy preset operation failed. Check installed components and the Requesty connection.')
        return checked
    bind(ApiHandler,'handle_request',handler_factory)
