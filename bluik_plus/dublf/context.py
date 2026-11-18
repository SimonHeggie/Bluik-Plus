# <pep8 compliant>

def get_active_poseBone_or_object(context):
    """Returns the active pose bone, or the active object if
    the bone is not found"""
    obj = context.active_pose_bone
    if obj is None:
        obj = context.active_object
    return obj

def get_active_node(context):
    """Returns the active node"""
    try:
        node = context.active_node
        return node
    except AttributeError:
        return None

