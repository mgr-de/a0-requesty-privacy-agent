"""Damaged activation and independent ownership recovery use synthetic state."""
import json
from pathlib import Path
import pytest
from usr.plugins.requesty_privacy_agent.helpers.activation_state import activation_state
from usr.plugins.requesty_privacy_agent.helpers import adapters,adapter_ownership

@pytest.mark.parametrize('value',[{}, {'active':'true'}, {'active':'false'}, {'active':1}, {'active':0}, {'active':None}, [], True])
def test_invalid_activation_is_never_implicit_deactivation(tmp_path,value):
    folder=tmp_path/'privacy-agent';folder.mkdir();(folder/'active.json').write_text(json.dumps(value))
    with pytest.raises(ValueError):activation_state(tmp_path)

@pytest.mark.parametrize('evidence',['activation-record','journal'])
def test_lost_state_blocks_previously_managed_installation(tmp_path,evidence):
    if evidence=='activation-record':
        p=tmp_path/'privacy-agent/activation-record.json';p.parent.mkdir();p.write_text('{"schema":1,"managed":true}')
    else:
        p=tmp_path/'privacy-guard-adapters/requesty_privacy_agent.json';p.parent.mkdir();p.write_text('{}')
    with pytest.raises(ValueError,match='missing from a managed'):activation_state(tmp_path)

def test_new_inactive_and_active_states_are_distinct(tmp_path):
    assert activation_state(tmp_path)=='unconfigured'
    folder=tmp_path/'privacy-agent';folder.mkdir()
    for enabled,expected in [(False,'inactive'),(True,'active')]:
        (folder/'active.json').write_text(json.dumps({'active':enabled}))
        assert activation_state(tmp_path)==expected

def test_ownership_cleanup_needs_no_companion_and_preserves_modified_file(tmp_path):
    root=tmp_path/'plugins/requesty_privacy_agent';root.mkdir(parents=True)
    owned=adapters.sources();adapter_ownership.manage(root,owned)
    assert adapters.integrity(tmp_path)['intact']
    relative=next(iter(owned));path=tmp_path/'extensions/python'/relative
    path.write_text(path.read_text()+'# local modification retained\n')
    result=adapter_ownership.manage(root,owned,remove=True)
    assert result['native_adapters_removed']==len(owned)-1
    assert result['retained_modified_adapters']==1
    assert path.exists()
    journal=tmp_path/'privacy-guard-adapters/requesty_privacy_agent.json'
    assert set(json.loads(journal.read_text()))=={relative}
    with pytest.raises(ValueError,match='another extension'):adapter_ownership.manage(root,owned)

def test_missing_owned_file_can_be_repaired_but_active_integrity_fails(tmp_path):
    root=tmp_path/'plugins/requesty_privacy_agent';root.mkdir(parents=True)
    owned=adapters.sources();adapter_ownership.manage(root,owned)
    path=tmp_path/'extensions/python'/next(iter(owned));path.unlink()
    assert not adapters.integrity(tmp_path)['intact']
    adapter_ownership.manage(root,owned)
    assert adapters.integrity(tmp_path)['intact']

def test_foreign_journal_paths_cannot_delete_outside_files(tmp_path):
    root=tmp_path/'plugins/requesty_privacy_agent';root.mkdir(parents=True)
    victim=tmp_path/'foreign.txt';victim.write_text('synthetic unchanged')
    journal=tmp_path/'privacy-guard-adapters/requesty_privacy_agent.json';journal.parent.mkdir()
    journal.write_text(json.dumps({'../../foreign.txt':'0'*64}))
    with pytest.raises(ValueError):adapter_ownership.manage(root,adapters.sources(),remove=True)
    assert victim.read_text()=='synthetic unchanged'

def test_uninstall_cleans_owned_adapters_when_companions_are_missing(tmp_path,monkeypatch):
    from usr.plugins.requesty_privacy_agent import hooks
    from usr.plugins.requesty_privacy_agent.helpers import manager
    root=tmp_path/'plugins/requesty_privacy_agent';root.mkdir(parents=True)
    adapter_ownership.manage(root,adapters.sources())
    monkeypatch.setattr(manager,'active',lambda:False)
    monkeypatch.setattr(manager,'remove_legacy_bridge',lambda:None)
    monkeypatch.setattr(manager,'components',lambda:(_ for _ in ()).throw(AssertionError('companions must not be required')))
    monkeypatch.setattr(adapters,'install',lambda remove=False:adapter_ownership.manage(root,adapters.sources(),remove=remove))
    result=hooks.uninstall()
    assert result['native_adapters_removed']==len(adapters.sources())
    assert not (tmp_path/'privacy-guard-adapters/requesty_privacy_agent.json').exists()


def test_retained_adapter_blocks_invalid_marker_before_manager_import(tmp_path,monkeypatch):
    from helpers import files
    folder=tmp_path/'privacy-agent';folder.mkdir();(folder/'active.json').write_text('{"active":"true"}')
    monkeypatch.setattr(files,'get_abs_path',lambda *args:str(tmp_path))
    source=adapters.sources()['_functions/models/LiteLLMChatWrapper/unified_call/start/_89_privacy_agent_call.py']
    namespace={};exec(compile(source,'synthetic-owned-adapter','exec'),namespace)
    with pytest.raises(ValueError,match='boolean active'):
        namespace['PrivacyAgentAdapter'](None).execute(data={})


def test_missing_manager_adapter_blocks_enforcement_before_transport(tmp_path,monkeypatch):
    from usr.plugins.requesty_privacy_agent.helpers import manager
    from helpers import files
    folder=tmp_path/'privacy-agent';folder.mkdir();(folder/'active.json').write_text('{"active":true}')
    monkeypatch.setattr(files,'get_abs_path',lambda *args:str(tmp_path))
    monkeypatch.setattr(manager,'components',lambda:{'synthetic':{'compatible':True}})
    with pytest.raises(ValueError,match='adapters are incomplete'):manager.require_components()


def test_broken_state_diagnostics_bypass_only_read_only_http_boundary(tmp_path,monkeypatch):
    import asyncio
    from flask import Flask,request
    from helpers import files
    from helpers.api import ApiHandler
    from usr.plugins.requesty_privacy_agent.helpers import manager,preset_bridge,native_presets
    folder=tmp_path/'privacy-agent';folder.mkdir();(folder/'active.json').write_text('{}')
    monkeypatch.setattr(files,'get_abs_path',lambda *args:str(tmp_path))
    monkeypatch.setattr(manager,'components',lambda:{'synthetic':{'compatible':True}})
    monkeypatch.setattr(native_presets,'enabled',lambda:(_ for _ in ()).throw(AssertionError('read-only diagnostics must not authorize native models')))
    class ReadOnlyDiagnostics(ApiHandler):
        async def process(self,input,request):return manager.public_status()
    app=Flask(__name__)
    preset_bridge.install()
    try:
        with app.test_request_context('/api/plugins/requesty_privacy_agent/setup',json={'action':'status'}):
            response=asyncio.run(ReadOnlyDiagnostics(None,None).handle_request(request))
        assert response.status_code==200
        assert response.get_json()['diagnostics']['activation_state']=='broken'
    finally:preset_bridge.remove()
