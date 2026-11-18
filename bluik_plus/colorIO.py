import bpy

def apply_color_management(mode='automatic'):
    """Apply color management for 'automatic' (Khronos PBR) or leave as 'default'."""
    scene = bpy.context.scene

    if mode == 'automatic':
        scene.display_settings.display_device = 'sRGB'
        scene.view_settings.view_transform = 'Khronos PBR Neutral'
        scene.view_settings.look = 'None'
        scene.view_settings.exposure = 0
        scene.view_settings.gamma = 1
        scene.sequencer_colorspace_settings.name = 'Khronos PBR Neutral sRGB'
        print("[COLOR I/O] Applied Khronos PBR Neutral color management.")

    elif mode == 'default':
        print("[COLOR I/O] Default mode: No changes applied to color management.")

    else:
        print(f"[COLOR I/O] Unknown mode: {mode}")
