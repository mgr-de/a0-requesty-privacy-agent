from usr.plugins.requesty_privacy_agent.helpers import manager

def install(**kwargs):
    # Installation alone never activates an installation-wide policy.
    return {'active':manager.active(),'components':manager.components()}

def pre_update(**kwargs):
    return {'active':manager.active()}

def uninstall(**kwargs):
    if manager.active():raise ValueError('Deactivate Privacy Agent centrally before uninstalling it.')
    manager.remove_legacy_bridge()
    if all(v['compatible'] for v in manager.components().values()):
        from usr.plugins.requesty_privacy_agent.helpers.adapters import install
        install(remove=True)
    return {'note':'Common configuration and keys preserved outside the plugin directory.'}
