"""Native presets are the model source; policy/key ownership remains separate."""
from copy import deepcopy
import hashlib
import json
import re
from uuid import uuid4

TEMPLATES = {
    'Default': ('gpt-6.1-sol@eu','gpt-6-luna@eu',None),
    'Efficiency': ('glm-5.3@eu','deepseek-v4.1-flash@eu','deepseek-v4.1-flash@eu'),
    'Power': ('claude-opus-5-5@eu','gpt-6-luna@eu',None),
}

def enabled():
    from . import manager as m
    return m.active() and m.read('setup.json',{}).get('native_presets') is True

def catalog():
    from . import manager as m
    m.require_components()
    from usr.plugins.requesty.helpers.catalog import fetch
    return fetch('https://router.eu.requesty.ai/v1',m.read('credentials.json',{}).get('key'))

def embedding():
    from . import manager as m
    local=m.read('local.json',{}).get('local_embedding',{})
    return {'provider':'huggingface','name':local.get('model','sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'),'kwargs':{}}

def slot(identifier, available):
    from . import manager as m
    from usr.plugins.requesty.helpers.policy import Policy
    entry=available.get(identifier);Policy.parse(m.effective_policy()).check(entry)
    if entry.get('supports_tool_calling') is not True:raise ValueError('Model tool support is not confirmed.')
    length=entry.get('context_window')
    if type(length) is not int or length<=0:raise ValueError('Model context window is not confirmed.')
    return {'provider':'requesty_guarded','name':identifier,'api_base':'https://router.eu.requesty.ai/v1',
            'ctx_length':length,'vision':entry.get('supports_vision') is True,'kwargs':{}}

def build(name, main, utility, vision, available):
    result={'name':name,'chat':slot(main,available),'utility':slot(utility,available),'embedding':embedding()}
    if vision:
        result['vision']=slot(vision,available)
        if not result['vision']['vision']:raise ValueError('Select a catalog-confirmed Vision model.')
        result['vision']['override_main']=True
    elif not result['chat']['vision']:raise ValueError('This Main model needs a separate Vision model.')
    else:result['vision']={}
    return result

def validate(preset, available=None, profile_policy=None):
    from . import manager as m
    from usr.plugins.requesty.helpers.policy import Policy
    from usr.plugins.requesty.helpers.runtime_guard import validate_model_parameters
    import models
    available=available if available is not None else catalog()
    policy=Policy.parse(m.effective_policy(profile_policy))
    for role in ('chat','utility','vision'):
        conf=preset.get(role,{})
        if role=='vision' and not conf.get('name'):
            if not preset.get('chat',{}).get('vision'):raise ValueError('A separate Vision model is required.')
            continue
        if conf.get('provider')!='requesty_guarded':raise ValueError(role+': Provider must be Requesty while Privacy Agent is active.')
        if conf.get('api_key'):raise ValueError('Preset keys are not allowed. Use the central or profile Requesty key.')
        entry=available.get(conf.get('name'));policy.check(entry)
        if entry.get('supports_tool_calling') is not True:raise ValueError(role+': Tool support is unverified.')
        if role=='vision' and entry.get('supports_vision') is not True:raise ValueError('Vision support is unverified.')
        if role=='chat' and bool(conf.get('vision'))!=(entry.get('supports_vision') is True):raise ValueError('Set Supports Vision to the catalog-confirmed capability.')
        native_fields={'provider','name','api_base','api_key','ctx_length','ctx_input','ctx_history','vision','rl_requests','rl_input','rl_output','kwargs'}
        if role=='chat':native_fields.add('max_embeds')
        if role=='vision':native_fields.update({'max_embeds','timeout','max_tokens','override_main'})
        unexpected=set(conf)-native_fields
        if unexpected:
            labels=', '.join(sorted(field for field in unexpected if re.fullmatch('[a-z_]{1,30}',field)))
            raise ValueError(role+': Unsupported native model fields'+(' ('+labels+')' if labels else '')+'. Custom transport fields are not allowed.')
        try:
            configuration=models.ModelConfig(type=models.ModelType.CHAT,provider=conf['provider'],name=conf['name'],
                api_key=conf.get('api_key') or '',api_base=conf.get('api_base') or '',kwargs=deepcopy(conf.get('kwargs') or {}))
            options=configuration.build_kwargs()
        except Exception:raise ValueError('Invalid model settings. Check context size and advanced parameters.') from None
        if options.get('api_key'):raise ValueError('Store keys centrally or per profile, never inside preset parameters.')
        if not options.get('api_base'):options['api_base']=policy.endpoint
        validate_model_parameters(options,policy)
    if preset.get('embedding')!=embedding():
        # Native editor preserves empty transport fields and rate controls.
        # They are harmless locally; nonempty transport options remain forbidden.
        clean=deepcopy(preset.get('embedding',{}));clean.setdefault('kwargs',{})
        for field in ('api_base','api_key'):
            if clean.get(field) in (None,''):clean.pop(field,None)
        for field in ('rl_requests','rl_input'):
            if field in clean and type(clean[field]) in (int,float) and clean[field]>=0:clean.pop(field)
        if clean!=embedding():raise ValueError('Use the configured local embedding model without custom transport parameters.')

def fingerprint(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def current_snapshot():
    from . import manager as m
    from helpers import files,plugins
    from plugins._model_config.helpers import model_config as mc
    user=m.directory().parent
    paths=[mc._get_presets_path(),plugins.determine_plugin_asset_path('_model_config','','','config.json'),*[str(m.directory()/name) for name in ('setup.json','local.json','config.json')]]
    for asset in plugins.find_plugin_assets('setup.json',plugin_name='requesty',project_name='*',agent_profile='*',only_first=False):
        paths.append(asset['path'])
        paths.append(plugins.determine_plugin_asset_path('_model_config',asset['project_name'],asset['agent_profile'],'config.json'))
    result={}
    for value in paths:
        path=__import__('pathlib').Path(value)
        if not path.is_absolute() and path.parts and path.parts[0]==files.USER_DIR:
            path=user.joinpath(*path.parts[1:])
        if path.is_symlink() or not path.resolve().is_relative_to(user):raise ValueError('Unsafe preset migration source.')
        result[str(path.relative_to(user))]=path.read_text(encoding='utf-8') if path.exists() else None
    return result

def preview(overrides=None, preserve_current=True):
    from . import manager as m
    from plugins._model_config.helpers import model_config as mc
    if m.read('setup.json',{}).get('native_presets'):
        return {'already_migrated':True,'presets':mc.get_presets(),'fingerprint':fingerprint(current_snapshot()),'blocked':[]}
    available=catalog();existing=mc.get_presets();changes=overrides or {};result=[];blocked=[]
    for name,default in TEMPLATES.items():
        choice=changes.get(name,{})
        ids=(choice.get('main',default[0]),choice.get('utility',default[1]),choice.get('vision',default[2]))
        try:result.append(build(name,*ids,available))
        except ValueError as error:blocked.append({'name':name,'reason':str(error),'main':ids[0],'utility':ids[1],'vision':ids[2]})
    for old in existing:
        if str(old.get('name','')).casefold() in {name.casefold() for name in TEMPLATES}:continue
        converted=changes.get(old['name'])
        if converted:
            result.append(build(old['name'],converted['main'],converted['utility'],converted.get('vision'),available));continue
        try:validate(old,available);result.append(deepcopy(old))
        except ValueError:result.append(deepcopy(old)) # retained but runtime/UI blocked
    profiles=[]
    from helpers import plugins
    from usr.plugins.requesty.helpers import scope
    for asset in plugins.find_plugin_assets('setup.json',plugin_name='requesty',project_name='*',agent_profile='*',only_first=False):
        identity=(asset['project_name'],asset['agent_profile']);old=scope.read(identity,'setup.json',{})
        if not old.get('active') or not old.get('models'):continue
        name=('Requesty Profil '+identity[1])[:65]+' '+fingerprint(identity)[:8]
        original=old['models'];choice=changes.get(name,{})
        try:
            item=build(name,choice.get('main',original['chat']['name']),choice.get('utility',original['utility']['name']),choice.get('vision',original.get('vision',{}).get('name')),available)
            result.append(item);profiles.append({'project_name':identity[0],'agent_profile':identity[1],'preset_name':name})
        except ValueError as error:blocked.append({'name':name,'reason':str(error),'main':original['chat']['name'],'utility':original['utility']['name'],'vision':None})
    setup=m.read('setup.json',{});selected='Default'
    if preserve_current and setup.get('active') and setup.get('models'):
        old=setup['models'];name='Requesty bisherige Einrichtung'
        names={p['name'].casefold() for p in result};suffix=1
        while name.casefold() in names:name='Requesty bisherige Einrichtung '+str(suffix);suffix+=1
        result.append(build(name,old['chat']['name'],old['utility']['name'],old.get('vision',{}).get('name'),available));selected=name
    return {'already_migrated':False,'presets':result,'previous':existing,'blocked':blocked,'selected':selected,
            'profiles':profiles,'fingerprint':fingerprint(current_snapshot()),'cost_categories':{'Default':'Standard · kostenpflichtiges Sol-Modell','Efficiency':'Kostenorientiert','Power':'Hohe Leistung · höhere Kosten'}}

def apply(expected, overrides=None, preserve_current=True, languages=None):
    from . import manager as m
    from helpers import plugins
    from plugins._model_config.helpers import model_config as mc
    from agent import AgentContext
    if any(c.is_running() for c in AgentContext.all()):raise ValueError('Wait until running chats finish before migrating presets.')
    if m.read('setup.json',{}).get('native_presets'):return {'already_migrated':True}
    candidate=preview(overrides,preserve_current)
    if expected!=candidate['fingerprint']:raise ValueError('Preset settings changed. Review a fresh migration preview.')
    if candidate['blocked']:raise ValueError('Choose replacements for all unavailable standard models before migration.')
    before=current_snapshot()
    from . import adapters
    adapters.install()
    written={};user=m.directory().parent
    backup=m.directory()/'preset-backups';backup.mkdir(mode=0o700,parents=True,exist_ok=True)
    token=uuid4().hex;path=backup/(token+'.json')
    if backup.is_symlink() or not backup.resolve().is_relative_to(m.directory()):raise ValueError('Unsafe preset backup storage.')
    def save_backup():
        from usr.plugins.requesty.helpers.configuration import atomic_write
        atomic_write(path,json.dumps({'before':before,'written':written},ensure_ascii=False));path.chmod(0o600)
    save_backup()
    try:
        if languages:m.configure_local(languages)
        m.filter_check(m.read('local.json',{}))
        mc.save_presets(candidate['presets'])
        plugins.save_plugin_config('_model_config','','',{'model_preset':candidate['selected']})
        from usr.plugins.requesty.helpers import scope
        from usr.plugins.requesty.helpers.configuration import atomic_write
        for profile in candidate['profiles']:
            identity=(profile['project_name'],profile['agent_profile'])
            settings_path=__import__('pathlib').Path(plugins.determine_plugin_asset_path('_model_config',*identity,'config.json'))
            previous=json.loads(settings_path.read_text()) if settings_path.exists() else {}
            atomic_write(settings_path,json.dumps({**previous,'model_preset':profile['preset_name']}))
            atomic_write(scope.path(identity,'setup.json'),json.dumps({'active':True,'native_presets':True,'preset_name':profile['preset_name']}))
        m.write('setup.json',{'active':True,'native_presets':True,'preset_name':candidate['selected']})
        from . import preset_bridge
        preset_bridge.install()
        if not preset_bridge.healthy():raise ValueError('Native preset integration could not be installed.')
        for relative in before:
            p=user/relative;written[relative]=fingerprint(p.read_text(encoding='utf-8') if p.exists() else None)
        save_backup()
    except BaseException:
        for relative,value in before.items():
            p=user/relative
            if value is None:
                if p.exists():p.unlink()
            else:
                from usr.plugins.requesty.helpers.configuration import atomic_write
                atomic_write(p,value)
        from helpers import cache
        cache.clear(mc.PRESETS_CACHE_AREA)
        raise
    return {'backup_id':token,'selected':candidate['selected'],'presets':candidate['presets']}

def restore(token):
    from . import manager as m
    if m.active():raise ValueError('Deactivate centrally before restoring pre-migration settings.')
    if not isinstance(token,str) or not re.fullmatch('[a-f0-9]{32}',token):raise ValueError('Invalid backup identity.')
    path=m.directory()/'preset-backups'/(token+'.json')
    if path.is_symlink() or not path.resolve().is_relative_to(m.directory()):raise ValueError('Unsafe backup storage.')
    record=json.loads(path.read_text(encoding='utf-8'));user=m.directory().parent
    for relative,digest in record['written'].items():
        p=user/relative
        if p.is_symlink() or not p.resolve().is_relative_to(user):raise ValueError('Unsafe restore destination.')
        value=p.read_text(encoding='utf-8') if p.exists() else None
        if fingerprint(value)!=digest:raise ValueError('Settings changed after migration; restore would overwrite your edits.')
    from usr.plugins.requesty.helpers.configuration import atomic_write
    for relative,value in record['before'].items():
        p=user/relative
        if p.is_symlink() or not p.resolve().is_relative_to(user):raise ValueError('Unsafe restore destination.')
        if value is None:
            if p.exists():p.unlink()
        else:atomic_write(p,value)
    from helpers import cache
    from plugins._model_config.helpers import model_config as mc
    cache.clear(mc.PRESETS_CACHE_AREA)
    return {'restored':True}
