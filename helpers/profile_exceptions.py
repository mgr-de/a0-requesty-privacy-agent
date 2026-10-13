"""Operator-owned grants; chat data is a claim, never the authority.

Host filesystem administrators remain outside this boundary. Definition edits
invalidate grants deliberately; callers must explicitly grant a new generation.
"""
from copy import deepcopy
from contextvars import ContextVar
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import secrets

from . import manager

PROFILE = 'developer-privacy'
CLAIM = 'privacy_agent_chat_policy'
CONFIRM = 'ALLOW_UNMASKED_CONTEXT_AND_SUBAGENTS'
REVOKED = 'Developer permission changed. Start a new protected chat.'
deleting_chat = ContextVar('privacy_native_deleting_chat',default=None)


def require_operator():
    from flask import has_request_context, session
    from helpers import login
    expected = login.get_credentials_hash()
    if not has_request_context():
        raise ValueError('Manage profile exceptions through the native Agent Zero interface.')
    if expected and session.get('authentication') != expected:
        raise ValueError('Sign in with the configured Agent Zero login before managing profile exceptions.')


def state():
    value = manager.read('profile-exceptions.json', {'schema': 1, 'profiles': {}, 'chats': {}, 'audit': []})
    if value.get('schema') != 1 or any(not isinstance(value.get(key), dict) for key in ('profiles', 'chats')) or not isinstance(value.get('audit'), list):
        raise ValueError('Profile exception registry is invalid. Restore its local files.')
    return value


def save(value, event, profile_id='', chat_id=''):
    value['audit'] = [*value['audit'][-199:], {'event': event, 'profile_id': profile_id, 'chat_id': chat_id,
        'at': datetime.now(timezone.utc).isoformat()}]
    manager.write('profile-exceptions.json', value)


def definition(profile_id, project=''):
    from helpers import files, subagents
    available = subagents.get_available_agents_dict(project or None)
    item = available.get(profile_id)
    if item is None:
        raise ValueError('The approved profile no longer exists or is disabled.')
    expected = Path(files.get_abs_path(files.USER_DIR)) / 'agents' / profile_id
    actual = Path(item.path)
    if actual.is_symlink() or not expected.is_dir() or actual.resolve() != expected.resolve() or item.origin != ['user']:
        raise ValueError('The approved profile was replaced or shadowed by a project profile.')
    digest = hashlib.sha256()
    # Bind the actual directory incarnation, not just identical copied content.
    info = expected.stat()
    digest.update(str((info.st_dev, info.st_ino)).encode())
    for path in sorted(expected.rglob('*')):
        if path.is_symlink():
            raise ValueError('Approved profiles must not contain symbolic links.')
        if path.is_file():
            digest.update(str(path.relative_to(expected)).encode())
            digest.update(path.read_bytes())
    return {'path': str(expected.resolve()), 'fingerprint': digest.hexdigest()}


def create_profile():
    require_operator()
    manager.require_components()
    from helpers import files, subagents
    from plugins._agent_editor.helpers import editor
    with manager.LOCK:
        value = state()
        if PROFILE in value['profiles'] and (Path(files.get_abs_path(files.USER_DIR))/'agents'/PROFILE).is_dir():
            current = definition(PROFILE)
            if current != value['profiles'][PROFILE]['definition']:
                raise ValueError('Developer profile changed. Revoke its grant and review the profile before granting again.')
            return PROFILE
        if PROFILE in subagents.get_agents_dict():
            raise ValueError('Developer profile ID is already occupied. Existing profiles were not changed.')
        source = Path(files.get_abs_path('agents', 'developer'))
        target = Path(files.get_abs_path(files.USER_DIR)) / 'agents' / PROFILE
        if not source.is_dir() or source.is_symlink():
            raise ValueError('Built-in Developer profile is unavailable.')
        plan = editor.ChangePlan(profile_id=PROFILE, creating=True)
        for path in sorted(source.rglob('*')):
            if path.is_symlink():
                raise ValueError('Built-in Developer profile contains a symbolic link.')
            if path.is_file() and path.name not in {'AGENTS.md', 'agent.yaml', 'agent.json'}:
                plan.write(target / path.relative_to(source), path.read_bytes())
        plan.write(target / 'agent.yaml', 'title: Developer ohne Maskierung\ndescription: Explicit operator permission required for new unmasked chats.\n')
        editor.apply_change_plan(plan)
        value['profiles'][PROFILE] = {'definition': definition(PROFILE), 'generation': secrets.token_hex(16), 'grant': None}
        save(value, 'profile_created', PROFILE)
        return PROFILE


def grant(profile_id, confirmation):
    require_operator()
    if confirmation != CONFIRM:
        raise ValueError('Confirm that the full model context and subordinate calls may transmit personal data without masking.')
    if not manager.active():
        raise ValueError('Activate the central privacy protection first.')
    manager.require_components()
    with manager.LOCK:
        value = state()
        entry = value['profiles'].get(profile_id)
        if entry is None:
            raise ValueError('Create the managed Developer profile first.')
        current = definition(profile_id)
        if entry.get('grant') and entry['definition'] == current:
            return
        if entry.get('definition') != current:
            entry['generation'] = secrets.token_hex(16)
        entry['definition'] = current
        entry['grant'] = secrets.token_hex(16)
        save(value, 'grant', profile_id)


def revoke(profile_id, *, operator=True):
    if operator:
        require_operator()
    with manager.LOCK:
        value = state()
        entry = value['profiles'].get(profile_id)
        if entry is not None and entry.get('grant'):
            entry['grant'] = None
            save(value, 'revoke', profile_id)


def root(agent):
    from agent import AgentContext
    seen = set()
    while agent is not None:
        context = agent.context
        if context.id in seen:
            raise ValueError('Cyclic privacy owner context.')
        seen.add(context.id)
        parent_id = context.get_output_data('parent_context_id')
        if not parent_id:
            return getattr(context,'agent0',None) or agent
        parent = AgentContext.get(parent_id)
        if parent is None or parent.agent0 is None:
            raise ValueError('The parent privacy context is unavailable.')
        agent = parent.agent0
    raise ValueError('The privacy owner is unavailable.')


def effective(agent):
    owner = root(agent)
    context = owner.context
    # Native removal resets the agent before removing its context. Permit only
    # masked initialization inside this internal deletion scope; other tasks
    # keep the original revoked policy and cannot dispatch unmasked calls.
    deletion=deleting_chat.get()
    if deletion and deletion.get('active') and deletion.get('root_id',deletion['context_id'])==context.id:
        return {'mode':'masked','secret_guard':True}
    claim = context.get_data(CLAIM)
    with manager.LOCK:
        value = state()
        record = value['chats'].get(context.id)
        if record is None:
            if claim is not None:
                raise ValueError('Imported or invalid Developer policy cannot authorize a model call.')
            return {'mode': 'masked', 'secret_guard': True}
        if claim != record:
            raise ValueError(REVOKED)
        entry = value['profiles'].get(record['profile_id'])
        if not entry or not entry.get('grant') or entry['grant'] != record['grant'] or entry['generation'] != record['generation']:
            raise ValueError(REVOKED)
        from helpers import projects
        project = projects.get_context_project_name(context) or ''
        if owner.config.profile != record['profile_id'] or project != record['project']:
            raise ValueError(REVOKED)
        if definition(record['profile_id'], project) != entry['definition']:
            raise ValueError(REVOKED)
        return deepcopy(record)


def bind_new(context, profile_id):
    """Called only by the authenticated new-chat API, before any messages."""
    from helpers import projects
    with manager.LOCK:
        value = state()
        entry = value['profiles'].get(profile_id)
        project = projects.get_context_project_name(context) or ''
        if context.id in value['chats'] or context.get_data(CLAIM) is not None:
            raise ValueError('A Developer policy can only be assigned to a fresh chat.')
        if not entry or not entry.get('grant') or definition(profile_id, project) != entry['definition']:
            raise ValueError('Grant the actual Developer profile before starting its chat.')
        record = {'mode': 'unmasked', 'secret_guard': True, 'profile_id': profile_id, 'project': project,
            'generation': entry['generation'], 'grant': entry['grant'], 'receipt': secrets.token_hex(16)}
        value['chats'][context.id] = record
        save(value, 'new_chat', profile_id, context.id)
        context.set_data(CLAIM, deepcopy(record))


def remove_chat(context_id):
    with manager.LOCK:
        value = state()
        if value['chats'].pop(context_id, None) is not None:
            save(value, 'chat_removed', chat_id=context_id)


def public():
    from helpers import login
    value = state()
    profiles = []
    for key, entry in value['profiles'].items():
        try:
            valid = entry['definition'] == definition(key)
        except ValueError:
            valid = False
        profiles.append({'id': key, 'granted': bool(entry.get('grant')) and valid, 'definition_valid': valid})
    return {'login_configured': bool(login.get_credentials_hash()), 'profiles': profiles}


def require_model_transport():
    deletion=deleting_chat.get()
    if deletion and deletion.get('active'):
        raise ValueError('Model calls are not allowed during chat deletion.')
