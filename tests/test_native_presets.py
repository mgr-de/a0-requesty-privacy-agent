"""Native storage, migration and routing: synthetic metadata, no provider calls."""
import asyncio
from copy import deepcopy
import json
import pytest
from test_manager import setup
from usr.plugins.requesty_privacy_agent.helpers import native_presets as n,preset_bridge
from plugins._model_config.helpers import model_config as mc

@pytest.fixture
def native(setup,monkeypatch):
    m,scope,path=setup
    from helpers import plugins
    from helpers import files
    from pathlib import Path
    previous_abs=files.get_abs_path
    def isolated_abs(first,*rest):
        raw=str(first)
        if raw.startswith('usr/'):return str(path.joinpath(raw[4:],*rest))
        if raw.startswith('/a0/usr/'):return str(path.joinpath(raw[8:],*rest))
        return previous_abs(first,*rest)
    monkeypatch.setattr(files,'get_abs_path',isolated_abs)
    original_path=plugins.determine_plugin_asset_path
    def isolated_path(*args,**kwargs):
        raw=Path(original_path(*args,**kwargs))
        if not raw.is_absolute() and raw.parts and raw.parts[0]=='usr':return str(path.joinpath(*raw.parts[1:]))
        return str(raw)
    monkeypatch.setattr(plugins,'determine_plugin_asset_path',isolated_path)
    original_assets=plugins.find_plugin_assets
    monkeypatch.setattr(plugins,'find_plugin_assets',lambda *a,**k:[] if a and a[0]=='setup.json' else original_assets(*a,**k))
    names={name for values in n.TEMPLATES.values() for name in values if name}
    available={name:{'id':name,'api':'chat','geolocation':'eu','data_retention':False,
                     'data_used_for_training':False,'context_window':10000,'supports_tool_calling':True,
                     'supports_vision':name!='glm-5.3@eu'} for name in names}
    monkeypatch.setattr(n,'catalog',lambda:deepcopy(available))
    from usr.plugins.requesty.helpers import catalog
    monkeypatch.setattr(catalog,'fetch',lambda *a,**k:deepcopy(available))
    monkeypatch.setattr(m,'filter_check',lambda config:{'names':'available','embeddings':'available_locally'})
    monkeypatch.setattr(scope,'key',lambda owner:'SYNTHETIC-KEY')
    yield m,path,available
    preset_bridge.remove()

def migrate(native,preserve=False):
    candidate=n.preview(preserve_current=preserve)
    return n.apply(candidate['fingerprint'],preserve_current=preserve)

def test_fresh_defaults_are_native_and_default_is_selected(native):
    m,path,available=native
    migrate(native)
    assert [p['name'] for p in mc.get_presets()]==['Default','Efficiency','Power']
    assert mc.get_configured_preset_name()=='Default'
    assert m.read('setup.json')['native_presets'] and 'models' not in m.read('setup.json')
    assert preset_bridge.healthy()
    assert n.preview()['already_migrated']
    assert n.apply('ignored')['already_migrated']

def test_existing_deepseek_is_preserved_as_native_selected_preset(native):
    m,path,available=native
    model=n.slot('deepseek-v4.1-flash@eu',available)
    m.write('setup.json',{'active':True,'models':{'chat':model,'utility':model,'vision':model}})
    migrate(native,True)
    name=mc.get_configured_preset_name()
    assert name.startswith('Requesty bisherige Einrichtung')
    assert mc.resolve_preset(name)['chat']['name']=='deepseek-v4.1-flash@eu'

def test_unavailable_model_and_stale_preview_do_not_commit(native):
    m,path,available=native
    candidate=n.preview();before=n.current_snapshot()
    available.pop('gpt-6.1-sol@eu')
    with pytest.raises(ValueError,match='replacements'):n.apply(candidate['fingerprint'])
    assert n.current_snapshot()==before
    m.write('setup.json',{'active':False,'changed':True})
    with pytest.raises(ValueError,match='changed'):n.apply(candidate['fingerprint'])

def test_failed_commit_rolls_back_and_restore_refuses_later_edits(native,monkeypatch):
    m,path,available=native
    candidate=n.preview();before=n.current_snapshot();write=m.write
    def fail(name,value):
        if name=='setup.json':raise RuntimeError('simulated interrupted commit')
        return write(name,value)
    monkeypatch.setattr(m,'write',fail)
    with pytest.raises(RuntimeError):n.apply(candidate['fingerprint'])
    assert n.current_snapshot()==before
    monkeypatch.setattr(m,'write',write)
    receipt=migrate(native)
    presets=mc.get_presets();presets[0]['utility']=n.slot('deepseek-v4.1-flash@eu',available);mc.save_presets(presets)
    m.deactivate('DISABLE_INSTANCE_PROTECTION')
    with pytest.raises(ValueError,match='changed'):n.restore(receipt['backup_id'])

@pytest.mark.parametrize('change',[{'provider':'openrouter'},{'api_base':'https://other.test'},
                                  {'kwargs':{'fallbacks':['unsafe']}},{'name':'unknown'},
                                  {'api_key':'SYNTHETIC-DO-NOT-SAVE'}])
def test_native_save_blocks_unsafe_model_changes(native,change):
    migrate(native);before=n.current_snapshot();presets=mc.get_presets()
    presets[0]['chat'].update(change)
    with pytest.raises(ValueError):mc.save_presets(presets)
    assert n.current_snapshot()==before

def test_native_editor_selection_and_search_use_protected_models(native):
    migrate(native)
    from agent import Agent,AgentConfig
    from plugins._agent_editor.helpers.editor import build_editor_state
    from plugins._model_config.api.model_search import ModelSearch
    state=build_editor_state('agent0')
    assert state['model_preset']['effective']=='Default'
    assert {p['name'] for p in state['model_presets']}=={'Default','Efficiency','Power'}
    search=asyncio.run(ModelSearch(None,None).process({'provider':'requesty_guarded','query':'deepseek','model_type':'chat'},None))
    assert search['models']==['deepseek-v4.1-flash@eu']
    a=Agent(0,AgentConfig(profile='agent0',mcp_servers=''))
    for name in ['Default','Efficiency','Power']:
        a.context.set_data('chat_model_override',{'preset_name':name})
        wrapper=a.get_chat_model()
        while hasattr(wrapper,'_privacy_inner'):wrapper=wrapper._privacy_inner
        assert wrapper.model_name=='openai/'+mc.resolve_preset(name)['chat']['name']

def test_embedding_and_vision_requirements_survive_native_save(native):
    migrate(native)
    presets=mc.get_presets();presets[0]['embedding']={'provider':'openai','name':'remote'}
    with pytest.raises(ValueError,match='embedding'):mc.save_presets(presets)
    presets=mc.get_presets();presets[1]['vision']={}
    with pytest.raises(ValueError,match='Vision'):mc.save_presets(presets)

def test_deactivation_restores_owned_methods_and_preserves_foreign_changes(native):
    migrate(native);original=mc.save_presets
    mc.save_presets=lambda *a,**k:None
    assert not preset_bridge.healthy()
    preset_bridge.remove()
    assert mc.save_presets is not original
    # Restore the pre-bridge method so this synthetic modification stays local.
    mc.save_presets=original.__wrapped__


def test_profile_setup_is_migrated_without_moving_its_key(native,monkeypatch):
    m,path,available=native
    from helpers import plugins
    from usr.plugins.requesty.helpers import scope
    from usr.plugins.requesty.helpers.configuration import atomic_write
    profile=('','developer');setup_path=scope.path(profile,'setup.json')
    model=n.slot('deepseek-v4.1-flash@eu',available)
    atomic_write(setup_path,json.dumps({'active':True,'models':{'chat':model,'utility':model}}))
    key_path=scope.path(profile,'credentials.json');atomic_write(key_path,json.dumps({'key':'PRIVATE-SYNTHETIC'}));before=key_path.read_bytes()
    original_assets=plugins.find_plugin_assets
    monkeypatch.setattr(plugins,'find_plugin_assets',lambda *args,**kwargs:[{'project_name':'','agent_profile':'developer','path':str(setup_path)}] if args and args[0]=='setup.json' else original_assets(*args,**kwargs))
    preview=n.preview();assert preview['profiles'][0]['agent_profile']=='developer'
    n.apply(preview['fingerprint'],preserve_current=True)
    converted=scope.read(profile,'setup.json')
    assert converted['native_presets'] and 'models' not in converted
    assert key_path.read_bytes()==before
    assert mc.get_configured_preset_name(agent_profile='developer')==converted['preset_name']


def test_stale_wrappers_and_direct_chat_selection_are_rejected(native):
    migrate(native)
    from agent import Agent,AgentConfig
    from usr.plugins.requesty.helpers.runtime_guard import guarded_kwargs
    from usr.plugins.requesty.helpers.call_context import tool_agent
    from plugins._model_config.api.model_override import ModelOverride
    a=Agent(0,AgentConfig(profile='agent0',mcp_servers=''))
    wrapper=a.get_chat_model()
    while hasattr(wrapper,'_privacy_inner'):wrapper=wrapper._privacy_inner
    presets=mc.get_presets();presets[0]['chat']=n.slot('deepseek-v4.1-flash@eu',native[2]);mc.save_presets(presets)
    token=tool_agent.set(a)
    try:
        with pytest.raises(ValueError,match='changed'):guarded_kwargs(wrapper,{})
    finally:tool_agent.reset(token)
    before=a.context.get_data('chat_model_override')
    result=asyncio.run(ModelOverride(None,None).process({'context_id':a.context.id,'action':'set','override':{'provider':'openrouter','name':'unsafe'}},None))
    assert result.status_code==400 and a.context.get_data('chat_model_override')==before

def test_successful_restore_keeps_deactivation_and_bridge_ownership(native):
    m,path,available=native
    before=n.current_snapshot();receipt=migrate(native)
    m.deactivate('DISABLE_INSTANCE_PROTECTION')
    assert n.restore(receipt['backup_id'])['restored']
    assert not m.active() and n.current_snapshot()==before


def test_browser_main_vision_and_utility_roles_use_their_native_selections(native):
    migrate(native)
    from agent import Agent,AgentConfig
    from usr.plugins.requesty.helpers.runtime_guard import guarded_kwargs
    from usr.plugins.requesty.helpers.call_context import tool_agent
    a=Agent(0,AgentConfig(profile='agent0',mcp_servers=''))
    wrappers=[]
    for getter in [a.get_chat_model,a.get_utility_model]:
        wrapper=getter()
        while hasattr(wrapper,'_privacy_inner'):wrapper=wrapper._privacy_inner
        wrappers.append(wrapper)
    a.context.set_data('_browser_model_active',True);token=tool_agent.set(a)
    try:
        for wrapper in wrappers:assert guarded_kwargs(wrapper,{})['api_base']=='https://router.eu.requesty.ai/v1'
    finally:tool_agent.reset(token)


def test_profile_key_without_legacy_model_copy_is_used_for_native_presets(native,monkeypatch):
    m,path,available=native;migrate(native)
    from agent import Agent,AgentConfig
    from usr.plugins.requesty.helpers import scope
    from usr.plugins.requesty.helpers.configuration import atomic_write,create
    identity=('','developer');atomic_write(scope.path(identity,'credentials.json'),json.dumps({'key':'PROFILE-KEY'}))
    monkeypatch.setattr(scope,'key',lambda owner:'PROFILE-KEY' if owner==identity else 'CENTRAL-KEY')
    a=Agent(0,AgentConfig(profile='developer',mcp_servers=''))
    wrapper=a.get_chat_model()
    while hasattr(wrapper,'_privacy_inner'):wrapper=wrapper._privacy_inner
    assert wrapper._requesty_scope==identity and wrapper.kwargs['api_key']=='PROFILE-KEY'
    with pytest.raises(ValueError,match='native'):create('ignored','ignored','ignored',{},identity)


def test_direct_embedding_and_catalog_routes_cannot_leave_local_processing(native):
    migrate(native)
    import models
    from plugins._model_config.api.model_search import ModelSearch
    with pytest.raises(ValueError,match='local embedding'):models.get_embedding_model('openai','remote')
    result=asyncio.run(ModelSearch(None,None).process({'provider':'openai','model_type':'embedding'},None))
    assert result.status_code==400
    result=asyncio.run(ModelSearch(None,None).process({'provider':'huggingface','model_type':'embedding'},None))
    assert result['models']==[n.embedding()['name']]
