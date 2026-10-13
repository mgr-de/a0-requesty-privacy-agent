import pytest
pytest.importorskip('agent')
from test_manager import setup

def test_release_requires_fixed_production_detector():
    from usr.plugins.requesty_privacy_agent.helpers.manager import MIN_VERSIONS
    assert MIN_VERSIONS['local_privacy_guard'] == (1,7,4)

def test_legacy_evaluation_marker_preserves_floor_and_saved_settings(setup,monkeypatch):
    from types import SimpleNamespace
    from helpers import projects
    from usr.plugins.local_privacy_guard.helpers import agent_scope,pii_detector
    manager,scope,root = setup
    local = manager.read('local.json')
    local['pii_filter']['backend'] = 'presidio'
    manager.write('local.json',local)
    before = (root/'privacy-agent/local.json').read_bytes()
    monkeypatch.setattr(projects,'get_context_project_name',lambda context:'')
    monkeypatch.setattr(agent_scope,'selected_path',lambda *args:root/'absent.json')
    config = manager.local_config(SimpleNamespace(context=object(),config=SimpleNamespace(profile='agent0')))
    scanner = pii_detector.PIIFilter(config['pii_filter'])
    assert scanner.backend == 'local' and scanner.use_regex and scanner.use_ner
    assert set(scanner.ner_languages) >= {'de','en'}
    assert (root/'privacy-agent/local.json').read_bytes() == before
