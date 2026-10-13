"""Owned reversible bridges for native lifecycle APIs without extension hooks."""
from functools import wraps
from . import manager

_bridges = []


def block(context_id):
    from . import profile_exceptions as policy
    with manager.LOCK:
        value=policy.state()
        entry=value['chats'].get(context_id)
        if entry and not entry.get('blocked'):
            entry['blocked']=True
            policy.save(value,'chat_identity_changed',entry['profile_id'],context_id)


def install():
    from api.agent_profile_set import SetAgentProfile
    from api.chat_remove import RemoveChat
    from helpers import projects,subagents
    from plugins._agent_editor.helpers import editor
    from . import profile_exceptions as policy
    def attach(owner,name,factory):
        previous=getattr(owner,name)
        if getattr(previous,'_privacy_exception_lifecycle',False):return
        proxy=factory(previous)
        proxy._privacy_exception_lifecycle=True
        setattr(owner,name,proxy)
        _bridges.append((owner,name,previous,proxy))
    def profile_change(previous):
        @wraps(previous)
        async def changed(handler,input,request):
            result=await previous(handler,input,request)
            if manager.active() and isinstance(result,dict) and result.get('ok'):
                record=policy.state()['chats'].get(input.get('context_id'))
                if record and input.get('agent_profile')!=record['profile_id']:
                    block(input['context_id'])
            return result
        return changed
    attach(SetAgentProfile,'process',profile_change)
    def chat_remove(previous):
        @wraps(previous)
        async def removed(handler,input,request):
            scope={'context_id':input.get('context'),'active':True}
            token=policy.deleting_chat.set(scope)
            try:return await previous(handler,input,request)
            finally:
                scope['active']=False
                policy.deleting_chat.reset(token)
        return removed
    attach(RemoveChat,'process',chat_remove)
    def project_change(previous):
        @wraps(previous)
        def changed(*args,**kwargs):
            result=previous(*args,**kwargs)
            context_id=args[0] if args else kwargs.get('context_id',kwargs.get('ctxid'))
            if manager.active():
                from agent import AgentContext
                context=AgentContext.get(context_id)
                record=policy.state()['chats'].get(context_id)
                if record and context and (projects.get_context_project_name(context) or '')!=record['project']:
                    block(context_id)
            return result
        return changed
    attach(projects,'activate_project',project_change)
    attach(projects,'deactivate_project',project_change)
    def profile_edit(previous):
        @wraps(previous)
        def changed(plan,*args,**kwargs):
            if manager.active() and not plan.creating:
                policy.revoke(plan.profile_id,operator=False)
            return previous(plan,*args,**kwargs)
        return changed
    attach(editor,'apply_change_plan',profile_edit)
    def profile_delete(previous):
        @wraps(previous)
        def changed(name,*args,**kwargs):
            if manager.active():policy.revoke(name,operator=False)
            return previous(name,*args,**kwargs)
        return changed
    attach(subagents,'delete_agent_data',profile_delete)


def remove():
    for owner,name,previous,proxy in reversed(_bridges):
        if getattr(owner,name) is proxy:setattr(owner,name,previous)
    _bridges.clear()
