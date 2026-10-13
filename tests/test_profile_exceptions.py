"""Offline native policy tests: synthetic identities, no provider requests."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import asyncio
import json
import pytest

pytest.importorskip('agent')


@pytest.fixture
def policy(monkeypatch, tmp_path):
    from usr.plugins.requesty_privacy_agent.helpers import manager as m, profile_exceptions as p
    from helpers import files, subagents, login
    original = files.get_abs_path
    import shutil
    installed=Path(original(files.USER_DIR))/'extensions/python'
    if installed.exists():shutil.copytree(installed,tmp_path/'extensions/python')
    (tmp_path/'plugins').mkdir()
    monkeypatch.setattr(files, 'get_abs_path', lambda first, *parts:
        str(tmp_path.joinpath(*parts)) if first == files.USER_DIR else original(first, *parts))
    monkeypatch.setattr(m, 'require_components', lambda: None)
    monkeypatch.setattr(login, 'get_credentials_hash', lambda: 'synthetic-session-hash')
    from usr.plugins.local_privacy_guard.helpers import agent_scope
    monkeypatch.setattr(agent_scope,'selected_path',lambda project,profile:tmp_path/'absent-local.json')
    from plugins._agent_editor.helpers import editor
    monkeypatch.setattr(editor,'USER_AGENTS_ROOT',tmp_path/'agents')
    m.write('active.json', {'active': True})
    m.write('local.json', {'enabled': True, 'pii_filter': {'enabled': True, 'languages': ['en']},
        'local_embedding': {'enabled': True, 'auto_configure': True, 'model': 'sentence-transformers/synthetic-local-model'}})
    root = tmp_path / 'agents' / p.PROFILE
    root.mkdir(parents=True)
    (root / 'agent.yaml').write_text('title: Synthetic Developer\n')
    monkeypatch.setattr(subagents, 'get_available_agents_dict', lambda project=None:
        {p.PROFILE: SimpleNamespace(path=str(root), origin=['user'])})
    with m.LOCK:
        value = p.state()
        value['profiles'][p.PROFILE] = {'definition': p.definition(p.PROFILE), 'generation': 'synthetic-generation', 'grant': None}
        p.save(value, 'fixture', p.PROFILE)
    from flask import Flask
    app = Flask(__name__)
    app.secret_key = 'synthetic-test-session-only'
    with app.test_request_context('/'):
        from flask import session
        session['authentication'] = 'synthetic-session-hash'
        yield p, m, root
    from helpers import cache,extension,plugins
    cache.clear(extension._CLASSES_CACHE_AREA);cache.clear(extension._EXTENSIONS_CACHE_AREA)
    plugins.clear_plugin_cache()


def test_native_profile_creation_idempotent_and_builtin_only(policy, monkeypatch):
    p,m,root=policy
    value=p.state();value['profiles']={};p.save(value,'fixture_reset')
    (root/'agent.yaml').unlink();root.rmdir()
    from helpers import subagents
    monkeypatch.setattr(subagents,'get_agents_dict',lambda project=None:{})
    assert p.create_profile()==p.PROFILE
    assert (root/'agent.yaml').is_file()
    before=p.state()
    assert p.create_profile()==p.PROFILE
    assert p.state()==before
    assert not p.state()['profiles'][p.PROFILE]['grant']
    assert (root/'prompts').is_dir()


def test_memory_mode_and_root_identity_are_isolated(policy, monkeypatch):
    p,m,root=policy
    from usr.plugins.local_privacy_guard.helpers import agent_scope
    monkeypatch.setattr(agent_scope,'selected_path',lambda *args:root.parent/'absent.json')
    a=agent(p)
    before={'args':('_memory',),'result':{}}
    agent_scope.apply(before,a)
    approved_agent=approved(p)
    after={'args':('_memory',),'result':{}}
    agent_scope.apply(after,approved_agent)
    assert before['result']['agent_memory_subdir']!=after['result']['agent_memory_subdir']
    from agent import Agent,AgentConfig
    child=Agent(0,AgentConfig(profile='agent0',mcp_servers=''))
    child.context.set_output_data('parent_context_id',approved_agent.context.id)
    inherited={'args':('_memory',),'result':{}}
    agent_scope.apply(inherited,child)
    assert inherited['result']==after['result']


def test_setup_api_allows_local_explicit_grant_without_configured_login(policy,monkeypatch):
    p,m,root=policy
    from helpers import login
    from usr.plugins.requesty_privacy_agent.api.setup import Setup
    monkeypatch.setattr(login,'get_credentials_hash',lambda:'')
    for action in ('create-developer-profile','grant','revoke'):
        result=asyncio.run(Setup(None,None).process({'action':action,'profile_id':p.PROFILE,'confirmation':p.CONFIRM},None))
        assert result['ok'] is True
    assert not p.state()['profiles'][p.PROFILE]['grant']


def test_new_chat_api_is_empty_and_binds_before_publication(policy,monkeypatch):
    p,m,root=policy
    from usr.plugins.requesty_privacy_agent.api.developer_chat import DeveloperChat
    from usr.plugins.requesty_privacy_agent.api.setup import Setup
    from helpers import persist_chat,state_monitor_integration
    from agent import AgentContext
    import threading
    saved=[];published=[]
    monkeypatch.setattr(persist_chat,'save_tmp_chat',lambda context:saved.append((context.id,p.effective(context.agent0))))
    monkeypatch.setattr(persist_chat,'remove_chat',lambda context:None)
    monkeypatch.setattr(state_monitor_integration,'mark_dirty_all',lambda **kwargs:published.append(True))
    assert DeveloperChat.requires_auth() and DeveloperChat.requires_csrf()
    assert Setup.requires_auth() and Setup.requires_csrf()
    p.grant(p.PROFILE,p.CONFIRM)
    result=asyncio.run(DeveloperChat(None,threading.RLock()).process({'new_context':'ignored-client-id'},None))
    assert result['ok'] is True
    assert result['ctxid']!='ignored-client-id'
    context=AgentContext.get(result['ctxid'])
    assert context.agent0.history.all_messages()==[]
    assert saved[0][1]['mode']=='unmasked' and published
    p.revoke(p.PROFILE)
    before=set(p.state()['chats'])
    failed=asyncio.run(DeveloperChat(None,threading.RLock()).process({},None))
    assert failed['ok'] is False and set(p.state()['chats'])==before


def test_setup_authenticated_worker_and_list_never_expose_receipt(policy):
    p,m,root=policy
    from usr.plugins.requesty_privacy_agent.api.setup import Setup
    result=asyncio.run(Setup(None,None).process({'action':'grant','profile_id':p.PROFILE,'confirmation':p.CONFIRM},None))
    assert result['ok'] is True
    public=asyncio.run(Setup(None,None).process({'action':'list'},None))
    assert public['profile_exceptions']['profiles'][0]['granted']
    assert p.state()['profiles'][p.PROFILE]['grant'] not in json.dumps(public)


def test_native_profile_switch_back_does_not_reenable_old_chat(policy,monkeypatch):
    p,m,root=policy
    from usr.plugins.requesty_privacy_agent.helpers import exception_lifecycle
    from api.agent_profile_set import SetAgentProfile
    from helpers import subagents,persist_chat,state_monitor_integration
    from types import SimpleNamespace
    monkeypatch.setattr(subagents,'get_available_agents_dict',lambda project=None:{
        p.PROFILE:SimpleNamespace(path=str(root),origin=['user'],title='Developer'),
        'agent0':SimpleNamespace(title='Protected')})
    monkeypatch.setattr(persist_chat,'save_tmp_chat',lambda context:None)
    monkeypatch.setattr(state_monitor_integration,'mark_dirty_for_context',lambda *args,**kwargs:None)
    a=approved(p)
    exception_lifecycle.install()
    handler=SetAgentProfile(None,None)
    for profile in ('agent0',p.PROFILE):
        result=asyncio.run(handler.process({'context_id':a.context.id,'agent_profile':profile},None))
        assert result['ok'] is True
    with pytest.raises(ValueError):p.effective(a)


def test_native_wrappers_main_utility_vision_and_running_output(policy,monkeypatch):
    p,m,root=policy
    from agent import Agent,AgentConfig
    from helpers import litellm_transport,extension,cache
    from usr.plugins.requesty.helpers import catalog
    from usr.plugins.local_privacy_guard.helpers import agent_scope,transport_admission
    from litellm import ModelResponse
    monkeypatch.setattr(agent_scope,'selected_path',lambda *args:root.parent/'absent.json')
    identifier='synthetic/eu-flash'
    model={'provider':'requesty_guarded','name':identifier,'api_base':'https://router.eu.requesty.ai/v1',
        'kwargs':{},'ctx_length':8192,'vision':True}
    m.write('setup.json',{'active':True,'models':dict(chat=model,utility=model,vision={**model,'override_main':True})})
    m.write('credentials.json',{'key':'synthetic-managed-model-secret'})
    metadata={'id':identifier,'api':'chat','geolocation':'eu','data_retention':False,'data_used_for_training':False,
        'context_window':8192,'supports_vision':True,'supports_tool_calling':True}
    monkeypatch.setattr(catalog,'fetch',lambda *args,**kwargs:{identifier:metadata})
    captured=[]
    revoke_during_call=False
    async def provider(**kwargs):
        nonlocal revoke_during_call
        captured.append(kwargs)
        if revoke_during_call:p.revoke(p.PROFILE)
        return ModelResponse(choices=[{'message':{'role':'assistant','content':'alice@example.invalid'},'finish_reason':'stop'}])
    monkeypatch.setattr(litellm_transport,'acompletion',provider)
    cache.clear(extension._CLASSES_CACHE_AREA);cache.clear(extension._EXTENSIONS_CACHE_AREA)
    try:
        protected=agent(p)
        result=asyncio.run(protected.get_chat_model().unified_call(user_message='alice@example.invalid'))
        assert 'alice@example.invalid' not in str(result)
        a=approved(p)
        for getter in (a.get_chat_model,a.get_utility_model):
            result=asyncio.run(getter().unified_call(system_message='alice@example.invalid',user_message='alice@example.invalid'))
            assert result[0]=='alice@example.invalid'
            assert 'alice@example.invalid' in json.dumps(captured[-1]['messages'])
            assert captured[-1]['num_retries']==captured[-1]['max_retries']==0
        async def vision():
            from plugins._model_config.helpers import model_config as mc
            from langchain_core.messages import HumanMessage
            await extension.call_extensions_async('tool_execute_before',a,tool_name='vision_load',tool_args={})
            try:
                return await mc.build_vision_model(a).unified_call(messages=[HumanMessage(content='alice@example.invalid')])
            finally:await extension.call_extensions_async('tool_execute_after',a)
        assert asyncio.run(vision())[0]=='alice@example.invalid'
        count=len(captured)
        with pytest.raises(ValueError):
            asyncio.run(a.get_chat_model().unified_call(user_message='synthetic-managed-model-secret'))
        assert len(captured)==count
        # A request admitted before revocation finishes in its original mode.
        revoke_during_call=True
        result=asyncio.run(a.get_chat_model().unified_call(user_message='alice@example.invalid'))
        assert result[0]=='alice@example.invalid'
        with pytest.raises(ValueError):
            asyncio.run(a.get_chat_model().unified_call(user_message='alice@example.invalid'))
        assert len(captured)==count+1
    finally:
        cache.clear(extension._CLASSES_CACHE_AREA);cache.clear(extension._EXTENSIONS_CACHE_AREA)


def agent(p):
    from agent import Agent, AgentConfig
    return Agent(0, AgentConfig(profile=p.PROFILE, mcp_servers=''))


def approved(p):
    p.grant(p.PROFILE, p.CONFIRM)
    a = agent(p)
    p.bind_new(a.context, p.PROFILE)
    return a


def test_legacy_and_profile_switch_remain_masked(policy):
    p, m, root = policy
    a = agent(p)
    assert p.effective(a)['mode'] == 'masked'
    p.grant(p.PROFILE, p.CONFIRM)
    assert p.effective(a)['mode'] == 'masked'


@pytest.mark.parametrize('authenticated,configured', [(False, True), (True, True), (True, False), (False, False)])
def test_configured_login_still_requires_authentication(policy, monkeypatch, authenticated, configured):
    p, m, root = policy
    from helpers import login
    from flask import session
    monkeypatch.setattr(login, 'get_credentials_hash', lambda: 'synthetic-session-hash' if configured else '')
    session['authentication'] = 'synthetic-session-hash' if authenticated else ''
    for action in (p.create_profile, lambda: p.grant(p.PROFILE, p.CONFIRM), lambda: p.revoke(p.PROFILE)):
        if configured and not authenticated:
            with pytest.raises(ValueError, match='login'):
                action()
        else:
            action()


def test_operator_context_and_explicit_confirmation(policy):
    p, m, root = policy
    with pytest.raises(ValueError, match='Confirm'):
        p.grant(p.PROFILE, 'yes')
    assert not p.state()['profiles'][p.PROFILE]['grant']


def test_grant_idempotent_and_revocation_never_resurrects_old_chat(policy):
    p, m, root = policy
    a = approved(p)
    receipt = p.effective(a)
    p.grant(p.PROFILE, p.CONFIRM)
    assert p.effective(a) == receipt
    p.revoke(p.PROFILE)
    p.revoke(p.PROFILE)
    with pytest.raises(ValueError, match='new protected chat'):
        p.effective(a)
    p.grant(p.PROFILE, p.CONFIRM)
    with pytest.raises(ValueError):
        p.effective(a)
    assert p.effective(approved(p))['mode'] == 'unmasked'


def test_imported_claim_and_modified_claim_block(policy):
    p, m, root = policy
    a = approved(p)
    b = agent(p)
    b.context.set_data(p.CLAIM, deepcopy(a.context.get_data(p.CLAIM)))
    with pytest.raises(ValueError, match='Imported'):
        p.effective(b)
    a.context.get_data(p.CLAIM)['receipt'] = 'tampered'
    with pytest.raises(ValueError):
        p.effective(a)


@pytest.mark.parametrize('change', ['edit', 'delete', 'shadow', 'plugin_overlay', 'switch'])
def test_identity_changes_block(policy, monkeypatch, change):
    p, m, root = policy
    a = approved(p)
    if change == 'edit':
        (root / 'agent.yaml').write_text('title: Different Developer\n')
    elif change == 'delete':
        (root / 'agent.yaml').unlink()
        root.rmdir()
    elif change in {'shadow','plugin_overlay'}:
        from helpers import subagents
        monkeypatch.setattr(subagents, 'get_available_agents_dict', lambda project=None:
            {p.PROFILE: SimpleNamespace(path=str(root), origin=['user', 'project'] if change=='shadow' else ['plugin','user'])})
    elif change == 'switch':
        a.config.profile = 'agent0'
    with pytest.raises(ValueError):
        p.effective(a)


def test_local_chat_policy_independent_of_optional_login_configuration(policy,monkeypatch):
    p,m,root=policy
    from helpers import login
    a=approved(p)
    expected=p.effective(a)
    monkeypatch.setattr(login,'get_credentials_hash',lambda:'')
    assert p.effective(a)==expected
    p.revoke(p.PROFILE)
    with pytest.raises(ValueError):p.effective(a)


@pytest.mark.parametrize('subordinate',[False,True])
def test_revoked_chat_native_delete_uses_only_scoped_masked_initialization(policy,monkeypatch,subordinate):
    p,m,root=policy
    from api.chat_remove import RemoveChat
    from helpers import persist_chat,state_monitor_integration
    from helpers.task_scheduler import TaskScheduler
    from agent import AgentContext,Agent,AgentConfig
    from flask import current_app
    from usr.plugins.requesty_privacy_agent.helpers import exception_lifecycle
    a=approved(p)
    subject=a
    if subordinate:
        subject=Agent(0,AgentConfig(profile='agent0',mcp_servers=''))
        subject.context.set_output_data('parent_context_id',a.context.id)
    p.revoke(p.PROFILE)
    with pytest.raises(ValueError):p.effective(a)
    scope={'context_id':subject.context.id,'root_id':a.context.id,'active':True}
    token=p.deleting_chat.set(scope)
    try:
        assert p.effective(a)['mode']=='masked'
        with pytest.raises(ValueError,match='deletion'):m.enforce_call({},'unified_call')
        scope['active']=False
        with pytest.raises(ValueError):p.effective(a)
    finally:p.deleting_chat.reset(token)
    async def reload():return None
    scheduler=SimpleNamespace(cancel_tasks_by_context=lambda *args,**kwargs:None,
        reload=reload,get_tasks_by_context_id=lambda context_id:[])
    monkeypatch.setattr(TaskScheduler,'get',lambda:scheduler)
    monkeypatch.setattr(persist_chat,'remove_chat',lambda context_id:None)
    monkeypatch.setattr(state_monitor_integration,'mark_dirty_all',lambda **kwargs:None)
    exception_lifecycle.install()
    with current_app.test_request_context('/api/chat_remove'):
        result=asyncio.run(RemoveChat(None,None).process({'context':subject.context.id},None))
    assert result['message']=='Context removed.'
    assert AgentContext.get(subject.context.id) is None
    if subordinate:
        assert AgentContext.get(a.context.id) is not None
        assert a.context.id in p.state()['chats']
    else:assert a.context.id not in p.state()['chats']
    assert p.deleting_chat.get() is None
    with pytest.raises(ValueError):p.effective(a)


def test_native_reset_adapter_handles_revoked_policy_without_api_class_bridge(policy):
    p,m,root=policy
    from flask import current_app
    a=approved(p);p.revoke(p.PROFILE)
    with current_app.test_request_context('/api/chat_remove'):
        a.context.reset()
    assert p.deleting_chat.get() is None
    with pytest.raises(ValueError):p.effective(a)


def test_project_change_blocks_and_fresh_binding_is_separate(policy, monkeypatch):
    p, m, root = policy
    a = approved(p)
    from helpers import projects
    monkeypatch.setattr(projects, 'get_context_project_name', lambda context: 'synthetic-project')
    with pytest.raises(ValueError):
        p.effective(a)
    b = approved(p)
    assert p.effective(b)['project'] == 'synthetic-project'


def test_child_inherits_root_and_cannot_downgrade_protected_parent(policy):
    p, m, root = policy
    from agent import Agent, AgentConfig
    a = approved(p)
    child = Agent(0, AgentConfig(profile='agent0', mcp_servers=''))
    child.context.set_output_data('parent_context_id', a.context.id)
    assert p.effective(child) == p.effective(a)
    protected = agent(p)
    child.context.set_output_data('parent_context_id', protected.context.id)
    assert p.effective(child)['mode'] == 'masked'
    child.context.set_output_data('parent_context_id', 'synthetic-missing-parent')
    with pytest.raises(ValueError, match='parent'):
        p.effective(child)


def test_missing_and_cyclic_parents_block(policy):
    p, m, root = policy
    a = approved(p)
    a.context.set_output_data('parent_context_id', a.context.id)
    with pytest.raises(ValueError, match='Cyclic'):
        p.effective(a)


def test_remove_chat_and_reloaded_context(policy):
    p, m, root = policy
    a = approved(p)
    before = p.effective(a)
    assert p.state()['chats'][a.context.id] == before
    # Serialized claim is necessary but only accepted with the local registry.
    a.context.set_data(p.CLAIM, json.loads(json.dumps(before)))
    assert p.effective(a) == before
    p.remove_chat(a.context.id)
    with pytest.raises(ValueError, match='Imported'):
        p.effective(a)


def test_local_configuration_keeps_secrets_embedding_and_legacy_mapping(policy, monkeypatch):
    p, m, root = policy
    from usr.plugins.local_privacy_guard.helpers import agent_scope, model_guard
    target = root.parent / 'synthetic-config.json'
    monkeypatch.setattr(agent_scope, 'selected_path', lambda *args: target)
    m.write('local.json', {'pii_filter': {'languages': ['de']}, 'local_embedding': {
        'enabled': True, 'auto_configure': True, 'model': 'sentence-transformers/synthetic-local-model'}})
    protected = agent(p)
    identity = m.mapping_identity(protected)
    assert m.local_config(protected)['pii_filter']['enabled']
    a = approved(p)
    config = m.local_config(a)
    assert config['enabled'] and not config['pii_filter']['enabled']
    assert config['local_embedding']['enabled']
    monkeypatch.setattr(model_guard, 'mapping_for', lambda agent: pytest.fail('Secret-only must not read historical mappings'))
    pipeline = model_guard.PayloadFilter(a, config, True)
    assert pipeline.text('Synthetic Person alice@example.invalid') == 'Synthetic Person alice@example.invalid'
    assert pipeline.value({'tool_name': '[LPG_0123456789abcdef_PERSON_1]'})['tool_name'].startswith('[LPG_')
    pipeline.known_secrets.append('synthetic-managed-secret')
    with pytest.raises(ValueError):
        pipeline.text('synthetic-managed-secret')
    assert m.mapping_identity(protected) == identity


@pytest.mark.parametrize('name', ['completion', 'acompletion', 'responses', 'aresponses'])
def test_each_provider_attempt_rechecks_revocation(policy, monkeypatch, name):
    p, m, root = policy
    from usr.plugins.local_privacy_guard.helpers import transport_admission as t, instance
    from helpers import litellm_transport
    monkeypatch.setattr(instance, 'manager', lambda: m)
    calls = []
    def sync(**kwargs):
        calls.append(kwargs)
        return 'synthetic response'
    async def asynchronous(**kwargs):
        return sync(**kwargs)
    monkeypatch.setattr(litellm_transport, name, asynchronous if name.startswith('a') else sync)
    t.install()
    a = approved(p)
    token = t.receipt.set((a, p.effective(a)))
    try:
        if name.startswith('a'):
            asyncio.run(getattr(litellm_transport, name)(model='synthetic'))
        else:
            getattr(litellm_transport, name)(model='synthetic')
        assert calls[0]['num_retries'] == calls[0]['max_retries'] == 0
        p.revoke(p.PROFILE)
        with pytest.raises(ValueError):
            if name.startswith('a'):
                asyncio.run(getattr(litellm_transport, name)(model='synthetic'))
            else:
                getattr(litellm_transport, name)(model='synthetic')
        assert len(calls) == 1
    finally:
        t.receipt.reset(token)


def test_revocation_after_preparation_before_dispatch_has_no_provider_call(policy, monkeypatch):
    p, m, root = policy
    from usr.plugins.local_privacy_guard.helpers import transport_admission as t, instance
    monkeypatch.setattr(instance, 'manager', lambda: m)
    a = approved(p)
    token = t.receipt.set((a, p.effective(a)))
    try:
        async def delayed():
            await asyncio.sleep(0)
            p.revoke(p.PROFILE)
            await asyncio.sleep(0)
            t.admit({'model': 'synthetic'})
        with pytest.raises(ValueError):
            asyncio.run(delayed())
    finally:
        t.receipt.reset(token)
