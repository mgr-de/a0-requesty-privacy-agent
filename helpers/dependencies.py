"""Pinned archives verified before invoking Agent Zero's native ZIP installer."""
import hashlib
import json
from pathlib import Path
import tempfile
from urllib.request import Request,urlopen
import zipfile

def install_missing():
    from usr.plugins.requesty_privacy_agent.helpers.manager import components
    from plugins._plugin_installer.helpers.install import install_from_zip
    manifest=json.loads((Path(__file__).parents[1]/'dependencies.json').read_text())
    status=components()
    for name,entry in manifest.items():
        if status[name]['compatible']:continue
        if status[name]['installed']:
            raise ValueError('Update '+name+' using the native plugin manager. Existing installations will not be overwritten.')
        if not entry['url'].startswith('https://github.com/mgr-de/') or '/releases/download/' not in entry['url']:
            raise ValueError('Dependency source is invalid.')
        path=None
        try:
            with urlopen(Request(entry['url'],headers={'User-Agent':'AgentZero-Privacy-Agent'}),timeout=30) as response:
                content=response.read(50_000_001)
            if len(content)>50_000_000 or hashlib.sha256(content).hexdigest()!=entry['sha256']:
                raise ValueError('Dependency checksum does not match. No plugin was installed.')
            with tempfile.NamedTemporaryFile(suffix='.zip',delete=False) as stream:
                stream.write(content);path=Path(stream.name)
            with zipfile.ZipFile(path) as archive:
                if sum(item.file_size for item in archive.infolist())>100_000_000:
                    raise ValueError('Dependency archive is too large.')
                for item in archive.infolist():
                    relative=Path(item.filename)
                    if relative.is_absolute() or '..' in relative.parts or (item.external_attr>>16)&0o170000==0o120000:
                        raise ValueError('Dependency archive contains an unsafe path.')
                import yaml
                meta=yaml.safe_load(archive.read(name+'/plugin.yaml'))
                if meta['name']!=name or str(meta['version'])!=entry['version']:
                    raise ValueError('Dependency identity does not match its pinned release.')
            result=install_from_zip(str(path),original_filename=name+'.zip')
            if not result.get('success'):raise ValueError('Native dependency installation failed.')
        finally:
            if path is not None and path.exists():path.unlink()
