# <pep8 compliant>

import bpy  # pylint: disable=import-error

from . import dublf  # pylint: disable=import-error


class BLUIK_OpenURL(dublf.ops.OpenURL):
    bl_idname = "bluik.openurl"


class BLUIK_OT_ReportIssue(dublf.ops.DUBLF_OT_ReportIssue):
    bl_idname = "bluik.reportissue"
    addonName = __package__


class BLUIK_Preferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    layer_controllers: bpy.props.IntProperty(
        name="Layer for All controllers",
        default=0,
    )
    layer_skin: bpy.props.IntProperty(
        name="Layer for bones with influences",
        default=8,
    )
    layer_anchors: bpy.props.IntProperty(
        name="Layer for anchor bones",
        default=15,
    )
    layer_rig: bpy.props.IntProperty(
        name="Layer for bones without influences",
        default=24,
    )

    pie_menu_autorig: bpy.props.BoolProperty(
        description="Use a pie menu for the auto-rig operators. [SHIFT + R] in 'Pose' mode",
        name="Auto-rig operators. [SHIFT + R]",
        default=True,
    )
    pie_menu_armature_display: bpy.props.BoolProperty(
        description="A nice pie menu to change the armature display. [SHIFT + V] in 'Pose' or 'Edit' mode",
        name="Armature display. [SHIFT + V]",
        default=True,
    )
    pie_menu_animation: bpy.props.BoolProperty(
        description="A nice pie menu with tools for animators. [SHIFT + D] in 'Pose' mode",
        name="Animation tools. [SHIFT + D]",
        default=True,
    )

    def draw(self, context):
        layout = self.layout

        layout.operator("bluik.reportissue", text="Bug Report / Feature Request")

        layout.separator()
        layout.label(text="Layers:")
        row = layout.row(align=True)
        row.prop(self, "layer_controllers", text="Ctrl")
        row.prop(self, "layer_skin", text="Influence")
        row.prop(self, "layer_anchors", text="Anchor")
        row.prop(self, "layer_rig", text="Other")

        layout.separator()
        layout.label(text="Pie menus:")
        layout.prop(self, "pie_menu_autorig")
        layout.prop(self, "pie_menu_armature_display")
        layout.prop(self, "pie_menu_animation")


classes = (
    BLUIK_OpenURL,
    BLUIK_OT_ReportIssue,
    BLUIK_Preferences,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
