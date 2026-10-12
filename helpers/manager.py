"""Instance policy and setup. Filtering and routing stay in the companion plugins."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading

LOCK=threading.RLock()
SHARED=('', 'privacy_agent_shared')
MINIMUM={'region':'eu','strict_region':True,'no_retention':True,'no_training':True,'require_requesty_zdr':False}
MIN_VERSIONS={'requesty':(0,5,0),'local_privacy_guard':(1,5,0)}

def directory():
    from helpers import files
    user=Path(files.get_abs_path(files.USER_DIR)).resolve()
    target=user/'privacy-agent'
    if target.is_symlink() or not target.resolve().is_relative_to(user):
        raise ValueError('Privacy Agent storage is unsafe.')
    return target

def read(name,default=None):
    if name not in {'active.json','config.json','setup.json','credentials.json','local.json','account.json'}:
        raise ValueError('Unknown Privacy Agent asset.')
    path=directory()/name
    if not path.exists():return default
    if path.is_symlink():raise ValueError('Privacy Agent storage is unsafe.')
    try:value=json.loads(path.read_text(encoding='utf-8'))
    except Exception:raise ValueError('Privacy Agent configuration cannot be read. Restore its files.') from None
    if not isinstance(value,dict):raise ValueError('Privacy Agent configuration is invalid.')
    return value

def write(name,value):
    read(name) # validates the destination, including an existing symlink
    folder=directory();folder.mkdir(mode=0o700,parents=True,exist_ok=True);os.chmod(folder,0o700)
    fd,temporary=tempfile.mkstemp(prefix='.privacy-',dir=folder)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            json.dump(value,stream,ensure_ascii=False);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,folder/name);os.chmod(folder/name,0o600)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)

def active():
    return read('active.json',{}).get('active') is True

def components():
    from helpers import files
    import yaml
    root=Path(files.get_abs_path(files.USER_DIR))/'plugins'
    result={}
    for name,minimum in MIN_VERSIONS.items():
        path=root/name/'plugin.yaml'
        try:
            meta=yaml.safe_load(path.read_text(encoding='utf-8'))
            version=tuple(int(part) for part in str(meta['version']).split('.'))
            compatible=meta.get('name')==name and version>=minimum and version[0]==minimum[0]
            manifest=root.parent/'privacy-guard-adapters'/(name+'.json')
            owned=json.loads(manifest.read_text())
            intact=bool(owned) and all(
                not (root.parent/'extensions/python'/relative).is_symlink()
                and (root.parent/'extensions/python'/relative).resolve().is_relative_to((root.parent/'extensions/python').resolve())
                and hashlib.sha256((root.parent/'extensions/python'/relative).read_text().encode()).hexdigest()==digest
                for relative,digest in owned.items())
            compatible=compatible and intact
        except Exception:version=();compatible=False
        result[name]={'installed':path.is_file(),'compatible':compatible,'version':'.'.join(map(str,version))}
    return result

def require_components():
    if not all(item['compatible'] for item in components().values()):
        raise ValueError('Privacy Agent requires compatible Requesty and Local Privacy Guard plugins. Install or restore its components.')
    from usr.plugins.requesty.helpers import runtime_guard
    from usr.plugins.local_privacy_guard.helpers import model_guard
    if getattr(runtime_guard,'INSTANCE_API_VERSION',None)!=1 or getattr(model_guard,'INSTANCE_API_VERSION',None)!=1:
        raise ValueError('Restart Agent Zero after updating the privacy components before activating Privacy Agent.')

def effective_policy(profile=None):
    from usr.plugins.requesty.helpers.policy import Policy
    raw=deepcopy(profile or read('config.json',MINIMUM))
    Policy.parse(raw) # retain strict validation; do not hide invalid settings
    raw.update({key:value for key,value in MINIMUM.items() if key!='require_requesty_zdr'})
    # A profile may require verifiable gateway ZDR; manual attestation never satisfies it.
    raw['require_requesty_zdr']=bool(raw.get('require_requesty_zdr') or read('config.json',{}).get('require_requesty_zdr'))
    return raw

def requesty_owner(agent):
    from usr.plugins.requesty.helpers import scope
    candidate=scope.from_agent(agent)
    setup=scope.read(candidate,'setup.json')
    # A deliberate active profile model setup remains a selection, even if its
    # old profile toggle is off. Runtime validation enforces the instance floor.
    return candidate if setup and setup.get('active') else SHARED

def local_config(agent):
    from helpers import plugins,projects
    from usr.plugins.local_privacy_guard.helpers.agent_scope import selected_path
    floor=deepcopy(read('local.json') or plugins.get_default_plugin_config('local_privacy_guard'))
    path=selected_path(projects.get_context_project_name(agent.context) or '',agent.config.profile)
    profile=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    if not isinstance(profile,dict):raise ValueError('Profile text-filter settings are invalid.')
    result={**floor,**profile,'enabled':True}
    section={**floor.get('pii_filter',{}),**profile.get('pii_filter',{})}
    section.update(enabled=True,use_regex=True,use_ner=True,store_mapping=True)
    # Profiles may add detection, never replace built-ins or narrow NER types.
    section['ner_entity_types']=[]
    from usr.plugins.local_privacy_guard.helpers.pii_detector import UNIVERSAL_PATTERNS,LANGUAGE_PATTERNS
    reserved=set(UNIVERSAL_PATTERNS)|{key for patterns in LANGUAGE_PATTERNS.values() for key in patterns}
    patterns=[*floor.get('pii_filter',{}).get('custom_patterns',[]),*profile.get('pii_filter',{}).get('custom_patterns',[])]
    if any(not isinstance(pattern,dict) or pattern.get('name','CUSTOM') in reserved for pattern in patterns):
        raise ValueError('Custom patterns may add detection but must not replace built-in privacy patterns. Choose a new pattern name.')
    section['custom_patterns']=patterns
    section['action']='block' if section.get('action')=='block' else 'redact'
    requested=section.get('languages',[])
    if not isinstance(requested,list) or any(language not in {'en','de','fr','es','it','nl','pl','pt'} for language in requested):
        raise ValueError('Choose supported local filter languages.')
    section['languages']=sorted(set(floor.get('pii_filter',{}).get('languages',['de']))|set(requested)|{'en'})
    result['pii_filter']=section
    result['local_embedding']=deepcopy(floor['local_embedding'])
    return result

def mapping_identity(agent):
    install_legacy_bridge()
    from helpers import projects
    # Persisted with the native context; never follow later root-profile changes.
    identity=agent.context.get_data('privacy_agent_mapping_identity')
    project=projects.get_context_project_name(agent.context) or ''
    if identity is None:
        identity=[project,agent.config.profile]
        agent.context.set_data('privacy_agent_mapping_identity',identity)
    if not isinstance(identity,list) or len(identity)!=2 or not all(isinstance(v,str) for v in identity):
        raise ValueError('The chat privacy identity is invalid.')
    return tuple(identity)

def filter_check(config):
    from usr.plugins.local_privacy_guard.helpers.pii_detector import PIIFilter
    from usr.plugins.local_privacy_guard.helpers.agent_scope import embedding
    embedding(config)
    scanner=PIIFilter(config['pii_filter'])
    missing=sorted(set(scanner.ner_languages)-set(scanner.get_loaded_languages()))
    if missing:raise ValueError('Name detection unavailable: '+', '.join(missing)+'. Install the selected spaCy models in Agent Zero.')
    # Required local embeddings must load without making an external model call.
    from sentence_transformers import SentenceTransformer
    model=config['local_embedding']['model']
    try:SentenceTransformer(model,local_files_only=True)
    except Exception:
        raise ValueError('Local embeddings are unavailable. Prepare the selected sentence-transformers model in Agent Zero before activation; no local chat LLM is required.') from None
    return {'names':'available','embeddings':'available_locally','languages':scanner.get_loaded_languages()}

def public_status():
    setup=read('setup.json',{})
    account=read('account.json',{})
    public_models={slot:{field:conf.get(field) for field in ('provider','name','api_base','ctx_length','vision','override_main') if field in conf}
                   for slot,conf in setup.get('models',{}).items() if slot in {'chat','utility','vision'} and isinstance(conf,dict)}
    return {'active':active(),'components':components(),'has_key':bool(read('credentials.json',{}).get('key')),
        'models':public_models,'local':read('local.json',{}),'account':account,
        'account_verification':account.get('verification','unverified'),
        'policy':read('config.json',MINIMUM),'images':'External images are not protected by text masking.',
        'tools':'Websites, uploads and tool transfers are not comprehensively monitored.'}

def save_key(value):
    if active():raise ValueError('Deactivate centrally before changing the common key.')
    if not isinstance(value,str) or not value.strip() or len(value)>4096 or any(c.isspace() for c in value.strip()):
        raise ValueError('Enter a valid Requesty API key.')
    write('credentials.json',{'key':value.strip()})
    write('account.json',{}) # A different key may belong to another organization.

def model_catalog():
    require_components()
    from usr.plugins.requesty.helpers.catalog import fetch
    from usr.plugins.requesty.helpers.policy import Policy
    key=read('credentials.json',{}).get('key')
    if not key:raise ValueError('Save the common Requesty API key first.')
    policy=Policy.parse(effective_policy())
    fields=('id','geolocation','supports_vision','supports_tool_calling','context_window','data_retention','data_used_for_training')
    return [{**{field:entry.get(field) for field in fields},'allowed':not policy.reasons(entry),
             'reasons':policy.reasons(entry)} for entry in fetch(policy.endpoint,key,refresh=True).values()]

def prepare_local(languages):
    require_components()
    if active():raise ValueError('Deactivate centrally before preparing a changed language selection.')
    if not isinstance(languages,list) or any(v not in {'en','de','fr','es','it','nl','pl','pt'} for v in languages):
        raise ValueError('Select supported filter languages.')
    from usr.plugins.local_privacy_guard.hooks import SPACY_MODELS,_install_spacy_model
    for language in sorted(set(languages)|{'en'}):
        result=_install_spacy_model(SPACY_MODELS[language])
        if result.get('status')=='failed':raise ValueError('Local name detection could not be prepared for '+language+'. Check access to the official spaCy model downloads.')
    from sentence_transformers import SentenceTransformer
    # This is a weights download, never a chat model service or remote code.
    SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',trust_remote_code=False)
    import importlib
    importlib.invalidate_caches()

def configure(value):
    require_components()
    from helpers import plugins
    from usr.plugins.requesty.helpers.policy import Policy
    from usr.plugins.requesty.helpers.catalog import fetch
    if not isinstance(value,dict) or set(value)!={'main','utility','vision','languages'}:
        raise ValueError('Choose Main, Utility, Vision and filter languages.')
    languages=value['languages']
    if not isinstance(languages,list) or not languages or any(v not in {'de','en','fr','es','it','nl','pl','pt'} for v in languages):
        raise ValueError('Select supported filter languages.')
    key=read('credentials.json',{}).get('key')
    if not key:raise ValueError('Save the common Requesty API key first.')
    policy=Policy.parse(effective_policy())
    catalog=fetch(policy.endpoint,key,refresh=True)
    models={'name':'Privacy Agent'}
    for slot,input_name in [('chat','main'),('utility','utility'),('vision','vision')]:
        identifier=value[input_name]
        if not isinstance(identifier,str):raise ValueError('Choose concrete catalog models.')
        entry=catalog.get(identifier);policy.check(entry)
        if slot=='vision' and entry.get('supports_vision') is not True:raise ValueError('Select a verified Vision model.')
        if entry.get('supports_tool_calling') is not True:raise ValueError('Select models with verified tool support.')
        length=entry.get('context_window')
        if type(length) is not int or length<=0:raise ValueError('Model context window is unverified.')
        models[slot]={'provider':'requesty_guarded','name':identifier,'api_base':policy.endpoint,
                      'kwargs':{},'ctx_length':length,'vision':entry.get('supports_vision') is True}
        if slot=='vision':models[slot]['override_main']=True
    local=deepcopy(plugins.get_default_plugin_config('local_privacy_guard'))
    local.update(enabled=True)
    local['pii_filter'].update(enabled=True,use_regex=True,use_ner=True,action='redact',languages=sorted(set(languages)|{'en'}))
    local['local_embedding'].update(enabled=True,auto_configure=True)
    check=filter_check(local)
    # Validate the complete candidate before any file is committed. Activation
    # remains a separate action; configure while active is deliberately refused.
    if active():raise ValueError('Deactivate centrally before replacing the common setup.')
    write('config.json',effective_policy())
    write('local.json',local)
    write('setup.json',{'active':True,'models':models})
    return check

def activate():
    require_components()
    setup=read('setup.json',{})
    local=read('local.json',{})
    if not setup.get('active') or not local:raise ValueError('Complete the common setup first.')
    filter_check(local)
    from usr.plugins.requesty.helpers.policy import Policy
    from usr.plugins.requesty.helpers.catalog import fetch
    key=read('credentials.json',{}).get('key')
    policy=Policy.parse(effective_policy())
    catalog=fetch(policy.endpoint,key,refresh=True)
    for slot in ('chat','utility','vision'):
        entry=catalog.get(setup.get('models',{}).get(slot,{}).get('name'));policy.check(entry)
        if entry.get('supports_tool_calling') is not True:raise ValueError('Tool support is no longer confirmed for a selected model.')
        if slot=='vision' and entry.get('supports_vision') is not True:raise ValueError('Vision support is no longer confirmed.')
    from usr.plugins.requesty_privacy_agent.helpers.adapters import install
    install()
    install_legacy_bridge()
    # Pin identities before the first profile transition. Native persistence
    # serializes context data, so restart retains ownership.
    from agent import AgentContext
    from helpers.persist_chat import save_tmp_chat
    if any(context.is_running() for context in AgentContext.all()):
        raise ValueError('Wait until running chats finish before activating the common rules.')
    for context in list(AgentContext.all()):
        if context.agent0:
            mapping_identity(context.agent0);save_tmp_chat(context)
    write('active.json',{'active':True,'activated_at':datetime.now(timezone.utc).isoformat(),'api_version':1})

def deactivate(confirmation):
    if confirmation!='DISABLE_INSTANCE_PROTECTION':raise ValueError('Confirm that all profiles lose the instance minimum rules.')
    from agent import AgentContext
    if any(context.is_running() for context in AgentContext.all()):
        raise ValueError('Wait until running chats finish before changing the instance rules.')
    write('active.json',{'active':False})
    remove_legacy_bridge()

def apply_model_config(data,agent):
    if not active() or agent is None:return
    require_components()
    args=data.get('args',())
    name=args[0] if args else data.get('kwargs',{}).get('plugin_name')
    if name!='_model_config' or not isinstance(data.get('result'),dict):return
    from usr.plugins.requesty.helpers import scope
    owner=requesty_owner(agent)
    models=scope.read(owner,'setup.json',{}).get('models',{})
    result=deepcopy(data['result'])
    for source,target in [('chat','chat_model'),('utility','utility_model')]:
        result[target]=deepcopy(models[source])
    # A profile's explicit sidecar remains a selection. Shared default is only
    # supplied where no profile sidecar exists; runtime checks reject conflicts.
    if owner==SHARED or not result.get('vision_model'):
        result['vision_model']=deepcopy(read('setup.json')['models']['vision'])
    data['result']=result

def enforce_call(data,method):
    if not active():return
    require_components()
    from usr.plugins.requesty.helpers.runtime_guard import guard_function,is_local_route
    from usr.plugins.requesty.helpers.call_context import tool_agent
    from usr.plugins.local_privacy_guard.helpers.model_guard import tool_agent as filter_owner,filtered_call
    wrapper=data['args'][0]
    proof=filtered_call.get()
    filtered_owner=proof[1] if proof and proof[0] is wrapper else None
    owner=tool_agent.get() or filter_owner.get() or filtered_owner
    bound=getattr(wrapper,'_requesty_policy_bound',False)
    if owner is None:
        # No chat identity means no safe mapping/attribution. Never send such an
        # external legacy/background call merely because its URL looks allowed.
        if not is_local_route(wrapper,{**wrapper.kwargs,**data.get('kwargs',{})}):
            raise ValueError('This external model call has no protected chat owner. Use the native protected model getter.')
        from usr.plugins.requesty.helpers.runtime_guard import local_kwargs
        local_kwargs(wrapper,{})
        return
    scope=getattr(wrapper,'_requesty_scope',None)
    from usr.plugins.requesty.helpers.call_context import owner as expected_owner
    expected=expected_owner(owner)
    test_scope=owner.context.get_data('_privacy_model_test_scope')
    if getattr(wrapper,'_requesty_test',False) and test_scope:
        from usr.plugins.requesty.helpers import scope as requesty_scope
        if tuple(test_scope)==requesty_scope.from_agent(owner):expected=tuple(test_scope)
    if scope is not None and scope!=expected:
        raise ValueError('This cached model belongs to another profile setup. Rebuild it using the current protected model getter.')
    requirements=getattr(wrapper,'_requesty_policy_scope',None)
    if requirements is not None:
        from usr.plugins.requesty.helpers.call_context import root_agent
        from usr.plugins.requesty.helpers.scope import from_agent
        if requirements!=from_agent(root_agent(owner)):
            raise ValueError('The cached model belongs to another profile policy. Rebuild it using the current protected model getter.')
    if not bound:guard_function(data)

async def enforce_output(data):
    if active():require_components()

_LEGACY_BRIDGES={}

def install_legacy_bridge():
    """Guard existing bare LangChain objects, which lack extensible call points.

    This opt-in instance bridge only checks/filter-passage ownership. The
    companions continue to perform routing, masking and output restoration.
    """
    from models import LiteLLMChatWrapper
    from functools import wraps
    for name in ('_call','_stream','_astream'):
        original=getattr(LiteLLMChatWrapper,name)
        if name in _LEGACY_BRIDGES:continue
        def factory(method,previous):
            @wraps(previous)
            def checked(wrapper,*args,**kwargs):
                if active():
                    require_components()
                    from usr.plugins.local_privacy_guard.helpers.model_guard import filtered_call,is_local
                    proof=filtered_call.get()
                    if not is_local(wrapper,kwargs):
                        if not proof or proof[0] is not wrapper:
                            raise ValueError('This old external model wrapper has not passed the chat text filter. Rebuild it using the protected model getter.')
                        from usr.plugins.requesty.helpers.runtime_guard import guarded_kwargs,is_requesty
                        if not is_requesty(wrapper):raise ValueError('The old model wrapper bypasses Requesty. Rebuild it using the protected model getter.')
                        from usr.plugins.requesty.helpers.call_context import owner
                        if getattr(wrapper,'_requesty_scope',None)!=owner(proof[1]):
                            raise ValueError('The old model wrapper belongs to another profile setup. Rebuild it.')
                        from usr.plugins.requesty.helpers.call_context import root_agent
                        from usr.plugins.requesty.helpers.scope import from_agent
                        requirements=getattr(wrapper,'_requesty_policy_scope',None)
                        if requirements is not None and requirements!=from_agent(root_agent(proof[1])):
                            raise ValueError('The old model wrapper belongs to another profile policy. Rebuild it.')
                        checked_options=guarded_kwargs(wrapper,{k:v for k,v in kwargs.items() if k not in {'run_manager'}})
                        kwargs={**checked_options,**{k:v for k,v in kwargs.items() if k=='run_manager'}}
                return previous(wrapper,*args,**kwargs)
            return checked
        proxy=factory(name,original)
        setattr(LiteLLMChatWrapper,name,proxy)
        _LEGACY_BRIDGES[name]=(original,proxy)

def remove_legacy_bridge():
    from models import LiteLLMChatWrapper
    for name,(original,proxy) in list(_LEGACY_BRIDGES.items()):
        if getattr(LiteLLMChatWrapper,name) is proxy:setattr(LiteLLMChatWrapper,name,original)
        del _LEGACY_BRIDGES[name]
