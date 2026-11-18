# <pep8 compliant>

import bpy # pylint: disable=import-error

def popup_view3d():
    """Creates a 3D view in a new window
    
    Return: Tuple(window, area)"""
    bpy.ops.wm.window_new()
    area = bpy.context.area
    area.type = 'VIEW_3D'
    return (bpy.context.window, area)

def popup_camera_view():
    """Creates a 3D view in a new window
    and sets it to camera view
    
    Return: Tuple(window, area)"""
    view = popup_view3d()
    bpy.context.space_data.region_3d.view_perspective = 'CAMERA'
    return view
