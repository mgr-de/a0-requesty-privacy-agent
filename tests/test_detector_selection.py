"""Detector selection is independent of route selection and instance safeguards."""
import pytest
pytest.importorskip('agent')
from test_manager import setup


def test_optional_detector_configuration_survives_instance_floor(setup, monkeypatch):
    manager, scope, root = setup
    from types import SimpleNamespace
    from helpers import projects
    from usr.plugins.local_privacy_guard.helpers import agent_scope
    agent = SimpleNamespace(config=SimpleNamespace(profile='agent0'), context=object())
    monkeypatch.setattr(projects, 'get_context_project_name', lambda context: '')
    monkeypatch.setattr(agent_scope, 'selected_path', lambda *args: root / 'absent-profile.json')
    local = manager.read('local.json')
    local['pii_filter'].update(backend='nym', nym_model_dir='/tmp/synthetic-bundle', nym_threads=1)
    manager.write('local.json', local)
    config = manager.local_config(agent)
    section = config['pii_filter']
    assert section['backend'] == 'nym'
    assert section['nym_model_dir'] == '/tmp/synthetic-bundle'
    assert section['use_regex'] and section['use_ner'] and section['store_mapping']
    assert set(section['languages']) >= {'de', 'en'}
    assert manager.effective_policy()['region'] == 'eu'
