import asyncio
from helpers.api import ApiHandler
from usr.plugins.requesty_privacy_agent.helpers import manager

class Setup(ApiHandler):
    async def process(self,input,request):
        try:
            command=input.get('action','status')
            if command in {'create-developer-profile','grant','revoke','repair_adapters','cleanup_adapters'}:
                # Flask session context is verified before entering the worker.
                from usr.plugins.requesty_privacy_agent.helpers.profile_exceptions import require_operator
                require_operator()
            def action():
                with manager.LOCK:
                    command=input.get('action','status')
                    if command=='key':manager.save_key(input.get('key'))
                    elif command=='catalog':return {'ok':True,'models':manager.model_catalog()}
                    elif command=='configure':manager.configure(input.get('configuration'))
                    elif command=='migration_preview':
                        from usr.plugins.requesty_privacy_agent.helpers.native_presets import preview
                        return {'ok':True,'preview':preview(input.get('overrides'),input.get('preserve_current',True))}
                    elif command=='migration_apply':
                        from usr.plugins.requesty_privacy_agent.helpers.native_presets import apply
                        receipt=apply(input.get('fingerprint'),input.get('overrides'),input.get('preserve_current',True),input.get('languages'))
                        return {'ok':True,'receipt':receipt,**manager.public_status()}
                    elif command=='migration_restore':
                        from usr.plugins.requesty_privacy_agent.helpers.native_presets import restore
                        return {'ok':True,**restore(input.get('backup_id'))}
                    elif command=='prepare_local':manager.prepare_local(input.get('languages'))
                    elif command=='activate':
                        if input.get('confirm_all_profiles') is not True:raise ValueError('Confirm that all existing and future profiles will be affected.')
                        manager.activate()
                    elif command=='deactivate':manager.deactivate(input.get('confirmation'))
                    elif command=='repair_adapters':manager.repair_adapters()
                    elif command=='cleanup_adapters':manager.cleanup_adapters(input.get('confirmation'))
                    elif command=='account':
                        from usr.plugins.requesty.helpers.account import confirmation
                        manager.write('account.json',confirmation(input.get('settings')))
                    elif command=='install_dependencies':
                        from usr.plugins.requesty_privacy_agent.helpers.dependencies import install_missing
                        install_missing()
                    elif command in {'create-developer-profile','grant','revoke'}:
                        from usr.plugins.requesty_privacy_agent.helpers import profile_exceptions as policy
                        if command=='create-developer-profile':policy.create_profile()
                        elif command=='grant':policy.grant(input.get('profile_id'),input.get('confirmation'))
                        else:policy.revoke(input.get('profile_id'))
                    elif command in {'list','get'}:
                        from usr.plugins.requesty_privacy_agent.helpers.profile_exceptions import public
                        result=public()
                        if command=='get':
                            result['profiles']=[p for p in result['profiles'] if p['id']==input.get('profile_id')]
                        return {'ok':True,'profile_exceptions':result}
                    elif command!='status':raise ValueError('Unknown setup action.')
                    return {'ok':True,**manager.public_status()}
            return await asyncio.to_thread(action)
        except Exception as error:
            # Network/library exceptions may contain keys or response payloads.
            # Only explicitly authored validation errors are safe to display.
            message=str(error) if isinstance(error,ValueError) else 'Setup failed. Check installed components and the Requesty connection; no protection was activated.'
            return {'ok':False,'error':message}
