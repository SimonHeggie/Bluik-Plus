# Bluik-Plus
# Modified version of Bluik 0.7.5 by Nicolas "Duduf" Dufresne.
# Runtime and pipeline changes by Simon Heggie, 2025.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See the LICENSE file for details.

# <pep8 compliant>

bl_info = {
    "name": "Bluik-Plus",
    "blender": (3, 0, 0),
    "author": "Simon Heggie",
    "location": "Armature properties Pose Menu, View3d sidebar (N), Shader Editor sidebar (N), File > Import.",
    "version": (0, 8, 3),
    "description": (
        "Advanced control and interchange of 2D cut out layered scenes for .OCA and .OCO. "
        "Major Fork of Bluik 0.7.5 by Simon Heggie. Not an official RxLab release."
    ),
    "wiki_url": "https://bluik.rxlab.guide/",
}

import bpy  # pylint: disable=import-error


# Import "registration modules" here.
REGISTER_MODULE_NAMES = (
    "dublf",
    "preferences",
    "autorig",
    "selection_sets",
    "cam_linker",
    "ui_controls",
    "ui_layers",
    "tex_anim",
    "layers",
    "oca",
    "dopesheet_filters",
    "oco",
    "object_selector",
)

def _import_register_modules():
    import importlib

    mods = []
    pkg = __name__  #"bluik-plus"
    for name in REGISTER_MODULE_NAMES:
        mods.append(importlib.import_module("." + name, pkg))
    return mods

def _reload_modules(mods):
    import importlib

    for mod in mods:
        importlib.reload(mod)


_modules = []


def register():
    global _modules

    # If Blender hot-reloads, _modules may already exist.
    if _modules:
        _reload_modules(_modules)
    else:
        _modules = _import_register_modules()

    for mod in _modules:
        if hasattr(mod, "register"):
            mod.register()

    # Attributes
    if not hasattr(bpy.types.Armature, "duik_rig_type"):
        rig_types = [
            ("custom", "Custom", "A custom character.", "", 0),
            ("biped", "Biped", "Character with two arms, two legs and a tail.", "", 1),
            ("quadruped", "Quadruped", "Character with two arms, two legs and a tail.", "", 2),
            ("insect", "Insect", "Character with six legs.", "", 3),
            ("arachnid", "Arachnid", "Character with eight legs.", "", 4),
        ]
        bpy.types.Armature.duik_rig_type = bpy.props.EnumProperty(
            items=rig_types,
            description="The type of the character (biped, quadruped...)",
            default="biped",
            name="Type",
        )

    if not hasattr(bpy.types.Armature, "duik_layers_arm_ikfk"):
        bpy.types.Armature.duik_layers_arm_ikfk = bpy.props.BoolProperty(
            name="Arm: separate IK/FK",
            description="If checked, the UI for the arm layers will add separate buttons for IK and FK",
            default=True,
        )

    if not hasattr(bpy.types.Armature, "duik_layers_leg_ikfk"):
        bpy.types.Armature.duik_layers_leg_ikfk = bpy.props.BoolProperty(
            name="Leg: separate IK/FK",
            description="If checked, the UI for the leg layers will add separate buttons for IK and FK",
            default=True,
        )


def unregister():
    # Unregister submodules first (reverse order)
    for mod in reversed(_modules):
        if hasattr(mod, "unregister"):
            mod.unregister()

    # Attributes (guarded deletes)
    if hasattr(bpy.types.Armature, "duik_rig_type"):
        del bpy.types.Armature.duik_rig_type
    if hasattr(bpy.types.Armature, "duik_layers_leg_ikfk"):
        del bpy.types.Armature.duik_layers_leg_ikfk
    if hasattr(bpy.types.Armature, "duik_layers_arm_ikfk"):
        del bpy.types.Armature.duik_layers_arm_ikfk


if __name__ == "__main__":
    register()
