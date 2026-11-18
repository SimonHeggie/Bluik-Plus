# <pep8 compliant>

import bpy # pylint: disable=import-error

# Shape Keys tools and methods

def get_key(context):
    """Gets or creates (with a single basis key) the key from the active object"""
    key = context.active_object.data.shape_keys
    if key is not None: return key
    c = context.copy()
    bpy.ops.object.shape_key_add(c, from_mix=False)
    return context.active_object.data.shape_keys
