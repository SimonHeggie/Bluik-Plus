# <pep8 compliant>

# OCA Import

from __future__ import annotations

import math
import os
import re
from typing import List, Optional, Tuple

import bpy  # pylint: disable=import-error
from bpy_extras.object_utils import AddObjectHelper  # pylint: disable=import-error
from mathutils import Vector  # pylint: disable=import-error

from . import dublf
from . import layers

from .blend_modes import (
    decide_target,
    ensure_material_blend_wiring,
    probe_material_outputs,
    set_blend_group_output,
)


DEBUG_VERBOSE = True


def _norm_key(s: str) -> str:
    return " ".join((s or "").split())


def _first_nonblank_frame(frames: list) -> dict:
    """
    Return first frame that looks like a real image frame.
    If none exist, return frames[0] or {}.
    """
    if not frames:
        return {}
    for fr in frames:
        name = (fr.get("name") or "").strip()
        fn = (fr.get("fileName") or "").strip()
        w = float(fr.get("width") or 0.0)
        h = float(fr.get("height") or 0.0)
        if name and name != "_blank" and fn and w > 0.0 and h > 0.0:
            return fr
    return frames[0] or {}


def _get_render_scene(context, scene_root):
    """
    Resolve the actual bpy.types.Scene to write output resolution onto.

    layers.create_scene() may return a Duik container (often a Collection), not a Scene.
    """
    if isinstance(scene_root, bpy.types.Scene):
        return scene_root

    if isinstance(scene_root, bpy.types.Collection):
        users = getattr(scene_root, "users_scene", None)
        if users:
            return users[0]

    return context.scene


def _set_render_resolution(scene, width, height, percentage=100):
    """Set Blender output render resolution on a real bpy.types.Scene."""
    r = scene.render
    r.resolution_x = int(width)
    r.resolution_y = int(height)
    r.resolution_percentage = int(percentage)
    r.pixel_aspect_x = 1.0
    r.pixel_aspect_y = 1.0


def _fit_duik_camera(scene_root, _render_scene, doc_w, doc_h, px_to_unit=100.0):
    """
    Apply OCA document sizing to Duik scene metadata and fit the Duik camera.

    scene_root: the Duik container returned by layers.create_scene (often a Collection)
    """
    if not hasattr(scene_root, "duik_scene"):
        return

    duik_scene = scene_root.duik_scene
    duik_scene.width = int(doc_w)
    duik_scene.height = int(doc_h)

    cam = getattr(duik_scene, "camera", None)
    if not cam or not getattr(cam, "data", None):
        return

    cam_data = cam.data
    if getattr(cam_data, "type", None) != "ORTHO" or not hasattr(cam_data, "ortho_scale"):
        return

    doc_w_u = float(doc_w) / float(px_to_unit)
    doc_h_u = float(doc_h) / float(px_to_unit)

    cam_data.ortho_scale = max(doc_w_u, doc_h_u)


def _action_curves(obj):
    ad=obj.animation_data
    if not ad or not ad.action:return []
    if hasattr(ad.action,'fcurves'):return list(ad.action.fcurves)
    from bpy_extras.anim_utils import animdata_get_channelbag_for_assigned_slot
    bag=animdata_get_channelbag_for_assigned_slot(ad)
    return list(bag.fcurves) if bag else []


def _set_fcurves_constant(action, data_paths, owner=None):
    curves=_action_curves(owner) if owner else getattr(action,'fcurves',[])
    for curve in curves:
        if curve.data_path in data_paths:
            for key in curve.keyframe_points:key.interpolation='CONSTANT'


def _is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _get_layer_rotation_payload(oca_layer: dict) -> Tuple[object, float]:
    """
    Prefer per-frame rotation/cameraHeight if present, else fall back to layer-level.

    Returns: (rotation_payload, camera_height)
    rotation_payload may be scalar or [x,y,z] list, or None.
    """
    frames = oca_layer.get("frames") or []
    frame0 = _first_nonblank_frame(frames) if frames else {}
    rot = None
    cam_h = None

    if frame0:
        rot = frame0.get("rotation", None)
        cam_h = frame0.get("cameraHeight", None)

    if rot is None:
        rot = oca_layer.get("rotation", None)
    if cam_h is None:
        cam_h = oca_layer.get("cameraHeight", None)

    try:
        cam_h_f = float(cam_h) if cam_h is not None else 20000.0
    except Exception:
        cam_h_f = 20000.0

    return rot, cam_h_f


def _parse_oca_rotation_value(value):
    from .oca_transforms import rotation
    return rotation(value)

def _apply_rotation_keys(obj, oca_layer, frame_base=0):
    """
    Apply per-frame rotation onto obj.rotation_euler and key it.

    Supports:
      - scalar degrees (legacy): animates Blender Y
      - [x,y,z] degrees: direct Blender XYZ Euler additions (v0.8.2 convention)

    Notes:
      - We key the full rotation_euler so it works for vector rotation.
      - The base plane orientation (X=90°) is included here.
    """
    frames = oca_layer.get("frames") or []
    if len(frames) < 2:
        return

    base_rot_payload, _cam_h = _get_layer_rotation_payload(oca_layer)
    base_x_add, base_y_add, base_z_add = _parse_oca_rotation_value(base_rot_payload)

    needs_keys = False
    for fr in frames:
        if "rotation" not in fr:
            continue
        fr_payload = fr.get("rotation", None)
        x_add, y_add, z_add = _parse_oca_rotation_value(fr_payload)
        if (x_add != base_x_add) or (y_add != base_y_add) or (z_add != base_z_add):
            needs_keys = True
            break

    if not needs_keys:
        return

    if obj.animation_data is None:
        obj.animation_data_create()
    if obj.animation_data.action is None:
        obj.animation_data.action = bpy.data.actions.new(name=f"{obj.name}_OCA_Rotation")

    action = obj.animation_data.action

    base_x = math.radians(90.0)

    for fr in frames:
        fr_num = int(fr.get("frameNumber", 0))
        fr_payload = fr.get("rotation", base_rot_payload)

        x_add, y_add, z_add = _parse_oca_rotation_value(fr_payload)

        bpy.context.scene.frame_set(frame_base + fr_num)

        obj.rotation_euler.x = base_x + x_add
        obj.rotation_euler.y = y_add
        obj.rotation_euler.z = z_add

        obj.keyframe_insert(data_path="rotation_euler")

    _set_fcurves_constant(action, {"rotation_euler"}, owner=obj)



def _apply_cropped_frame_transform_keys(
    obj,
    oca_layer,
    doc_w,
    doc_h,
    px_to_unit=100.0,
    frame_base=0,
):
    """
    Fix cropped or trimmed animated frames by keying object location and scale per frame.

    The plane is later rotated 90 degrees on X (see apply_common_transformations()).
    A Blender plane is in XY by default; after X rotation, the vertical dimension
    corresponds to obj.scale.y, not obj.scale.z. We key scale.x and scale.y and leave
    scale.z unchanged.
    """
    frames = oca_layer.get("frames") or []
    if not frames:
        return

    base_w = abs(float(oca_layer.get("width") or 0.0))
    base_h = abs(float(oca_layer.get("height") or 0.0))
    if base_w <= 0.0 or base_h <= 0.0:
        return

    base_pos = oca_layer.get("position")

    needs_keys = False
    for fr in frames:
        fw = float(fr.get("width", base_w))
        fh = float(fr.get("height", base_h))
        if fw != base_w or fh != base_h:
            needs_keys = True
            break
        if fr.get("position") != base_pos:
            needs_keys = True
            break

    if not needs_keys:
        return

    if obj.animation_data is None:
        obj.animation_data_create()
    if obj.animation_data.action is None:
        obj.animation_data.action = bpy.data.actions.new(name=f"{obj.name}_OCA_CropFix")

    action = obj.animation_data.action

    keep_y = float(obj.location.y)
    keep_sz = float(obj.scale.z) if obj.scale else 1.0

    for fr in frames:
        fr_num = int(fr.get("frameNumber", 0))
        fr_pos = fr.get("position") or base_pos or [float(doc_w) / 2.0, float(doc_h) / 2.0]

        fw = float(fr.get("width", base_w))
        fh = float(fr.get("height", base_h))

        sx = fw / base_w
        sy = fh / base_h

        x = (float(fr_pos[0]) - (float(doc_w) / 2.0)) / float(px_to_unit)
        z = ((float(doc_h) / 2.0) - float(fr_pos[1])) / float(px_to_unit)

        bpy.context.scene.frame_set(frame_base + fr_num)

        obj.location.x = x
        obj.location.y = keep_y
        obj.location.z = z

        obj.scale.x = sx
        obj.scale.y = sy
        obj.scale.z = keep_sz

        obj.keyframe_insert(data_path="location")
        obj.keyframe_insert(data_path="scale")

    _set_fcurves_constant(action, {"location", "scale"}, owner=obj)


def _safe_clear_material_slots(mesh):
    """
    Version-safe removal for mesh.materials.

    Do not use .clear(); it is not available on bpy_prop_collection in some builds.
    """
    if mesh is None or not hasattr(mesh, "materials"):
        return

    mats = mesh.materials
    try:
        for idx in range(len(mats) - 1, -1, -1):
            mats.pop(index=idx)
    except Exception:
        try:
            while len(mats) > 0:
                mats.remove(mats[0])
        except Exception:
            return


def _ensure_unique_mesh_datablock(obj) -> bool:
    """
    If this object uses a shared mesh datablock, duplicate it so per-layer material slots
    do not stomp other layers.

    Returns True if a copy was made.
    """
    if not obj or getattr(obj, "type", None) != "MESH":
        return False
    if not getattr(obj, "data", None):
        return False

    # For clone objects we explicitly want to share mesh later.
    # We will force sharing in the clone resolver, so do not duplicate here.
    if obj.get("_oca_is_clone", False):
        return False

    mesh = obj.data
    try:
        users = int(getattr(mesh, "users", 0))
    except Exception:
        users = 0

    if users > 1:
        try:
            obj.data = mesh.copy()
            return True
        except Exception:
            return False

    return False


def calculate_collection_instance_offset(collection):
    """Calculate bounding box center X/Z in world space, and highest duik_layer.depth for Y."""
    min_corner = Vector((float("inf"), float("inf"), float("inf")))
    max_corner = Vector((float("-inf"), float("-inf"), float("-inf")))
    highest_y = float("-inf")
    has_geometry = False

    depsgraph = bpy.context.evaluated_depsgraph_get()

    for obj in collection.all_objects:
        if obj.type == "MESH" and obj.data:
            obj_eval = obj.evaluated_get(depsgraph)
            mesh = obj_eval.to_mesh()

            for v in mesh.vertices:
                world_coord = obj.matrix_world @ v.co
                has_geometry = True
                for i in range(3):
                    min_corner[i] = min(min_corner[i], world_coord[i])
                    max_corner[i] = max(max_corner[i], world_coord[i])

            obj_eval.to_mesh_clear()

        if hasattr(obj, "duik_layer") and hasattr(obj.duik_layer, "depth"):
            highest_y = max(highest_y, obj.duik_layer.depth)

    if not has_geometry:
        return Vector((0.0, 0.0, 0.0))

    center_x = (min_corner.x + max_corner.x) / 2.0
    center_z = (min_corner.z + max_corner.z) / 2.0
    final_y = highest_y if highest_y != float("-inf") else 0.0

    return Vector((center_x, final_y, center_z))


def apply_common_transformations(context, obj, depth, scene=None):
    """Preserve v0.8.2 Euler additions, including Blender IDPropertyArray values."""
    if not obj:return
    if getattr(obj,'instance_type',None)=='COLLECTION':
        if hasattr(obj,'duik_layer'):obj.duik_layer.depth=depth
        return
    values=obj.get('_oca_rotation_euler_add',(0.,0.,0.))
    values=tuple(float(v) for v in values)
    obj.rotation_euler=(math.pi/2+values[0],values[1],values[2])


def _force_depth_on_object(obj: bpy.types.Object, depth: float) -> None:
    """Ensure the object's depth is applied both to duik properties and transform Y."""
    if not obj:
        return

    # Duik depth property
    try:
        if hasattr(obj, "duik_layer") and hasattr(obj.duik_layer, "depth"):
            obj.duik_layer.depth = float(depth)
    except Exception:
        pass

    # Transform Y as a reliable fallback
    try:
        obj.location.y = float(depth)
    except Exception:
        pass

def _material_surface_linked_via_group_fallback(mat: bpy.types.Material) -> bool:
    """
    Fallback checker in case blend_modes.material_surface_linked_via_group is not present.
    """
    if not mat or not getattr(mat, "use_nodes", False) or not getattr(mat, "node_tree", None):
        return False
    nt = mat.node_tree
    out_nodes = [n for n in nt.nodes if getattr(n, "type", "") == "OUTPUT_MATERIAL"]
    if not out_nodes:
        return False
    out = next((n for n in out_nodes if getattr(n, "is_active_output", False)), out_nodes[0])
    surface_in = out.inputs.get("Surface") if getattr(out, "inputs", None) else None
    if not surface_in or not getattr(surface_in, "is_linked", False) or not surface_in.links:
        return False
    link = surface_in.links[0]
    from_node = getattr(link, "from_node", None)
    return bool(from_node and getattr(from_node, "type", "") == "GROUP")


def _audit_imported_layers(
    imported_objects: List[bpy.types.Object],
    label: str = "AUDIT",
) -> None:
    """
    End-of-import audit to confirm object -> mesh -> material assignment and that the active
    material output is driven via the BLEND-MODE group.

    This does not modify anything; it only prints.
    """
    if not imported_objects:
        return

    print("")
    print("------------------------------------------------------------")
    print(f"[OCA IMPORT {label}] Imported layer object audit: {len(imported_objects)} objects")
    print("------------------------------------------------------------")

    for obj in imported_objects:
        if not obj or obj.name not in bpy.data.objects:
            continue

        obj_type = getattr(obj, "type", "UNKNOWN")
        is_inst = bool(getattr(obj, "instance_type", None) == "COLLECTION")
        mesh = getattr(obj, "data", None) if obj_type == "MESH" else None

        mesh_name = getattr(mesh, "name", None)
        try:
            mesh_users = int(getattr(mesh, "users", 0)) if mesh else 0
        except Exception:
            mesh_users = 0

        mat0 = None
        mat_slots = 0
        if mesh and hasattr(mesh, "materials"):
            try:
                mat_slots = len(mesh.materials)
            except Exception:
                mat_slots = 0
            if mat_slots > 0:
                try:
                    mat0 = mesh.materials[0]
                except Exception:
                    mat0 = None

        mat_name = getattr(mat0, "name", None) if mat0 else None

        group_ok = _material_surface_linked_via_group_fallback(mat0) if mat0 else False

        print(f"[OCA IMPORT {label}] OBJ '{obj.name}' type={obj_type} instance={is_inst}")
        print(f"  MESH name={mesh_name} users={mesh_users} mat_slots={mat_slots} mat0={mat_name}")
        print(f"  GROUP_DRIVES_ACTIVE_SURFACE={group_ok}")

    print("------------------------------------------------------------")
    print("")


class IMPORT_OCA_OT_import(bpy.types.Operator, AddObjectHelper):
    """Imports Open Cel Animation as mesh planes."""
    bl_idname = "import_oca.import"
    bl_label = "Import OCA as Duik 2D Scene"
    bl_options = {"REGISTER", "PRESET", "UNDO"}

    filepath: bpy.props.StringProperty(
        maxlen=1024, subtype="FILE_PATH", options={"HIDDEN", "SKIP_SAVE"}
    )
    filename: bpy.props.StringProperty(
        maxlen=1024, subtype="FILE_NAME", options={"HIDDEN", "SKIP_SAVE"}
    )
    directory: bpy.props.StringProperty(
        maxlen=1024, subtype="DIR_PATH", options={"HIDDEN", "SKIP_SAVE"}
    )

    shader: bpy.props.EnumProperty(
        name="Shader",
        items=(
            (
                "PRINCIPLEDEMIT",
                "Principled Emit",
                "Self illuminated Principled shader. PBR compatible",
            ),
            (
                "PRINCIPLED",
                "Principled",
                "Principled shader affected by scene lighting. PBR compatible",
            ),
            (
                "SHADELESS",
                "Shadeless",
                "Camera/reflection visible. Will default to Principled on export",
            ),
            ("EMISSION", "Emit", "Emission shader. Will default to Principled on export"),
        ),
        default="PRINCIPLEDEMIT",
        description="Node shader to use",
    )

    scene_type: bpy.props.EnumProperty(
        name="Scene perspective",
        items=(
            ("2D", "2D", "A 2D scene (orthographic)", "VIEW_ORTHO", 0),
            ("2.5D", "2.5D", "A 2.5D scene (perspective)", "VIEW_PERSPECTIVE", 1),
        ),
        default="2D",
        description="Perspective of the scene",
    )

    update_timeline: bpy.props.BoolProperty(
        name="Update frame range",
        description="Update frame range according to imported animation",
        default=False,
    )

    update_fps: bpy.props.BoolProperty(
        name="Update frame rate",
        description="Update FPS according to imported animation",
        default=True,
    )

    render_settings: bpy.props.EnumProperty(
        name="Render Preset",
        items=(
            ("REALTIME", "Real-time", "Real-time optimized settings"),
            ("RENDER", "Render", "Higher quality render settings"),
            ("DEFAULT", "Default", "Keep the user's current settings"),
        ),
        default="REALTIME",
    )

    color_management: bpy.props.EnumProperty(
        name="Color Management",
        items=(
            ("AUTO", "Automatic", "Use sRGB and Khronos PBR Neutral if applicable"),
            ("DEFAULT", "Default", "Leave Blender color management unchanged"),
        ),
        default="AUTO",
    )

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        box.label(text="Spatial Options:", icon="SNAP_GRID")
        box.row().prop(self, "scene_type", expand=True)

        box = layout.box()
        box.label(text="Material Settings:", icon="MATERIAL")
        box.row().prop(self, "shader", expand=True)

        box = layout.box()
        box.label(text="Scene and Render Settings:", icon="SCENE")
        box.prop(self, "update_timeline")
        box.prop(self, "update_fps")

        box = layout.box()
        box.label(text="Render Preset:", icon="RENDER_STILL")
        box.row().prop(self, "render_settings", expand=True)

        box = layout.box()
        box.label(text="Color Management:", icon="COLOR")
        box.row().prop(self, "color_management", expand=True)

        return None

    def invoke(self, context, event):
        del event

        engine = context.scene.render.engine
        if engine not in {"CYCLES", "BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"}:
            if engine != "BLENDER_WORKBENCH":
                self.report(
                    {"ERROR"},
                    f"Cannot generate materials for unknown render engine: {engine}",
                )
                return {"CANCELLED"}
            self.report(
                {"WARNING"},
                f"Generating Cycles/EEVEE compatible material, but it won't be visible in {engine}",
            )

        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        editmode = context.preferences.edit.use_enter_edit_mode
        context.preferences.edit.use_enter_edit_mode = False
        if context.active_object and context.active_object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        try:
            self.import_oca(context)
            if self.render_settings in {"REALTIME", "RENDER"}:
                from . import eevee_optimise
                if self.render_settings == "REALTIME":
                    eevee_optimise.apply_realtime_settings()
                else:
                    eevee_optimise.apply_render_settings()
            if self.color_management == "AUTO":
                from . import colorIO
                colorIO.apply_color_management()
            self._finalize_blend_modes()
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        finally:
            context.preferences.edit.use_enter_edit_mode = editmode
        dublf.ui.redraw()
        return {"FINISHED"}

    def _finalize_blend_modes(self) -> None:
        blend_queue = getattr(self, "_blend_queue", None)
        if not blend_queue:
            return

        print(f"[OCA BLEND] Finalizing blend modes for {len(blend_queue)} material assignments...")

        warned = getattr(self, "_warned_blend_modes", None)
        if warned is None:
            self._warned_blend_modes = set()
            warned = self._warned_blend_modes

        unique_mats = []
        seen = set()
        for mat, _ in blend_queue:
            if not mat:
                continue
            key = mat.as_pointer()
            if key in seen:
                continue
            seen.add(key)
            unique_mats.append(mat)

        for mat in unique_mats:
            ensure_material_blend_wiring(mat, reporter=self.report)

        seen.clear()
        for mat, oca_blend in blend_queue:
            if not mat:
                continue
            key = mat.as_pointer()
            if key in seen:
                continue
            seen.add(key)

            decision = decide_target(oca_blend)
            set_blend_group_output(mat, decision.target)

        for mat in unique_mats:
            try:
                probe_material_outputs(mat, label="FINAL")
            except Exception:
                pass

        _audit_imported_layers(getattr(self, "_imported_layer_objects", []), label="FINAL")

    def import_oca(self, context):
        from . import oca13_import
        if oca13_import.try_import(self,context):
            return
        resolved_clones = set()
        self.original_objects = {}
        self.clone_queue = []

        self._warned_blend_modes = set()

        self._blend_queue: List[Tuple[bpy.types.Material, str]] = []
        self._imported_layer_objects: List[bpy.types.Object] = []

        oca_document = dublf.oca.load(self.filepath)

        self._doc_w = int(oca_document["width"])
        self._doc_h = int(oca_document["height"])
        self._start_time = int(oca_document.get("startTime", 0))

        if self.update_timeline:
            context.scene.frame_start = oca_document["startTime"]
            context.scene.frame_end = oca_document["endTime"]

        if self.update_fps:
            context.scene.render.fps = oca_document["frameRate"]

        material_shader = self.shader
        self._material_shader = material_shader

        scene_shader = material_shader
        if scene_shader == "PRINCIPLEDEMIT":
            scene_shader = "PRINCIPLED"

        scene_root = layers.create_scene(
            context,
            oca_document["name"],
            oca_document["width"],
            oca_document["height"],
            oca_document["backgroundColor"],
            self.scene_type,
            scene_shader,
        )

        render_scene = _get_render_scene(context, scene_root)

        _set_render_resolution(render_scene, self._doc_w, self._doc_h, 100)
        _fit_duik_camera(scene_root, render_scene, self._doc_w, self._doc_h, px_to_unit=100.0)

        depth_stack = {"current": 0.0}
        for layer in oca_document["layers"]:
            self.import_layer(
                context,
                layer,
                scene_root,
                scene_root,
                depth_stack,
                material_shader,
            )

        # Resolve clones after originals exist
        for oca_layer, containing_group, depth, clone_stub in self.clone_queue:
            clone_name = oca_layer["name"]
            if clone_name in resolved_clones:
                continue
            resolved_clones.add(clone_name)

            frames = oca_layer.get("frames") or [{}]
            source_name = frames[0].get("name", clone_name)
            source_key = _norm_key(source_name)

            source_obj = self.original_objects.get(source_key)
            source_collection = bpy.data.collections.get(source_key)

            clone_obj = clone_stub

            if source_obj and getattr(source_obj, "data", None):
                clone_obj.data = source_obj.data
                self._apply_clone_size_scale(clone_obj,oca_layer,source_obj)

                # Ensure slot 0 is object-linked and keeps its own material
                # (the clone already created its own material in import_layer)
                try:
                    if clone_obj.material_slots and clone_obj.material_slots[0]:
                        clone_obj.material_slots[0].link = "OBJECT"
                except Exception:
                    pass

            elif source_collection:
                clone_obj.data = None
                clone_obj.instance_type = "COLLECTION"
                clone_obj.instance_collection = source_collection
            else:
                print(f"[OCA CLONE] Unresolved clone '{clone_name}' source='{source_key}'")
                continue

            clone_obj["_skip_doc_offset"] = True
            layers.set_layer_position(clone_obj, oca_layer["position"])
            layers.set_as_layer(clone_obj, containing_group)

            # Ensure clone depth is actually applied in transforms
            _force_depth_on_object(clone_obj, depth)

            if hasattr(layers, "init_duik_properties"):
                layers.init_duik_properties(clone_obj, clone_name, depth)

        unique_objs = {}
        for obj in self.original_objects.values():
            try:
                if obj and obj.name in bpy.data.objects:
                    unique_objs[obj.name] = obj
            except ReferenceError:
                pass

        for obj in [e[3] for e in self.clone_queue]:
            try:
                if obj and obj.name in bpy.data.objects:
                    unique_objs[obj.name] = obj
            except ReferenceError:
                pass

        for obj in unique_objs.values():
            depth = getattr(getattr(obj, "duik_layer", None), "depth", 0.0)
            apply_common_transformations(context, obj, depth, scene_root)


        seen_collections = set()
        for obj in self.original_objects.values():
            for col in getattr(obj, "users_collection", []):
                if col.name in seen_collections:
                    continue
                seen_collections.add(col.name)

                center = calculate_collection_instance_offset(col)
                col.instance_offset = Vector((center.x, center.y, center.z))

        for oca_layer, containing_group, _depth, clone_obj in self.clone_queue:
            frames = oca_layer.get("frames") or [{}]
            source_name = frames[0].get("name", clone_obj.name)
            source_key = _norm_key(source_name)

            source_collection = bpy.data.collections.get(source_key)
            if not source_collection:
                continue

            center = calculate_collection_instance_offset(source_collection)
            group_depth_correction = abs(center.y)

            start_fixing = False
            for obj in sorted(
                containing_group.objects,
                key=lambda o: getattr(getattr(o, "duik_layer", None), "depth", 0.0),
                reverse=True,
            ):
                if start_fixing and hasattr(obj, "duik_layer") and hasattr(obj.duik_layer, "depth"):
                    obj.duik_layer.depth -= group_depth_correction
                if obj == clone_obj:
                    start_fixing = True

    def _apply_clone_size_scale(self, obj, layer, source):
        # Raw shared mesh bounds are independent of the source object's current
        # non-uniform scale or rotation. Correct the clone's own animation too.
        vertices=source.data.vertices
        width=(max(v.co.x for v in vertices)-min(v.co.x for v in vertices))*100
        height=(max(v.co.y for v in vertices)-min(v.co.y for v in vertices))*100
        if width<=0 or height<=0:raise ValueError('Clone source has empty image bounds')
        factors=(float(layer['width'])/width,float(layer['height'])/height)
        previous=obj.get('_oca_clone_size_correction',(1.,1.))
        delta=[factors[i]/previous[i] for i in range(2)]
        for i in range(2):obj.scale[i]*=delta[i]
        frame0=_first_nonblank_frame(layer.get('frames',[]))
        frame_pos=frame0.get('position',layer['position'])
        dx=(float(layer['position'][0])-float(frame_pos[0]))/100
        dz=-(float(layer['position'][1])-float(frame_pos[1]))/100
        for curve in _action_curves(obj):
            if curve.data_path=='scale' and curve.array_index in (0,1):
                factor=delta[curve.array_index]
                for key in curve.keyframe_points:
                    key.co[1]*=factor;key.handle_left[1]*=factor;key.handle_right[1]*=factor
            elif curve.data_path=='location' and curve.array_index in (0,2):
                offset=dx if curve.array_index==0 else dz
                for key in curve.keyframe_points:
                    key.co[1]+=offset;key.handle_left[1]+=offset;key.handle_right[1]+=offset
        obj['_oca_clone_size_correction']=factors

    def import_layer(
        self,
        context,
        oca_layer,
        containing_group,
        scene_root,
        depth_stack=None,
        shader_mode=None,
    ):
        del scene_root

        if depth_stack is None:
            depth_stack = {"current": 0.0}

        if shader_mode is None:
            shader_mode = getattr(self, "_material_shader", getattr(self, "shader", "PRINCIPLED"))

        layer_type = oca_layer["type"]

        if layer_type == "grouplayer":
            group = layers.create_group(context, oca_layer["name"], containing_group)
            for child in oca_layer.get("childLayers", []):
                self.import_layer(context, child, group, group, depth_stack, shader_mode)
            group.hide_viewport = not oca_layer.get("visible", True)
            group.hide_render = oca_layer.get("reference", False)
            return

        if layer_type not in {"paintlayer", "vectorlayer", "filllayer", "filelayer", "clonelayer"}:
            return

        layer_name = oca_layer["name"]
        frames = oca_layer.get("frames") or [{}]
        frame0 = _first_nonblank_frame(frames)
        frame_name = frame0.get("name", layer_name)
        file_name = frame0.get("fileName", "") or ""

        depth_stack["current"] -= 0.01
        current_depth = depth_stack["current"]

        is_clone = (layer_type == "clonelayer")
        if is_clone:
            oca_layer["_was_image_clonelayer"] = True

        layer_obj = layers.create_layer(
            context, layer_name, abs(oca_layer["width"]), abs(oca_layer["height"]), containing_group
        )

        self._imported_layer_objects.append(layer_obj)

        layer_obj["_oca_is_clone"] = bool(is_clone)

        # Register originals for lookup. For clones, do not register frame_name to avoid overriding.
        self.original_objects[_norm_key(layer_name)] = layer_obj
        if not is_clone:
            self.original_objects[_norm_key(frame_name)] = layer_obj
            # Also register all non-blank frame names for animated sources
            for fr in frames:
                nm = _norm_key(fr.get("name", ""))
                fn = (fr.get("fileName") or "").strip()
                if nm and nm != "_blank" and fn:
                    self.original_objects[nm] = layer_obj

        layers.set_layer_position(layer_obj, oca_layer["position"])
        layers.set_as_layer(layer_obj, containing_group)

        if hasattr(layers, "init_duik_properties"):
            layers.init_duik_properties(layer_obj, layer_name, current_depth)
        else:
            if hasattr(layer_obj, "duik_layer"):
                layer_obj.duik_layer.depth = current_depth
            if hasattr(layer_obj, "duik_type"):
                layer_obj.duik_type = "LAYER"

        rotation_payload,camera_height=_get_layer_rotation_payload(oca_layer)
        angles=_parse_oca_rotation_value(rotation_payload)
        layer_obj['_oca_rotation_euler_add']=angles
        layer_obj['_oca_cameraHeight']=camera_height
        layer_obj.rotation_euler=(math.pi/2+angles[0],angles[1],angles[2])

        _apply_cropped_frame_transform_keys(
            layer_obj,
            oca_layer,
            self._doc_w,
            self._doc_h,
            px_to_unit=100.0,
            frame_base=self._start_time,
        )

        _apply_rotation_keys(layer_obj,oca_layer,frame_base=self._start_time)

        self.update_frame_paths(oca_layer["frames"])

        # Material naming should be layer_name, not frame_name
        shader_base_name = re.sub(r"\.\d+$", "", layer_name)

        frames_shader = layers.create_layer_shader(
            shader_base_name,
            oca_layer["frames"],
            oca_layer.get("animated", False),
            shader_mode,
        )

        if oca_layer.get("label", 0) != 0:
            frames_shader.diffuse_color = dublf.oca.OCALabels[oca_layer["label"] % 8 + 1]

        _ensure_unique_mesh_datablock(layer_obj)

        if getattr(layer_obj, "data", None) is not None and hasattr(layer_obj.data, "materials"):
            _safe_clear_material_slots(layer_obj.data)
            layer_obj.data.materials.append(frames_shader)

        # For clones, keep material as OBJECT-linked so it survives mesh reassignment
        if is_clone:
            try:
                if layer_obj.material_slots and layer_obj.material_slots[0]:
                    layer_obj.material_slots[0].link = "OBJECT"
                    layer_obj.material_slots[0].material = frames_shader
            except Exception:
                pass

            # Enqueue for later mesh sharing resolution
            self.clone_queue.append((oca_layer, containing_group, current_depth, layer_obj))

        oca_blend = oca_layer.get("blendingMode", "normal")
        print(f"[OCA BLEND] queued: {frames_shader.name} -> {oca_blend}")

        try:
            frames_shader["oca_blendingMode"] = (oca_blend or "normal")
        except Exception:
            pass

        self._blend_queue.append((frames_shader, oca_blend))

        if DEBUG_VERBOSE:
            try:
                probe_material_outputs(frames_shader, label="POST_CREATE_SHADER")
            except Exception:
                pass

    def update_frame_paths(self, frames):
        project_name = os.path.basename(self.filepath)
        if project_name.lower().endswith(".oca"):
            project_name = project_name[:-4]

        for f in frames:
            file_name = f.get("fileName", "")
            if not file_name:
                continue

            file_rel = file_name.lstrip("/")

            if file_rel.startswith(project_name + "/"):
                file_rel = file_rel[len(project_name) + 1 :]

            f["fileName"] = os.path.join(self.directory.rstrip("/"), file_rel).replace("\\\\", "/")


def import_oca_button(self, context):
    del context
    self.layout.operator(
        IMPORT_OCA_OT_import.bl_idname,
        text="OCA as Duik 2D Scene",
        icon="ONIONSKIN_ON",
    )


classes = (IMPORT_OCA_OT_import,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(import_oca_button)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    bpy.types.TOPBAR_MT_file_import.remove(import_oca_button)
