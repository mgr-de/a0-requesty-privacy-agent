"""Small persistent native adapters, using the companion ownership protocol."""
from pathlib import Path

def sources():
    header='from helpers.extension import Extension\n\nclass PrivacyAgentAdapter(Extension):\n'
    # Active marker is outside the plugin directory. A missing manager must
    # raise, even if someone hides its plugin discovery with a profile toggle.
    # Embed the small protocol so retained adapters fail closed even if the
    # Manager directory was removed. No companion import is needed here.
    from . import activation_state as protocol
    prelude=Path(protocol.__file__).read_text()+"\nfrom helpers import files\nstate=activation_state(files.get_abs_path(files.USER_DIR))\nif state!='active':return\ntry:\n    from usr.plugins.requesty_privacy_agent.helpers import manager\nexcept ImportError:raise ValueError('Restore Privacy Agent or deactivate it centrally.') from None\n"
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
    # The authenticated Manager settings panel remains readable for recovery;
    # it is not a model configuration and conveys no transport authorization.
    key='_functions/helpers/plugins/get_plugin_config/end/_89_privacy_agent_config.py'
    guard="        args=(data or {}).get('args',())\n        kwargs=(data or {}).get('kwargs',{})\n        name=args[0] if args else kwargs.get('plugin_name')\n        if name=='requesty_privacy_agent':return\n"
    files[key]=files[key].replace('        """Strict central activation protocol',guard+'        """Strict central activation protocol',1)
    for method in ('unified_call','unified_turn'):
        files[f'_functions/models/LiteLLMChatWrapper/{method}/start/_89_privacy_agent_call.py']=body(f"manager.enforce_call(data,'{method}')")
        files[f'_functions/models/LiteLLMChatWrapper/{method}/end/_98_privacy_agent_output.py']=body('await manager.enforce_output(data)',True)
    return files

def install(remove=False):
    from .adapter_ownership import manage
    return manage(Path(__file__).resolve().parents[1],sources(),remove=remove)


def integrity(user):
    from .adapter_ownership import integrity as check
    return check(Path(user),sources())
