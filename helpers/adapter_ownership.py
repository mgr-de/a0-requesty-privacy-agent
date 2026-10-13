"""Manager-owned adapter maintenance without optional companion imports."""
import hashlib,json
from pathlib import Path

def manage(plugin_root,owned,remove=False):
    root=Path(plugin_root).resolve();user=root.parent.parent
    target_root=user/'extensions'/'python';manifest=user/'privacy-guard-adapters'/('requesty_privacy_agent.json')
    legacy=root/'inherited-bridge.json'
    source_manifest=manifest if manifest.exists() else legacy
    if source_manifest.is_symlink() or not manifest.resolve().is_relative_to(user):
        raise ValueError('Native adapter ownership must stay in the user directory without symbolic links.')
    previous=json.loads(source_manifest.read_text()) if source_manifest.exists() else {}
    if not target_root.resolve().is_relative_to(user):raise ValueError('Native adapters must stay below the user directory.')
    planned=[]
    if not isinstance(previous,dict) or not set(previous).issubset(owned) or any(
        not isinstance(value,str) or len(value)!=64 or any(ch not in '0123456789abcdef' for ch in value)
        for value in previous.values()):
        raise ValueError('Native adapter ownership is invalid. Preserve and recover the ownership journal before updating.')
    digest=lambda value:hashlib.sha256(value.encode()).hexdigest()
    for relative,source in owned.items():
        target=(target_root/relative).resolve()
        if not target.is_relative_to(target_root.resolve()):raise ValueError('Invalid native adapter path.')
        if target.is_symlink() or (target_root/relative).is_symlink():raise ValueError('Native adapter symbolic links must be restored manually.')
        current=target.read_text(encoding='utf-8') if target.exists() else None
        if remove:
            if current is not None and previous.get(relative)==digest(current):planned.append((target,None))
        else:
            if current is not None and current!=source and previous.get(relative)!=digest(current):
                raise ValueError('A native adapter path contains another extension. Preserve it and choose a clean installation path.')
            planned.append((target,source))
    for target,source in planned:
        if source is None:target.unlink()
        else:
            target.parent.mkdir(parents=True,exist_ok=True);target.write_text(source,encoding='utf-8')
    if not remove:
        manifest.parent.mkdir(parents=True,exist_ok=True)
        manifest.write_text(json.dumps({path:digest(source) for path,source in owned.items()}),encoding='utf-8')
    else:
        retained={relative:value for relative,value in previous.items() if (target_root/relative).exists()}
        if retained:manifest.write_text(json.dumps(retained),encoding='utf-8')
        elif manifest.exists():manifest.unlink()
    if legacy.exists():legacy.unlink()
    return {'native_adapters_removed' if remove else 'native_adapters_installed':len(planned), 'retained_modified_adapters':len(retained) if remove else 0}


def integrity(user,owned):
    user=Path(user).resolve();journal=user/'privacy-guard-adapters/requesty_privacy_agent.json';target=user/'extensions/python'
    try:
        if journal.is_symlink() or not journal.resolve().is_relative_to(user):raise ValueError()
        values=json.loads(journal.read_text(encoding='utf-8'))
        expected={relative:hashlib.sha256(text.encode()).hexdigest() for relative,text in owned.items()}
        if values!=expected:return {'intact':False,'reason':'ownership_record_missing_or_outdated'}
        for relative,digest in expected.items():
            path=target/relative
            if path.is_symlink() or not path.resolve().is_relative_to(target.resolve()) or not path.is_file() or hashlib.sha256(path.read_text(encoding='utf-8').encode()).hexdigest()!=digest:
                return {'intact':False,'reason':'adapter_missing_or_changed'}
        return {'intact':True,'reason':'intact'}
    except Exception:return {'intact':False,'reason':'ownership_record_missing_or_invalid'}
