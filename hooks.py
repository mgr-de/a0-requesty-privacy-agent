from usr.plugins.requesty_privacy_agent.helpers import manager

def install(**kwargs):
    # Installation alone never activates an installation-wide policy.
    if manager.active():
        from usr.plugins.requesty_privacy_agent.helpers.adapters import install as install_adapters
        install_adapters()
        manager.install_legacy_bridge()
        manager.require_components()
    return {'active':manager.active(),'components':manager.components()}

def pre_update(**kwargs):
    return {'active':manager.active()}

def uninstall(**kwargs):
    if manager.active():raise ValueError('Deactivate Privacy Agent centrally before uninstalling it.')
    manager.remove_legacy_bridge()
    from usr.plugins.requesty_privacy_agent.helpers.adapters import install
    result=install(remove=True)
    return {**result,'note':'Common configuration and keys preserved outside the plugin directory; modified unowned adapters are retained.'}
