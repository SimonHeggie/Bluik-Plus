# <pep8 compliant>

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Optional, Set

import bpy  # pylint: disable=import-error


Target = str
Severity = str  # "exact" | "approx" | "incompatible"


@dataclass(frozen=True)
class BlendDecision:
    target: Target
    severity: Severity
    message: str


TARGET_NORMAL: Target = "normal"
TARGET_MULTIPLY: Target = "multiply"
TARGET_ADD: Target = "add"
TARGET_LUMINOSITY: Target = "luminosity"

_GROUP_NAME = "BLEND-MODE"


EXACT_MAP: Dict[str, Target] = {
    "normal": TARGET_NORMAL,
    "multiply": TARGET_MULTIPLY,
    "add": TARGET_ADD,
    "screen": TARGET_ADD,
    "linear_dodge": TARGET_ADD,
    "luminosity_sai": TARGET_LUMINOSITY,
}

APPROX_MULTIPLY = {
    "darken",
    "burn",
    "linear_burn",
    "easy_burn",
    "gamma_dark",
    "fog_darken_ifs_illusions",
    "fog_darken",
    "shade_ifs_illusions",
    "shade",
    "alpha_darken",
    "subtract",
    "inverse_subtract",
}

APPROX_ADD = {
    "dodge",
    "easy dodge",
    "easy_dodge",
    "glow",
    "glow_heat",
    "heat",
    "heat_glow",
    "heat_glow_freeze_reflect_hybrid",
    "heat_glow_freeze_reflect",
    "super_light",
}

REFUSE_SET = {
    "hue",
    "saturation",
    "color",
    "luminosity",
    "hue_hsi",
    "saturation_hsi",
    "color_hsi",
    "inc_intensity",
    "dec_intensity",
    "inc_saturation_hsi",
    "dec_saturation_hsi",
    "hue_hsl",
    "saturation_hsl",
    "color_hsl",
    "inc_lightness",
    "dec_lightness",
    "inc_saturation_hsl",
    "dec_saturation_hsl",
    "hue_hsv",
    "saturation_hsv",
    "value",
    "color_hsv",
    "inc_value",
    "dec_value",
    "inc_saturation_hsv",
    "dec_saturation_hsv",
    "dec_luminosity",
    "inc_saturation",
    "dec_saturation",
    "increase_luminosity",
    "decrease_luminosity",
    "increase_saturation",
    "decrease_saturation",
    "diff",
    "difference",
    "exclusion",
    "negation",
    "and",
    "or",
    "xor",
    "xnor",
    "nand",
    "nor",
    "implication",
    "not_implication",
    "converse",
    "not_converse",
    "equivalence",
    "greater",
    "geometric_mean",
    "divisive_modulo",
    "parallel",
    "allanon",
    "pnorm_a",
    "pnorm_b",
    "penumbra a",
    "penumbra b",
    "penumbra c",
    "penumbra d",
    "penumbra_a",
    "penumbra_b",
    "penumbra_c",
    "penumbra_d",
    "arc_tangent",
    "erase",
    "destination-in",
    "stencil_alpha",
    "destination in",
}


def decide_target(oca_mode: str) -> BlendDecision:
    raw = (oca_mode or "").strip()
    key = raw.lower()

    if key in EXACT_MAP:
        return BlendDecision(EXACT_MAP[key], "exact", "")

    if key in APPROX_MULTIPLY:
        return BlendDecision(
            TARGET_MULTIPLY,
            "approx",
            f"OCA blend '{raw}' approximated to '{TARGET_MULTIPLY}'.",
        )

    if key in APPROX_ADD:
        if key in {"dodge", "easy dodge", "easy_dodge"}:
            return BlendDecision(
                TARGET_LUMINOSITY,
                "approx",
                f"OCA blend '{raw}' approximated to '{TARGET_LUMINOSITY}'.",
            )
        return BlendDecision(
            TARGET_ADD,
            "approx",
            f"OCA blend '{raw}' approximated to '{TARGET_ADD}'.",
        )

    if key in REFUSE_SET:
        return BlendDecision(
            TARGET_NORMAL,
            "incompatible",
            f"Very incompatible blend mode '{raw}'. Falling back to '{TARGET_NORMAL}'.",
        )

    return BlendDecision(
        TARGET_NORMAL,
        "incompatible",
        f"Unknown blend mode '{raw}'. Falling back to '{TARGET_NORMAL}'.",
    )


# ----------------------------------------------------------------------
# Probes
# ----------------------------------------------------------------------

def _sock_src_str(sock: Optional[bpy.types.NodeSocket]) -> str:
    if not sock:
        return "None"
    try:
        node = sock.node
        return f"{node.name} ({node.type}).{sock.name}"
    except Exception:
        return "UnknownSocket"


def _surface_link_str(out_node: bpy.types.Node) -> str:
    try:
        surf = out_node.inputs.get("Surface")
        if not surf:
            return "Surface: <missing>"
        if not surf.is_linked or not surf.links:
            return "Surface: UNLINKED"
        lk = surf.links[0]
        return f"Surface: linked from {_sock_src_str(lk.from_socket)}"
    except Exception:
        return "Surface: <error>"


def _find_group_node_by_name(mat: bpy.types.Material, group_name: str) -> Optional[bpy.types.Node]:
    if not mat or not mat.use_nodes or not mat.node_tree:
        return None
    for n in mat.node_tree.nodes:
        if getattr(n, "type", "") == "GROUP":
            ng = getattr(n, "node_tree", None)
            if ng and getattr(ng, "name", "") == group_name:
                return n
    return None


def _iter_material_outputs(nt: bpy.types.NodeTree):
    for n in getattr(nt, "nodes", []):
        if n and getattr(n, "type", "") == "OUTPUT_MATERIAL":
            yield n


def probe_material_outputs(mat: bpy.types.Material, label: str = "") -> None:
    """
    Diagnostic probe. Call this after your final blend pass.
    Prints:
      - all material outputs, which is active, and surface linkage
      - group node status and its Shader input linkage
    """
    if not mat or not getattr(mat, "use_nodes", False) or not getattr(mat, "node_tree", None):
        print(f"[OCA BLEND PROBE] {label} material={getattr(mat, 'name', '?')} has no node tree")
        return

    nt = mat.node_tree
    outs = list(_iter_material_outputs(nt))
    group_node = _find_group_node_by_name(mat, _GROUP_NAME)

    header = f"[OCA BLEND PROBE] {label} material='{mat.name}' outputs={len(outs)} nodes={len(nt.nodes)} links={len(nt.links)}"
    print(header)

    for i, out_node in enumerate(outs):
        active = bool(getattr(out_node, "is_active_output", False))
        print(f"  OUT[{i}] name='{out_node.name}' active={active} { _surface_link_str(out_node) }")

    if not group_node:
        print("  GROUP: missing")
        return

    print(f"  GROUP: present name='{group_node.name}'")

    try:
        shader_in = group_node.inputs.get("Shader")
        if not shader_in:
            print("  GROUP Shader input: <missing>")
        elif not shader_in.is_linked or not shader_in.links:
            print("  GROUP Shader input: UNLINKED")
        else:
            print(f"  GROUP Shader input: linked from {_sock_src_str(shader_in.links[0].from_socket)}")
    except Exception:
        print("  GROUP Shader input: <error>")

    try:
        if outs:
            active_out = next((o for o in outs if getattr(o, "is_active_output", False)), outs[0])
            surf = active_out.inputs.get("Surface")
            if surf and surf.is_linked and surf.links:
                src = surf.links[0].from_socket
                src_node = getattr(src, "node", None)
                if src_node == group_node:
                    print(f"  ACTIVE Surface is driven by GROUP output socket '{src.name}'")
                else:
                    print(f"  ACTIVE Surface is NOT driven by GROUP. It is driven by {_sock_src_str(src)}")
    except Exception:
        print("  ACTIVE Surface driver: <error>")


# ----------------------------------------------------------------------
# Node group creation
# ----------------------------------------------------------------------

def _remove_all_nodes(node_tree: bpy.types.NodeTree) -> None:
    nodes = getattr(node_tree, "nodes", None)
    if not nodes:
        return
    for n in list(nodes):
        try:
            nodes.remove(n)
        except Exception:
            pass


def _remove_all_interface_items(ng: bpy.types.NodeTree) -> None:
    iface = getattr(ng, "interface", None)
    if iface is None:
        return
    items = getattr(iface, "items_tree", None)
    if items is None:
        return
    try:
        all_items = list(items)
    except Exception:
        all_items = []
    for it in reversed(all_items):
        try:
            iface.remove(it)
        except Exception:
            try:
                items.remove(it)
            except Exception:
                pass


def _group_has_required_sockets(ng: bpy.types.NodeTree) -> bool:
    if not ng or getattr(ng, "bl_idname", "") != "ShaderNodeTree":
        return False
    try:
        has_in = "Shader" in ng.inputs
        has_out = all(
            name in ng.outputs
            for name in (TARGET_ADD, TARGET_LUMINOSITY, TARGET_MULTIPLY, TARGET_NORMAL)
        )
        return bool(has_in and has_out)
    except Exception:
        return False

# ----------------------------------------------------------------------
# Node group creation - MAIN MODULE:
# ----------------------------------------------------------------------

def _ensure_blend_group(rebuild: bool = False) -> bpy.types.NodeTree:
    ng = bpy.data.node_groups.get(_GROUP_NAME)

    def looks_valid(g: bpy.types.NodeTree) -> bool:
        if not g or getattr(g, "bl_idname", "") != "ShaderNodeTree":
            return False
        try:
            if "Shader" not in g.inputs:
                return False
            for name in ("add", "luminosity", "multiply", "normal"):
                if name not in g.outputs:
                    return False
        except Exception:
            return False
        try:
            non_io = [n for n in g.nodes if n.type not in {"GROUP_INPUT", "GROUP_OUTPUT"}]
            return len(non_io) > 0
        except Exception:
            return False

    if ng and looks_valid(ng) and not rebuild:
        return ng

    if not ng or getattr(ng, "bl_idname", "") != "ShaderNodeTree":
        ng = bpy.data.node_groups.new(_GROUP_NAME, "ShaderNodeTree")

    _remove_all_nodes(ng)

    if hasattr(ng, "interface"):
        _remove_all_interface_items(ng)
        iface = ng.interface
        iface.new_socket(name="Shader", in_out="INPUT", socket_type="NodeSocketShader")
        for name in ("add", "luminosity", "multiply", "normal"):
            iface.new_socket(name=name, in_out="OUTPUT", socket_type="NodeSocketShader")
    else:
        if "Shader" not in ng.inputs:
            ng.inputs.new("NodeSocketShader", "Shader")
        for name in ("add", "luminosity", "multiply", "normal"):
            if name not in ng.outputs:
                ng.outputs.new("NodeSocketShader", name)

    nodes = ng.nodes
    links = ng.links

    n_in = nodes.new("NodeGroupInput")
    n_in.location = (-800, 0)

    n_out = nodes.new("NodeGroupOutput")
    n_out.location = (800, 0)

    shader_out = next((s for s in n_in.outputs if s.name == "Shader"), None)
    if shader_out is None and n_in.outputs:
        shader_out = n_in.outputs[0]

    out_add = next((s for s in n_out.inputs if s.name == "add"), None)
    out_lum = next((s for s in n_out.inputs if s.name == "luminosity"), None)
    out_mul = next((s for s in n_out.inputs if s.name == "multiply"), None)
    out_norm = next((s for s in n_out.inputs if s.name == "normal"), None)

    frame_add = nodes.new("NodeFrame")
    frame_add.label = "Additive - (Spine calls it 'screen')"
    frame_add.location = (-200, 400)

    frame_lum = nodes.new("NodeFrame")
    frame_lum.label = "Luminocity/Shine (SAI) (Spine calls it 'Additive')"
    frame_lum.location = (-200, 150)

    frame_mul = nodes.new("NodeFrame")
    frame_mul.label = "Multiply"
    frame_mul.location = (-200, -150)

    frame_norm = nodes.new("NodeFrame")
    frame_norm.label = "Normal (clamped alpha)"
    frame_norm.location = (-200, -400)

    # 1) ADD
    sh_to_rgb_add = nodes.new("ShaderNodeShaderToRGB")
    sh_to_rgb_add.location = (-500, 450)
    sh_to_rgb_add.parent = frame_add

    bsdf_trans_add = nodes.new("ShaderNodeBsdfTransparent")
    bsdf_trans_add.location = (-250, 350)
    bsdf_trans_add.parent = frame_add

    add_shader_add = nodes.new("ShaderNodeAddShader")
    add_shader_add.location = (50, 400)
    add_shader_add.parent = frame_add

    if shader_out is not None:
        links.new(shader_out, sh_to_rgb_add.inputs[0])

    links.new(sh_to_rgb_add.outputs["Color"], add_shader_add.inputs[0])
    links.new(bsdf_trans_add.outputs["BSDF"], add_shader_add.inputs[1])
    if out_add is not None:
        links.new(add_shader_add.outputs["Shader"], out_add)

    # 2) LUMINOSITY (simplified: remove RGB Curves, keep Mix FLOAT)
    sh_to_rgb_lum = nodes.new("ShaderNodeShaderToRGB")
    sh_to_rgb_lum.location = (-700, 200)
    sh_to_rgb_lum.parent = frame_lum

    mix_float = nodes.new("ShaderNodeMix")
    mix_float.location = (-450, 80)
    mix_float.parent = frame_lum
    try:
        mix_float.data_type = "FLOAT"
    except Exception:
        pass

    try:
        if "A" in mix_float.inputs:
            mix_float.inputs["A"].default_value = 1.0
        if "B" in mix_float.inputs:
            mix_float.inputs["B"].default_value = 10.0
    except Exception:
        pass

    bsdf_trans_lum = nodes.new("ShaderNodeBsdfTransparent")
    bsdf_trans_lum.location = (-200, 80)
    bsdf_trans_lum.parent = frame_lum

    add_shader_lum = nodes.new("ShaderNodeAddShader")
    add_shader_lum.location = (50, 200)
    add_shader_lum.parent = frame_lum

    if shader_out is not None:
        links.new(shader_out, sh_to_rgb_lum.inputs[0])

    # Keep the float mix driven from the ShaderToRGB color (as before)
    links.new(sh_to_rgb_lum.outputs["Color"], mix_float.inputs[0])

    # Use float mix result to tint transparent (as before)
    try:
        links.new(mix_float.outputs["Result"], bsdf_trans_lum.inputs["Color"])
    except Exception:
        if mix_float.outputs:
            links.new(mix_float.outputs[0], bsdf_trans_lum.inputs["Color"])

    # Requested: ShaderToRGB Color straight into Add Shader top input
    links.new(sh_to_rgb_lum.outputs["Color"], add_shader_lum.inputs[0])

    links.new(bsdf_trans_lum.outputs["BSDF"], add_shader_lum.inputs[1])
    if out_lum is not None:
        links.new(add_shader_lum.outputs["Shader"], out_lum)


    # 3) MULTIPLY
    sh_to_rgb_mul = nodes.new("ShaderNodeShaderToRGB")
    sh_to_rgb_mul.location = (-700, -100)
    sh_to_rgb_mul.parent = frame_mul

    bsdf_trans_mul = nodes.new("ShaderNodeBsdfTransparent")
    bsdf_trans_mul.location = (-450, -200)
    bsdf_trans_mul.parent = frame_mul

    invert_mul = nodes.new("ShaderNodeInvert")
    invert_mul.location = (-450, -40)
    invert_mul.parent = frame_mul
    try:
        invert_mul.inputs["Fac"].default_value = 1.0
    except Exception:
        pass

    mix_shader_mul = nodes.new("ShaderNodeMixShader")
    mix_shader_mul.location = (0, -150)
    mix_shader_mul.parent = frame_mul

    if shader_out is not None:
        links.new(shader_out, sh_to_rgb_mul.inputs[0])
        links.new(shader_out, mix_shader_mul.inputs[2])

    links.new(sh_to_rgb_mul.outputs["Color"], bsdf_trans_mul.inputs["Color"])
    links.new(bsdf_trans_mul.outputs["BSDF"], mix_shader_mul.inputs[1])
    links.new(sh_to_rgb_mul.outputs["Alpha"], invert_mul.inputs["Color"])
    links.new(invert_mul.outputs["Color"], mix_shader_mul.inputs[0])

    if out_mul is not None:
        links.new(mix_shader_mul.outputs["Shader"], out_mul)

    # 4) NORMAL
    sh_to_rgb_norm = nodes.new("ShaderNodeShaderToRGB")
    sh_to_rgb_norm.location = (-700, -400)
    sh_to_rgb_norm.parent = frame_norm

    math_clamp = nodes.new("ShaderNodeMath")
    math_clamp.location = (-450, -400)
    math_clamp.parent = frame_norm
    math_clamp.operation = "MULTIPLY"
    try:
        math_clamp.inputs[1].default_value = 0
    except Exception:
        pass
    math_clamp.use_clamp = True

    mix_shader_norm = nodes.new("ShaderNodeMixShader")
    mix_shader_norm.location = (0, -400)
    mix_shader_norm.parent = frame_norm

    if shader_out is not None:
        links.new(shader_out, mix_shader_norm.inputs[1])
        links.new(shader_out, sh_to_rgb_norm.inputs[0])

    links.new(sh_to_rgb_norm.outputs["Color"], mix_shader_norm.inputs[2])
    links.new(sh_to_rgb_norm.outputs["Alpha"], math_clamp.inputs[0])
    links.new(math_clamp.outputs["Value"], mix_shader_norm.inputs[0])

    if out_norm is not None:
        links.new(mix_shader_norm.outputs["Shader"], out_norm)

    return ng


# ----------------------------------------------------------------------
# Material wiring
# ----------------------------------------------------------------------

def _get_or_create_principled_shader_socket(
    mat: bpy.types.Material,
) -> Optional[bpy.types.NodeSocket]:
    """
    Deterministic fallback shader source.
    Ensures there is a Principled BSDF node and returns its BSDF output socket.
    """
    if not mat or not mat.node_tree:
        return None

    nodes = mat.node_tree.nodes

    princ = next((n for n in nodes if getattr(n, "type", "") == "BSDF_PRINCIPLED"), None)
    if princ is None:
        try:
            princ = nodes.new("ShaderNodeBsdfPrincipled")
            princ.location = (0, 0)
        except Exception:
            return None

    out_sock = None
    try:
        out_sock = princ.outputs.get("BSDF")
    except Exception:
        out_sock = None

    return out_sock

def _ensure_group_shader_input_link(
    mat: bpy.types.Material,
    group_node: bpy.types.Node,
) -> bool:
    """
    Ensures the BLEND-MODE group node has a valid Shader input link.
    Does not touch Material Output.Surface.
    """
    if not mat or not mat.node_tree or not group_node:
        return False

    shader_in = None
    try:
        shader_in = group_node.inputs.get("Shader")
    except Exception:
        shader_in = None
    if not shader_in:
        return False

    if shader_in.is_linked and shader_in.links:
        return True

    src_socket = _find_fallback_shader_source(mat, exclude_node=group_node)
    if src_socket is None:
        src_socket = _get_or_create_principled_shader_socket(mat)

    if src_socket is None:
        return False

    links = mat.node_tree.links
    _remove_links_to_socket(links, shader_in)

    try:
        links.new(src_socket, shader_in)
        return True
    except Exception:
        return False


def ensure_material_blend_wiring(
    mat: bpy.types.Material,
    reporter: Optional[Callable] = None,
) -> bool:
    """
    Public readiness helper:
    - Ensures BLEND-MODE group datablock exists
    - Ensures the material has a group node instance
    - Forces wiring: shader source -> group.Shader, group.normal -> Material Output.Surface
    """
    if not mat:
        return False

    ok = install_blend_group_normal(mat)
    if not ok and reporter is not None:
        try:
            reporter(
                {"WARNING"},
                f"Failed to ensure blend wiring for material '{getattr(mat, 'name', '?')}'.",
            )
        except Exception:
            pass
    return ok


def _iter_material_outputs(nt: bpy.types.NodeTree):
    for n in getattr(nt, "nodes", []):
        if n and getattr(n, "type", "") == "OUTPUT_MATERIAL":
            yield n


def _find_active_material_output(mat: bpy.types.Material):
    if not mat or not mat.use_nodes or not mat.node_tree:
        return None

    nt = mat.node_tree

    # Prefer active output
    for n in _iter_material_outputs(nt):
        if getattr(n, "is_active_output", False):
            return n

    # Fallback: first output
    for n in _iter_material_outputs(nt):
        return n

    return None

def set_blend_group_output(mat: bpy.types.Material, target: str) -> bool:
    """
    Pass 2: Switch which group output drives Material Output Surface.
    Also guarantees group.Shader is linked (deterministic fallback).
    """
    if not mat:
        return False

    mat.use_nodes = True
    if not getattr(mat, "node_tree", None):
        return False

    out_node = _ensure_active_material_output(mat)
    if not out_node:
        return False

    surface_in = out_node.inputs.get("Surface")
    if not surface_in:
        return False

    # Find the BLEND-MODE group node instance
    group_node = None
    for n in mat.node_tree.nodes:
        if n.type == "GROUP" and getattr(getattr(n, "node_tree", None), "name", "") == _GROUP_NAME:
            group_node = n
            break
    if not group_node:
        return False

    # Guarantee Shader input is linked (this is what your probes show missing)
    _ensure_group_shader_input_link(mat, group_node)

    if target not in group_node.outputs:
        target = TARGET_NORMAL

    links = mat.node_tree.links
    _remove_links_to_socket(links, surface_in)

    try:
        links.new(group_node.outputs[target], surface_in)
    except Exception as exc:
        print(f"[OCA BLEND] set_blend_group_output failed for '{mat.name}': {exc}")
        return False

    _ensure_active_material_output(mat)
    return True


def install_blend_group_normal(mat: bpy.types.Material) -> bool:
    """
    Pass 1: Ensure the Blend Mode group exists in the material and is wired in NORMAL mode.
    This is done for every material, regardless of OCA blend mode.
    """
    if not mat:
        return False

    mat.use_nodes = True
    if not getattr(mat, "node_tree", None):
        return False

    ng = bpy.data.node_groups.get(_GROUP_NAME)
    rebuild = not _group_has_required_sockets(ng) if ng else True
    ng = _ensure_blend_group(rebuild=rebuild)

    group_node = _ensure_group_node_in_material(mat, ng)
    out_node = _ensure_active_material_output(mat)
    if not out_node:
        return False

    surface_in = out_node.inputs.get("Surface")
    if not surface_in:
        return False

    shader_in = group_node.inputs.get("Shader")
    if not shader_in:
        return False

    links = mat.node_tree.links

    # Determine shader source: prefer whatever currently feeds Surface, unless it is the group itself.
    src_socket = None
    if surface_in.is_linked and surface_in.links:
        lnk = surface_in.links[0]
        if lnk.from_node != group_node:
            src_socket = lnk.from_socket

    if src_socket is None:
        src_socket = _find_fallback_shader_source(mat, exclude_node=group_node)

    if src_socket is None:
        src_socket = _get_or_create_principled_shader_socket(mat)

    if src_socket is None:
        return False

    # Force wiring
    _remove_links_to_socket(links, shader_in)
    _remove_links_to_socket(links, surface_in)

    try:
        links.new(src_socket, shader_in)
        links.new(group_node.outputs[TARGET_NORMAL], surface_in)
    except Exception as exc:
        print(f"[OCA BLEND] install_blend_group_normal failed for '{mat.name}': {exc}")
        return False

    _ensure_active_material_output(mat)
    return True



def _ensure_active_material_output(mat: bpy.types.Material):
    """
    Ensure there is a Material Output node and that it is active.
    Returns the active output node.
    """
    if not mat or not mat.use_nodes or not mat.node_tree:
        return None

    nt = mat.node_tree
    out = _find_active_material_output(mat)

    if out is None:
        out = nt.nodes.new("ShaderNodeOutputMaterial")

    # Make it active, demote others
    try:
        for n in _iter_material_outputs(nt):
            n.is_active_output = (n == out)
    except Exception:
        pass

    return out


def _find_active_output(mat: bpy.types.Material) -> Optional[bpy.types.Node]:
    if not mat or not mat.use_nodes or not mat.node_tree:
        return None
    for n in _iter_material_outputs(mat.node_tree):
        if getattr(n, "is_active_output", False):
            return n
    for n in _iter_material_outputs(mat.node_tree):
        return n
    return None


def _ensure_active_output(mat: bpy.types.Material) -> Optional[bpy.types.Node]:
    if not mat or not mat.use_nodes or not mat.node_tree:
        return None

    nt = mat.node_tree
    out = _find_active_output(mat)
    if out is None:
        try:
            out = nt.nodes.new("ShaderNodeOutputMaterial")
        except Exception:
            return None

    try:
        for n in _iter_material_outputs(nt):
            n.is_active_output = (n == out)
    except Exception:
        pass

    return out


def _ensure_group_node_in_material(mat: bpy.types.Material, ng: bpy.types.NodeTree) -> bpy.types.Node:
    nodes = mat.node_tree.nodes
    for n in nodes:
        if n.type == "GROUP" and getattr(n, "node_tree", None) == ng:
            return n
    g = nodes.new("ShaderNodeGroup")
    g.node_tree = ng
    g.label = "BLEND-MODE"
    g.name = "BLEND-MODE"
    return g


def _first_shader_output_socket(node: bpy.types.Node) -> Optional[bpy.types.NodeSocket]:
    for out in getattr(node, "outputs", []):
        try:
            if getattr(out, "type", "") == "SHADER":
                return out
        except Exception:
            continue
    return None


def _find_fallback_shader_source(
    mat: bpy.types.Material,
    exclude_node: Optional[bpy.types.Node],
) -> Optional[bpy.types.NodeSocket]:
    nodes = list(getattr(mat.node_tree, "nodes", []))
    preferred_types = ("BSDF_PRINCIPLED", "EMISSION", "GROUP", "MIX_SHADER", "ADD_SHADER")

    for t in preferred_types:
        for n in nodes:
            if n == exclude_node or getattr(n, "type", "") == "OUTPUT_MATERIAL":
                continue
            if getattr(n, "type", "") == t:
                sock = _first_shader_output_socket(n)
                if sock:
                    return sock

    for n in nodes:
        if n == exclude_node or getattr(n, "type", "") == "OUTPUT_MATERIAL":
            continue
        sock = _first_shader_output_socket(n)
        if sock:
            return sock

    return None


def _remove_links_to_socket(links, sock) -> None:
    if not sock:
        return
    for lk in list(getattr(sock, "links", [])):
        try:
            links.remove(lk)
        except Exception:
            pass

def _wire_shader_to_output(mat: bpy.types.Material, group_node: bpy.types.Node, target: Target) -> bool:
    if not mat or not mat.use_nodes or not mat.node_tree:
        return False

    nt = mat.node_tree
    links = nt.links

    out_node = _ensure_active_material_output(mat)
    if not out_node:
        return False

    surface_in = out_node.inputs.get("Surface")
    if not surface_in:
        return False

    shader_input = group_node.inputs.get("Shader") if hasattr(group_node, "inputs") else None
    if not shader_input:
        return False

    if target not in group_node.outputs:
        target = TARGET_NORMAL
    group_out = group_node.outputs.get(target)
    if not group_out:
        return False

    # Capture existing Surface link so we can restore it on failure
    old_surface_from_socket = None
    if surface_in.is_linked and surface_in.links:
        try:
            old_surface_from_socket = surface_in.links[0].from_socket
        except Exception:
            old_surface_from_socket = None

    # Decide shader source without mutating anything
    src_socket = None

    # 1) If group Shader input already has a source, keep it
    if shader_input.is_linked and shader_input.links:
        try:
            src_socket = shader_input.links[0].from_socket
        except Exception:
            src_socket = None

    # 2) Prefer whatever currently feeds Material Output Surface (unless it is the group)
    if src_socket is None and old_surface_from_socket is not None:
        try:
            if surface_in.links[0].from_node != group_node:
                src_socket = old_surface_from_socket
        except Exception:
            src_socket = old_surface_from_socket

    # 3) Fallback scan
    if src_socket is None:
        src_socket = _find_fallback_shader_source(mat, exclude_node=group_node)

    if src_socket is None:
        return False

    # Mutate deterministically: clear then link
    try:
        _remove_links_to_socket(links, shader_input)
        _remove_links_to_socket(links, surface_in)

        links.new(src_socket, shader_input)
        links.new(group_out, surface_in)

    except Exception as exc:
        print(
            "[OCA BLEND] Wiring failed for material "
            f"'{getattr(mat, 'name', '?')}' target='{target}': {exc}"
        )

        # Rollback: restore Surface if possible
        try:
            _remove_links_to_socket(links, surface_in)
            if old_surface_from_socket is not None:
                links.new(old_surface_from_socket, surface_in)
        except Exception:
            pass

        return False

    _ensure_active_material_output(mat)
    return True



def apply_oca_blend_mode(
    mat: bpy.types.Material,
    oca_mode: str,
    reporter: Optional[Callable] = None,
    warned_modes: Optional[Set[str]] = None,
) -> BlendDecision:
    if warned_modes is None:
        warned_modes = set()

    decision = decide_target(oca_mode)

    if mat is None or not getattr(mat, "use_nodes", False) or not getattr(mat, "node_tree", None):
        return decision

    try:
        mat["oca_blend_mode_original"] = (oca_mode or "").strip()
        mat["oca_blend_mode_target"] = decision.target
    except Exception:
        pass

    ng = bpy.data.node_groups.get(_GROUP_NAME)
    rebuild = not _group_has_required_sockets(ng) if ng else True
    ng = _ensure_blend_group(rebuild=rebuild)

    group_node = _ensure_group_node_in_material(mat, ng)

    applied = _wire_shader_to_output(mat, group_node, decision.target)

    mode_key = (oca_mode or "").strip().lower()
    if decision.severity in {"approx", "incompatible"} and mode_key not in warned_modes:
        warned_modes.add(mode_key)
        if decision.message:
            print(f"[OCA BLEND] {decision.message}")
            if reporter is not None:
                try:
                    reporter({"WARNING"}, decision.message)
                except Exception:
                    pass

    if not applied:
        msg = (
            f"Blend mode '{oca_mode}' mapped to '{decision.target}' but material '{mat.name}' "
            "could not be wired (no suitable shader source or output)."
        )
        print(f"[OCA BLEND] {msg}")
        if reporter is not None:
            try:
                reporter({"WARNING"}, msg)
            except Exception:
                pass

    return decision
