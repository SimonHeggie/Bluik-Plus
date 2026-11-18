import bpy

def apply_eevee_settings(mode='realtime'):
    scene = bpy.context.scene
    # Blender 5.x renamed Eevee back to BLENDER_EEVEE.
    try:
        scene.render.engine = 'BLENDER_EEVEE'
    except TypeError:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    eevee = scene.eevee

    if mode == 'realtime':
        # Realtime-optimized settings
        eevee.taa_samples = 1
        eevee.taa_render_samples = 1
        eevee.use_raytracing = False
        eevee.use_taa_reprojection = False
        eevee.use_shadow_jitter_viewport = False
        eevee.use_shadows = False
        scene.render.use_motion_blur = False
        scene.render.use_high_quality_normals = False
        eevee.shadow_pool_size = '16'
        eevee.gi_irradiance_pool_size = '16'
        scene.render.preview_pixel_size = '1'
        scene.render.compositor_device = 'GPU'
        scene.render.compositor_precision = 'AUTO'

    elif mode == 'render':
        # Render-optimized settings (but still balanced)
        eevee.taa_samples = 64
        eevee.taa_render_samples = 128
        eevee.use_raytracing = True
        eevee.use_shadows = True
        eevee.use_taa_reprojection = True
        eevee.use_shadow_jitter_viewport = True
        scene.render.use_motion_blur = True
        scene.render.use_high_quality_normals = True
        eevee.shadow_pool_size = '1024'
        eevee.gi_irradiance_pool_size = '512'
        scene.render.preview_pixel_size = '1'
        scene.render.compositor_device = 'GPU'
        scene.render.compositor_precision = 'FULL'

def apply_realtime_settings():
    print("[EEVEE OPTIMISE] Applying real-time render settings...")
    apply_eevee_settings(mode='realtime')

def apply_render_settings():
    print("[EEVEE OPTIMISE] Applying render-quality settings...")
    apply_eevee_settings(mode='render')
