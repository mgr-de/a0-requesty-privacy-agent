"""Native framework integration, with catalog and embedding checks offline."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import pytest

pytest.importorskip('agent')

@pytest.fixture
def setup(monkeypatch,tmp_path):
    import shutil
    from usr.plugins.requesty_privacy_agent.helpers import manager as m
    from usr.plugins.requesty.helpers import scope
    from helpers import files
    # A private user directory prevents any interaction with the live setup.
    original=files.get_abs_path
    installed=Path(original(files.USER_DIR))/'extensions/python'
    if installed.exists():shutil.copytree(installed,tmp_path/'extensions/python')
    monkeypatch.setattr(files,'get_abs_path',lambda first,*rest: str(tmp_path.joinpath(*rest)) if first==files.USER_DIR else original(first,*rest))
    monkeypatch.setattr(m,'require_components',lambda:None)
    m.write('config.json',dict(m.MINIMUM))
    monkeypatch.setattr(m,'components',lambda:dict.fromkeys(m.MIN_VERSIONS,{'compatible':True,'installed':True,'version':'test'}))
    local={'enabled':True,'pii_filter':{'enabled':True,'use_ner':True,'use_regex':True,'languages':['de'],'action':'redact'},
        'local_embedding':{'enabled':True,'auto_configure':True,'model':'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'}}
    m.write('local.json',local)
    m.write('active.json',{'active':True})
    return m,scope,tmp_path

def test_minimum_cannot_be_weakened_and_stricter_zdr_survives(setup):
    m,scope,path=setup
    weak={'region':'us','strict_region':False,'no_retention':False,'no_training':False,'require_requesty_zdr':True}
    effective=m.effective_policy(weak)
    assert effective=={**m.MINIMUM,'require_requesty_zdr':True}
    from usr.plugins.requesty.helpers.policy import Policy
    assert 'cannot currently be verified' in ' '.join(Policy.parse(effective).reasons({'id':'a','api':'chat','data_retention':False,'data_used_for_training':False,'geolocation':'eu'}))

def test_global_off_switch_does_not_disable_instance_and_no_shared_after_deactivate(setup):
    m,scope,path=setup
    assert scope.enabled(('','any-new-profile'))
    m.deactivate('DISABLE_INSTANCE_PROTECTION')
    assert not scope.enabled(m.SHARED)

def test_mapping_identity_stable_across_profile_change_and_distinct_chats(setup):
    m,scope,path=setup
    from agent import Agent,AgentConfig
    a=Agent(0,AgentConfig(profile='agent0',mcp_servers=''))
    first=m.mapping_identity(a)
    a.config.profile='developer'
    assert m.mapping_identity(a)==first
    from usr.plugins.local_privacy_guard.helpers.model_guard import mapping_for
    firstmap=mapping_for(a)
    b=Agent(0,AgentConfig(profile='developer',mcp_servers=''))
    assert mapping_for(b).namespace!=firstmap.namespace

def test_common_defaults_without_profile_writes(setup):
    m,scope,path=setup
    from agent import Agent,AgentConfig
    a=Agent(0,AgentConfig(profile='agent0',mcp_servers=''))
    m.write('setup.json',{'active':True,'models':{'chat':{'name':'one'},'utility':{'name':'two'},'vision':{'name':'three'}}})
    assert m.requesty_owner(a)==m.SHARED
    data={'args':('_model_config',a),'result':{'chat_model':{'name':'old'},'utility_model':{},'vision_model':{}}}
    m.apply_model_config(data,a)
    assert data['result']['chat_model']['name']=='one'
    assert data['result']['vision_model']['name']=='three'
    assert not (path/'agents'/'agent0'/'plugins'/'requesty'/'setup.json').exists()

def test_local_disabled_filter_inherits_minimum(setup,monkeypatch):
    m,scope,path=setup
    from agent import Agent,AgentConfig
    from usr.plugins.local_privacy_guard.helpers import agent_scope
    target=path/'profile.json';target.write_text(json.dumps({'enabled':False,'pii_filter':{'enabled':False,'use_ner':False,'action':'log_only','languages':['fr']}}))
    monkeypatch.setattr(agent_scope,'selected_path',lambda *args:target)
    cfg=m.local_config(Agent(0,AgentConfig(profile='agent0',mcp_servers='')))
    assert cfg['enabled'] and cfg['pii_filter']['enabled'] and cfg['pii_filter']['use_ner']
    assert cfg['pii_filter']['action']=='redact'
    assert set(cfg['pii_filter']['languages'])=={'en','de','fr'}
    assert cfg['pii_filter']['ner_entity_types']==[]

def test_profile_cannot_replace_builtin_regex_or_narrow_ner(setup,monkeypatch):
    m,scope,path=setup
    from agent import Agent,AgentConfig
    from usr.plugins.local_privacy_guard.helpers import agent_scope
    target=path/'profile.json'
    target.write_text(json.dumps({'pii_filter':{'ner_entity_types':['NOT_A_PERSON'],'custom_patterns':[{'name':'EMAIL','regex':'never-match-this'}]}}))
    monkeypatch.setattr(agent_scope,'selected_path',lambda *args:target)
    with pytest.raises(ValueError,match='must not replace built-in'):
        m.local_config(Agent(0,AgentConfig(profile='agent0',mcp_servers='')))
    target.write_text(json.dumps({'pii_filter':{'ner_entity_types':['NOT_A_PERSON']}}))
    assert m.local_config(Agent(0,AgentConfig(profile='agent0',mcp_servers='')))['pii_filter']['ner_entity_types']==[]

def test_legacy_unowned_external_call_blocked_before_transport(setup):
    m,scope,path=setup
    wrapper=SimpleNamespace(kwargs={'api_base':'https://router.eu.requesty.ai/v1'},a0_model_conf=SimpleNamespace(api_base=''))
    with pytest.raises(ValueError,match='no protected chat owner'):
        m.enforce_call({'args':(wrapper,), 'kwargs':{}},'unified_call')

def test_key_and_configuration_errors_do_not_activate(setup):
    m,scope,path=setup
    m.write('active.json',{'active':False})
    with pytest.raises(ValueError):m.save_key('invalid key')
    with pytest.raises(ValueError):m.configure({'main':'missing'})
    assert not m.active()

def test_shared_key_never_returned_in_status(setup):
    m,scope,path=setup
    m.write('active.json',{'active':False})
    m.save_key('SYNTHETIC_PRIVATE_KEY_123')
    assert 'SYNTHETIC_PRIVATE_KEY_123' not in json.dumps(m.public_status())

def test_corrupt_active_marker_does_not_fail_open(setup):
    m,scope,path=setup
    (m.directory()/'active.json').write_text('{invalid')
    from usr.plugins.requesty.helpers.instance import manager
    with pytest.raises(ValueError,match='activation cannot be read'):manager()

def test_native_models_and_vision_protected_when_companion_discovery_is_off(setup,monkeypatch):
    import asyncio
    from agent import Agent,AgentConfig
    from helpers import plugins,extension,cache,litellm_transport
    from plugins._model_config.helpers import model_config as mc
    from usr.plugins.requesty.helpers import catalog
    from litellm import ModelResponse
    from usr.plugins.local_privacy_guard.helpers.model_guard import PrivacyWrapper,mapping_for
    m,scope,path=setup
    identifier='synthetic/eu-flash'
    model={'provider':'requesty_guarded','name':identifier,'api_base':m.MINIMUM and 'https://router.eu.requesty.ai/v1',
        'kwargs':{},'ctx_length':8192,'vision':True}
    m.write('credentials.json',{'key':'synthetic-instance-key'})
    m.write('setup.json',{'active':True,'models':dict(chat=model,utility=model,vision={**model,'override_main':True})})
    metadata={'id':identifier,'api':'chat','geolocation':'eu','data_retention':False,'data_used_for_training':False,
              'context_window':8192,'supports_vision':True,'supports_tool_calling':True}
    monkeypatch.setattr(catalog,'fetch',lambda *a,**kw:{identifier:metadata})
    enabled=plugins.get_enabled_plugins
    monkeypatch.setattr(plugins,'get_enabled_plugins',lambda a:[name for name in enabled(a) if name not in {'requesty','local_privacy_guard'}])
    captured=[]
    async def transport(**kwargs):
        captured.append(kwargs)
        return ModelResponse(choices=[{'message':{'role':'assistant','content':'alice@example.invalid'},'finish_reason':'stop'}])
    monkeypatch.setattr(litellm_transport,'acompletion',transport)
    cache.clear(extension._CLASSES_CACHE_AREA);cache.clear(extension._EXTENSIONS_CACHE_AREA)
    try:
        a=Agent(0,AgentConfig(profile='agent0',mcp_servers=''))
        for getter in (a.get_chat_model,a.get_utility_model):
            wrapper=getter();assert isinstance(wrapper,PrivacyWrapper)
            result=asyncio.run(wrapper.unified_call(user_message='alice@example.invalid'))
            assert 'alice@example.invalid' not in str(result)
            assert mapping_for(a).restore(result[0])=='alice@example.invalid'
        async def vision():
            from langchain_core.messages import HumanMessage
            await extension.call_extensions_async('tool_execute_before',a,tool_name='vision_load',tool_args={})
            try:
                wrapper=mc.build_vision_model(a)
                await wrapper.unified_call(messages=[HumanMessage(content=[{'type':'text','text':'alice@example.invalid'},
                    {'type':'image_url','image_url':{'url':'data:image/png;base64,SYNTHETIC'}}])])
            finally:await extension.call_extensions_async('tool_execute_after',a)
        asyncio.run(vision())
        assert len(captured)==3
        assert all(item['model']=='openai/'+identifier for item in captured)
        assert all('alice@example.invalid' not in json.dumps(item['messages']) for item in captured)
        assert 'data:image/png;base64,SYNTHETIC' in json.dumps(captured[-1]['messages'])
        assert a.context.get_data('local_privacy_media') is True
        assert a.context.get_data('local_privacy_media_route')['model']=='openai/'+identifier
        # LangChain invoke on the getter's wrapper must also prove that the
        # text filter ran before the otherwise unextensible legacy transport.
        monkeypatch.setattr(litellm_transport,'completion',lambda **kw:ModelResponse(choices=[{'message':{'role':'assistant','content':'alice@example.invalid'},'finish_reason':'stop'}]))
        result=a.get_chat_model().invoke('alice@example.invalid')
        assert 'alice@example.invalid' not in result.content
        assert mapping_for(a).restore(result.content)=='alice@example.invalid'
        # A stricter profile rule applies even while models/key are inherited.
        policy_path=scope.path(('','agent0'),'config.json');policy_path.parent.mkdir(parents=True,exist_ok=True)
        policy_path.write_text(json.dumps({**m.MINIMUM,'require_requesty_zdr':True}))
        from usr.plugins.requesty.helpers.policy import PolicyError
        with pytest.raises(PolicyError,match='cannot currently be verified'):
            asyncio.run(a.get_chat_model().unified_call(user_message='synthetic'))
        assert len(captured)==3
    finally:
        cache.clear(extension._CLASSES_CACHE_AREA);cache.clear(extension._EXTENSIONS_CACHE_AREA)

def test_native_final_remove_cleans_mapping_but_archive_retains_it(setup):
    from agent import Agent,AgentConfig,AgentContext
    from flask import Flask
    from helpers import cache,extension
    from usr.plugins.local_privacy_guard.helpers.model_guard import mapping_for
    cache.clear(extension._CLASSES_CACHE_AREA);cache.clear(extension._EXTENSIONS_CACHE_AREA)
    app=Flask(__name__)
    deleted=Agent(0,AgentConfig(profile='agent0',mcp_servers=''))
    archived=Agent(0,AgentConfig(profile='agent0',mcp_servers=''))
    dm=mapping_for(deleted);am=mapping_for(archived)
    dm.token('PERSON','Deleted Synthetic');am.token('PERSON','Archived Synthetic')
    with app.test_request_context('/api/chat_archive'):AgentContext.remove(archived.context.id)
    assert am.path.exists()
    with app.test_request_context('/api/chat_remove'):AgentContext.remove(deleted.context.id)
    assert not dm.path.exists()
    cache.clear(extension._CLASSES_CACHE_AREA);cache.clear(extension._EXTENSIONS_CACHE_AREA)

def test_bound_flag_without_filter_passage_does_not_authorize_external_send(setup):
    from usr.plugins.requesty.helpers.wrapper import GuardedRequestyWrapper
    import models
    m,scope,path=setup
    wrapper=GuardedRequestyWrapper(model='synthetic/eu',provider='openai',model_config=models.ModelConfig(type=models.ModelType.CHAT,provider='requesty_guarded',name='synthetic/eu'),api_base='https://router.eu.requesty.ai/v1')
    wrapper._requesty_scope=m.SHARED;wrapper._requesty_policy_bound=True
    with pytest.raises(ValueError,match='no protected chat owner'):
        m.enforce_call({'args':(wrapper,),'kwargs':{'user_message':'alice@example.invalid'}},'unified_call')

def test_old_bare_langchain_wrapper_stops_and_bridge_is_reversible(setup):
    from langchain_core.messages import HumanMessage
    import models
    m,scope,path=setup
    m.remove_legacy_bridge()
    original=models.LiteLLMChatWrapper._call
    wrapper=models.LiteLLMChatWrapper(model='old',provider='openai',model_config=models.ModelConfig(type=models.ModelType.CHAT,provider='openrouter',name='old'))
    m.install_legacy_bridge()
    with pytest.raises(ValueError,match='has not passed the chat text filter'):
        wrapper._call([HumanMessage(content='alice@example.invalid')])
    m.deactivate('DISABLE_INSTANCE_PROTECTION')
    assert models.LiteLLMChatWrapper._call is original

def test_activation_validates_all_slots_before_committing_marker(setup,monkeypatch):
    from usr.plugins.requesty.helpers import catalog
    from usr.plugins.requesty_privacy_agent.helpers import adapters
    from agent import AgentContext
    m,scope,path=setup
    m.write('active.json',{'active':False})
    models={slot:{'name':'synthetic/eu'} for slot in ('chat','utility','vision')}
    m.write('setup.json',{'active':True,'models':models})
    m.write('credentials.json',{'key':'synthetic-instance-key'})
    metadata={'id':'synthetic/eu','api':'chat','geolocation':'eu','data_retention':False,'data_used_for_training':False,'supports_tool_calling':True,'supports_vision':False}
    monkeypatch.setattr(catalog,'fetch',lambda *args,**kw:{metadata['id']:metadata})
    monkeypatch.setattr(m,'filter_check',lambda config:True)
    installed=[];monkeypatch.setattr(adapters,'install',lambda:installed.append(True))
    monkeypatch.setattr(AgentContext,'all',lambda:[])
    with pytest.raises(ValueError,match='Vision support'):m.activate()
    assert not m.active() and not installed
    metadata['supports_vision']=True;m.activate()
    assert m.active() and installed==[True]
    m.deactivate('DISABLE_INSTANCE_PROTECTION')


def test_native_profile_editor_without_chat_id_and_scoped_menu_choice(setup,monkeypatch):
    import asyncio
    from plugins._agent_editor.helpers.editor import build_editor_state
    from usr.plugins.requesty.helpers import catalog
    from usr.plugins.requesty.api.presets import Presets
    from agent import Agent,AgentConfig
    m,scope,path=setup
    identifier='bedrock/synthetic@eu-central-1'
    config={'provider':'requesty_guarded','name':identifier,'api_base':'https://router.eu.requesty.ai/v1','ctx_length':10000,'vision':True,'kwargs':{}}
    m.write('setup.json',{'active':True,'models':{slot:dict(config) for slot in ('chat','utility','vision')}})
    monkeypatch.setattr(scope,'key',lambda owner:'SYNTHETIC-SECRET')
    monkeypatch.setattr(catalog,'fetch',lambda *args,**kwargs:{identifier:{'id':identifier,'api':'chat','geolocation':'eu','data_retention':False,'data_used_for_training':False,'context_window':10000,'supports_vision':True}})
    state=build_editor_state('agent0')
    assert state['profile']['id']=='agent0'
    a=Agent(0,AgentConfig(profile='agent0',mcp_servers=''))
    result=asyncio.run(Presets(None,None).process({'context_id':a.context.id},None))
    assert result['scoped']['allowed'],result['scoped']['reasons']
    assert result['scoped']['name']=='Privacy Agent · gemeinsam'
    assert result['scoped']['models']['main']['name']==identifier
    assert 'SYNTHETIC-SECRET' not in json.dumps(result)
