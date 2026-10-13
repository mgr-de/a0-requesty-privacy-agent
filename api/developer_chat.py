"""Create a fresh operator-approved root chat atomically before use."""
from helpers.api import ApiHandler
from usr.plugins.requesty_privacy_agent.helpers import manager, profile_exceptions as policy


class DeveloperChat(ApiHandler):
    async def process(self, input, request):
        try:
            policy.require_operator()
            manager.require_components()
            if not manager.active():
                raise ValueError('Central privacy protection must remain active.')
            from agent import AgentContext
            from helpers import guids, persist_chat, projects, history
            from initialize import initialize_agent
            context_id = guids.generate_id()
            project=input.get('project_name','')
            if not isinstance(project,str):raise ValueError('Choose one valid project.')
            if project:
                projects.validate_project_name(project)
                projects.load_basic_project_data(project)
            # No await or publication between construction and authoritative
            # binding. Other API context creation and model admission wait.
            with self.thread_lock, manager.LOCK:
                try:
                    config=initialize_agent(override_settings={'agent_profile':policy.PROFILE})
                    context=AgentContext(config=config,id=context_id)
                    if project:projects.activate_project(context_id,project,mark_dirty=False)
                    context.config=config;context.agent0.config=config
                    # Discard only the freshly generated native greeting.
                    # No user history, inherited preset or imported data exists.
                    context.agent0.history=history.History(context.agent0)
                    context.agent0.last_user_message=None
                    context.log.reset()
                    policy.bind_new(context,policy.PROFILE)
                    persist_chat.save_tmp_chat(context)
                except Exception:
                    policy.remove_chat(context_id)
                    AgentContext.remove(context_id)
                    persist_chat.remove_chat(context_id)
                    raise
            from helpers.state_monitor_integration import mark_dirty_all
            mark_dirty_all(reason='privacy_developer_chat_created')
            return {'ok': True, 'ctxid': context_id, 'mode': 'unmasked', 'secret_guard': True}
        except Exception as error:
            return {'ok': False, 'error': str(error) if isinstance(error, ValueError) else 'Developer chat could not be created.'}
