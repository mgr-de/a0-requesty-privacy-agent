import hashlib
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import zipfile
import pytest

pytest.importorskip('agent')

@pytest.fixture
def installer(monkeypatch,tmp_path):
    from usr.plugins.requesty_privacy_agent.helpers import manager
    original=Path(__file__).parents[1]/'helpers/dependencies.py'
    root=tmp_path/'plugin';(root/'helpers').mkdir(parents=True)
    copy=root/'helpers/dependencies.py';copy.write_bytes(original.read_bytes())
    spec=importlib.util.spec_from_file_location('_dependency_test',copy)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    from plugins._plugin_installer.helpers import install
    calls=[]
    monkeypatch.setattr(install,'install_from_zip',lambda *a,**kw:calls.append(a) or {'success':True})
    state={'requesty':{'installed':False,'compatible':False}}
    monkeypatch.setattr(manager,'components',lambda:state)
    content=io.BytesIO()
    with zipfile.ZipFile(content,'w') as archive:
        archive.writestr('requesty/plugin.yaml','name: requesty\nversion: 0.5.0\n')
    payload=content.getvalue()
    manifest={'requesty':{'version':'0.5.0','url':'https://github.com/mgr-de/a0-requesty-privacy-guard/releases/download/v0.5.0/requesty.zip','sha256':hashlib.sha256(payload).hexdigest()}}
    (root/'dependencies.json').write_text(json.dumps(manifest))
    monkeypatch.setattr(module,'urlopen',lambda *a,**kw:io.BytesIO(payload))
    return module,root,state,calls,manifest

def test_valid_pin_uses_native_installer(installer):
    module,root,state,calls,manifest=installer;module.install_missing();assert len(calls)==1

def test_compatible_existing_plugin_is_not_downloaded_or_overwritten(installer,monkeypatch):
    module,root,state,calls,manifest=installer
    state['requesty']={'installed':True,'compatible':True}
    monkeypatch.setattr(module,'urlopen',lambda *a,**kw:pytest.fail('Existing plugin must be retained'))
    module.install_missing();assert calls==[]

def test_old_existing_plugin_requires_native_update(installer):
    module,root,state,calls,manifest=installer
    state['requesty']['installed']=True
    with pytest.raises(ValueError,match='will not be overwritten'):module.install_missing()
    assert calls==[]

def test_checksum_mismatch_stops_before_installation(installer):
    module,root,state,calls,manifest=installer
    manifest['requesty']['sha256']='0'*64;(root/'dependencies.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='checksum'):module.install_missing()
    assert calls==[]
