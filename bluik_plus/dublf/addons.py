# <pep8 compliant>

import bpy # pylint: disable=import-error

def is_addon_enabled( moduleName ):
    addons = bpy.context.preferences.addons
    for addon in addons:
        if addon.module == moduleName:
            return True
    return False
