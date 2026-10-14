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
    assert name.startswith('A0 Privacy bisherige Einrichtung')
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

def test_native_editor_empty_embedding_fields_do_not_block_valid_model_edits(native):
    migrate(native)
    from plugins._model_config.api.model_presets import ModelPresets
    presets=deepcopy(mc.get_presets())
    presets[0]['embedding'].update(api_base='',rl_requests=0,rl_input=0)
    presets[0]['chat']['max_embeds']=10
    presets[1]['utility']['name']='gpt-6-luna@eu'
    response=asyncio.run(ModelPresets(None,None).process({'action':'save','presets':presets},None))
    assert isinstance(response,dict),response.get_data(as_text=True)
    assert response['ok'] and mc.resolve_preset('Efficiency')['utility']['name']=='gpt-6-luna@eu'
    assert response['privacy_presets']['active']
    assert mc.get_embedding_providers()==[{'value':'huggingface','label':'Local HuggingFace'}]

def test_dynamic_native_api_loader_uses_the_same_policy_and_short_catalog(native,monkeypatch):
    m,path,available=native;migrate(native)
    from helpers.modules import load_classes_from_file
    from helpers import files
    from helpers.api import ApiHandler
    from flask import Flask,request
    handler=load_classes_from_file(files.get_abs_path('plugins/_model_config/api/model_search.py'),ApiHandler)[0](None,None)
    def forbidden(*args,**kwargs):raise AssertionError('Unfiltered native catalog must not run.')
    monkeypatch.setattr(handler,'_fetch_models',forbidden)
    available['vendor/deepseek-v4.1-flash']=dict(available['deepseek-v4.1-flash@eu'],id='vendor/deepseek-v4.1-flash')
    app=Flask(__name__)
    with app.test_request_context('/api/plugins/_model_config/model_search',method='POST',json={'provider':'requesty_guarded','query':'deepseek','model_type':'chat'}):
        result=asyncio.run(handler.handle_request(request))
        assert result.status_code==200
        assert result.get_json()['models']==['deepseek-v4.1-flash@eu']
    with app.test_request_context('/api/plugins/_model_config/model_search',method='POST',json={'provider':'openai','model_type':'embedding'}):
        assert asyncio.run(handler.handle_request(request)).status_code==400
    save=load_classes_from_file(files.get_abs_path('plugins/_model_config/api/model_presets.py'),ApiHandler)[0](None,None)
    bad=deepcopy(mc.get_presets());bad[0]['chat']['provider']='openrouter'
    before=mc.get_presets()
    with app.test_request_context('/api/plugins/_model_config/model_presets',method='POST',json={'action':'save','presets':bad}):
        assert asyncio.run(save.handle_request(request)).status_code==400
    assert mc.get_presets()==before


def test_native_presets_and_dynamic_profile_lifecycle_share_owned_api(native):
    migrate(native)
    from usr.plugins.requesty_privacy_agent.helpers import exception_lifecycle
    try:
        exception_lifecycle.install()
        assert preset_bridge.healthy()
        preset_bridge.install()
        exception_lifecycle.install()
        assert preset_bridge.healthy()
    finally:exception_lifecycle.remove()



def test_gateway_only_keeps_native_defaults_provider_lock_and_chat_selection(native,monkeypatch):
    m,path,available=native
    m.write('mode.json',{'local_guard_enabled':False})
    monkeypatch.setattr(m,'filter_check',lambda *a:pytest.fail('Gateway-only must not require NER'))
    migrate(native)
    assert [p['name'] for p in mc.get_presets()]==['Default','Efficiency','Power']
    assert [p['value'] for p in mc.get_chat_providers()]==['requesty_guarded']
    presets=mc.get_presets();presets[0]['chat']['provider']='openrouter'
    with pytest.raises(ValueError):mc.save_presets(presets)
    from agent import Agent,AgentConfig
    from plugins._model_config.api.model_override import ModelOverride
    import asyncio
    a=Agent(0,AgentConfig(profile='agent0',mcp_servers=''))
    wrapper=a.get_chat_model()
    assert not hasattr(wrapper,'_privacy_inner')
    assert wrapper._requesty_agent() is a
    assert wrapper.model_name=='openai/'+mc.resolve_preset('Default')['chat']['name']
    result=asyncio.run(ModelOverride(None,None).process({'context_id':a.context.id,'action':'set','override':{'provider':'openrouter','name':'unsafe'}},None))
    assert result.status_code==400
    from usr.plugins.local_privacy_guard.helpers import instance
    assert instance.manager() is None
    import models
    from unittest.mock import patch
    observed=[]
    source='Synthetic contact Anna Weber anna@example.com'
    async def complete(transport):
        observed.append(source in str(transport.messages))
        return {'response_delta':source,'reasoning_delta':''}
    with patch.object(models.LiteLLMTransport,'acomplete',complete):
        response,_=asyncio.run(wrapper.unified_call(user_message=source))
    assert response==source and observed==[True]
    a.context.set_data('chat_model_override',{'preset_name':'Efficiency'})
    assert a.get_chat_model().model_name=='openai/'+mc.resolve_preset('Efficiency')['chat']['name']



@pytest.mark.parametrize('local_guard',[False,True])
@pytest.mark.parametrize('shared_context',[False,True])
def test_subagent_preset_is_checked_against_getter_agent_not_parent_tool(native,local_guard,shared_context):
    m,path,available=native
    m.write('mode.json',{'local_guard_enabled':local_guard})
    migrate(native)
    from agent import Agent,AgentConfig
    from usr.plugins.requesty.helpers.runtime_guard import guarded_kwargs
    from usr.plugins.requesty.helpers.call_context import tool_agent,owner
    parent=Agent(0,AgentConfig(profile='agent0',mcp_servers=''))
    from helpers import plugins
    plugins.save_plugin_config('_model_config','','developer',{'model_preset':'Power'})
    child=Agent(1,AgentConfig(profile='developer',mcp_servers=''),context=parent.context if shared_context else None)
    if not shared_context:child.context.set_output_data('parent_context_id',parent.context.id)
    wrapper=child.get_chat_model()
    while hasattr(wrapper,'_privacy_inner'):wrapper=wrapper._privacy_inner
    assert wrapper._requesty_agent() is child
    assert wrapper._requesty_scope==owner(parent)
    token=tool_agent.set(parent)
    try:
        assert guarded_kwargs(wrapper,{})['api_base']=='https://router.eu.requesty.ai/v1'
        if not local_guard:
            import models,asyncio
            from unittest.mock import patch
            observed=[]
            async def complete(transport):
                observed.append(transport.model)
                return {'response_delta':'synthetic subordinate answer','reasoning_delta':''}
            with patch.object(models.LiteLLMTransport,'acomplete',complete):
                result=asyncio.run(wrapper.unified_turn(user_message='synthetic subordinate'))
            assert result.response=='synthetic subordinate answer'
            assert len(observed)==1 and observed[0].endswith(mc.resolve_preset('Power')['chat']['name'])
        child.context.set_data('chat_model_override',{'preset_name':'Efficiency'})
        with pytest.raises(ValueError,match='preset changed'):guarded_kwargs(wrapper,{})
        fresh=child.get_chat_model()
        while hasattr(fresh,'_privacy_inner'):fresh=fresh._privacy_inner
        assert guarded_kwargs(fresh,{})['api_base']=='https://router.eu.requesty.ai/v1'
    finally:tool_agent.reset(token)


def test_gateway_only_detects_changed_preset_without_parent_tool_context(native):
    m,path,available=native
    m.write('mode.json',{'local_guard_enabled':False});migrate(native)
    from agent import Agent,AgentConfig
    from usr.plugins.requesty.helpers.runtime_guard import guarded_kwargs
    a=Agent(0,AgentConfig(profile='agent0',mcp_servers=''));wrapper=a.get_chat_model()
    a.context.set_data('chat_model_override',{'preset_name':'Power'})
    with pytest.raises(ValueError,match='preset changed'):guarded_kwargs(wrapper,{})



def test_expired_model_owner_does_not_fall_back_to_parent_tool(native):
    m,path,available=native
    m.write('mode.json',{'local_guard_enabled':False});migrate(native)
    from agent import Agent,AgentConfig
    from usr.plugins.requesty.helpers.runtime_guard import guarded_kwargs
    from usr.plugins.requesty.helpers.call_context import tool_agent
    a=Agent(0,AgentConfig(profile='agent0',mcp_servers=''));wrapper=a.get_chat_model()
    wrapper._requesty_agent=lambda:None
    token=tool_agent.set(a)
    try:
        with pytest.raises(ValueError,match='owner is unavailable'):guarded_kwargs(wrapper,{})
    finally:tool_agent.reset(token)
