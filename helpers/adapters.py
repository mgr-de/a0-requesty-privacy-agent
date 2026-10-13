"""Small persistent native adapters, using the companion ownership protocol."""
import importlib.util
from pathlib import Path

def sources():
    header='from helpers.extension import Extension\n\nclass PrivacyAgentAdapter(Extension):\n'
    # Active marker is outside the plugin directory. A missing manager must
    # raise, even if someone hides its plugin discovery with a profile toggle.
    prelude="from pathlib import Path\nimport json\nfrom helpers import files\nmarker=Path(files.get_abs_path(files.USER_DIR))/'privacy-agent'/'active.json'\nif not marker.exists():return\nif marker.is_symlink():raise ValueError('Unsafe Privacy Agent activation.')\ntry:state=json.loads(marker.read_text())\nexcept Exception:raise ValueError('Privacy Agent activation is unreadable.') from None\nif state.get('active') is not True:return\ntry:\n    from usr.plugins.requesty_privacy_agent.helpers import manager\nexcept ImportError:raise ValueError('Restore Privacy Agent or deactivate it centrally.') from None\n"
    def body(code,asynchronous=False):
        signature='    async def execute(self,data=None,**kwargs):\n' if asynchronous else '    def execute(self,data=None,**kwargs):\n'
        return header+signature+''.join('        '+line+'\n' for line in (prelude+code).splitlines())
    files={
        '_functions/initialize/initialize_job_loop/start/_00_privacy_agent_presets.py':body("manager.install_legacy_bridge()\nif manager.read('setup.json',{}).get('native_presets'):\n    from usr.plugins.requesty_privacy_agent.helpers import preset_bridge\n    preset_bridge.install()"),
        '_functions/models/get_chat_model/end/_00_privacy_agent_legacy.py':body('manager.install_legacy_bridge()'),
        '_functions/helpers/plugins/get_plugin_config/end/_89_privacy_agent_config.py':body('manager.apply_model_config(data,self.agent)'),
        '_functions/helpers/plugins/delete_plugin/start/_00_privacy_agent_required.py':body("name=data['args'][0] if data.get('args') else data.get('kwargs',{}).get('plugin_name')\nif name in {'requesty','local_privacy_guard','requesty_privacy_agent'}:raise ValueError('Deactivate Privacy Agent centrally before removing required plugins.')"),
        '_functions/helpers/plugins/uninstall_plugin/start/_00_privacy_agent_required.py':body("name=data['args'][0] if data.get('args') else data.get('kwargs',{}).get('plugin_name')\nif name in {'requesty','local_privacy_guard','requesty_privacy_agent'}:raise ValueError('Deactivate Privacy Agent centrally before removing required plugins.')"),
        '_functions/helpers/plugins/toggle_plugin/start/_00_privacy_agent_required.py':body("args=data.get('args',())\nkwargs=data.get('kwargs',{})\nname=args[0] if args else kwargs.get('plugin_name')\nenabled=args[1] if len(args)>1 else kwargs.get('enabled')\nif name in {'requesty','local_privacy_guard','requesty_privacy_agent'} and enabled is False:raise ValueError('Deactivate A0 Privacy centrally before disabling required plugins.')"),
        'agent_init/_00_privacy_agent_identity.py':body("manager.mapping_identity(self.agent)"),
        '_functions/agent/AgentContext/reset/start/_00_privacy_agent_deletion.py':body("from flask import has_request_context,request\nif has_request_context() and request.path.rstrip('/').endswith('/chat_remove'):\n    from usr.plugins.requesty_privacy_agent.helpers import profile_exceptions as policy\n    context=data['args'][0]\n    agent=getattr(context,'agent0',None)\n    scope={'context_id':context.id,'root_id':policy.root(agent).context.id if agent else context.id,'active':True}\n    data['_privacy_deletion_scope']=scope\n    data['_privacy_deletion_token']=policy.deleting_chat.set(scope)"),
        '_functions/agent/AgentContext/reset/end/_00_privacy_agent_deletion.py':body("scope=data.pop('_privacy_deletion_scope',None)\nif scope is not None:\n    scope['active']=False\n    from usr.plugins.requesty_privacy_agent.helpers import profile_exceptions as policy\n    policy.deleting_chat.reset(data.pop('_privacy_deletion_token'))"),
        '_functions/plugins/_agent_editor/helpers/editor/apply_change_plan/start/_00_privacy_agent_profile.py':body("plan=data['args'][0] if data.get('args') else data.get('kwargs',{}).get('plan')\nif plan and not plan.creating:\n    from usr.plugins.requesty_privacy_agent.helpers.profile_exceptions import revoke\n    revoke(plan.profile_id,operator=False)"),
        '_functions/helpers/subagents/delete_agent_data/start/_00_privacy_agent_profile.py':body("profile=data['args'][0] if data.get('args') else data.get('kwargs',{}).get('name')\nfrom usr.plugins.requesty_privacy_agent.helpers.profile_exceptions import revoke\nrevoke(profile,operator=False)"),
        '_functions/agent/AgentContext/remove/end/_00_privacy_agent_chat.py':body("from flask import has_request_context,request\nif has_request_context() and request.path.rstrip('/').endswith('/chat_remove'):\n    from usr.plugins.requesty_privacy_agent.helpers.profile_exceptions import remove_chat\n    chat=data['args'][0] if data.get('args') else data.get('kwargs',{}).get('id')\n    remove_chat(chat)"),
    }
    for method in ('unified_call','unified_turn'):
        files[f'_functions/models/LiteLLMChatWrapper/{method}/start/_89_privacy_agent_call.py']=body(f"manager.enforce_call(data,'{method}')")
        files[f'_functions/models/LiteLLMChatWrapper/{method}/end/_98_privacy_agent_output.py']=body('await manager.enforce_output(data)',True)
    return files

def install(remove=False):
    # Reuse file ownership/preflight, not a second installer implementation.
    from usr.plugins.requesty.helpers import inherited_bridge
    spec=importlib.util.spec_from_file_location('_privacy_agent_adapter_ownership',inherited_bridge.__file__)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.PLUGIN='requesty_privacy_agent';module.sources=sources
    return module.manage(Path(__file__).resolve().parents[1],remove=remove)
